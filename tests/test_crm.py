import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from content_planner.crm import CRM
from content_planner.database import Client, Contract, Database
from content_planner.contract_documents import fill_template


class CRMTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name)/'account'/ 'db.sqlite'
        self.db = Database(self.path)
        self.crm = CRM(self.db)
        self.client = self.db.create_client(Client(None,'Cliente','','','','',''))
        self.other = self.db.create_client(Client(None,'Outro','','','','',''))

    def tearDown(self):
        self.folder.cleanup()

    def service(self, **overrides):
        data = dict(name='Design',description='Descrição',scope='Escopo',value_cents=10000,billing='Única',status='Em andamento')
        data.update(overrides)
        return self.crm.save_service(self.client,data)

    def test_migration_repeated_and_old_data_preserved(self):
        contract = Contract(None,self.client,'Anterior',description='Texto anterior',value_cents=900,status='Ativo')
        ident = self.db.create_contract(contract)
        # Remove apenas tabelas/triggers novos em uma fixture para simular versão anterior.
        with self.db.connect() as conn:
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
                conn.execute(f'DROP TRIGGER {row[0]}')
            for table in ['crm_receipts','crm_charges','crm_contract_versions','crm_documents','crm_services','crm_profiles','crm_templates','crm_notes','crm_activities','crm_migrations']:
                conn.execute(f'DROP TABLE {table}')
        upgraded = Database(self.path)
        self.assertEqual(upgraded.get_contract(ident).description,'Texto anterior')
        self.assertEqual(upgraded.get_client(self.client).name,'Cliente')
        self.assertEqual(len(list(self.path.parent.glob('*.bak'))),1)
        Database(self.path)
        self.assertEqual(len(list(self.path.parent.glob('*.bak'))),1)
        with upgraded.connect() as conn:
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_service_status_validation_and_concurrent_edit(self):
        ident = self.service()
        service = self.crm.services(self.client)[0]
        service['status'] = 'Concluído'
        self.crm.save_service(self.client,service,ident,service['revision'])
        self.assertEqual(self.crm.services(self.client)[0]['status'],'Concluído')
        with self.assertRaises(ValueError):
            self.crm.save_service(self.client,service,ident,service['revision'])
        with self.assertRaises(ValueError):
            self.crm.save_service(self.other,service,ident,2)
        with self.assertRaises(ValueError):
            self.service(value_cents=-1)
        with self.assertRaises(ValueError):
            self.service(start_date='2026-09-08',end_date='2026-09-07')

    def test_contract_versions_signed_immutable_and_duplicate(self):
        service = self.service()
        contract = Contract(None,self.client,'Contrato',description='Escopo',value_cents=100)
        extra = dict(content='Texto inicial',document_status='Rascunho',billing='Única',service_id=service)
        ident = self.crm.save_document(contract,extra)
        extra['content'] = 'Texto revisado'
        self.crm.save_document(contract,extra,1)
        self.assertEqual(len(self.crm.versions(self.client,ident)),2)
        self.assertEqual(json.loads(self.crm.versions(self.client,ident)[1]['snapshot'])['content'],'Texto inicial')
        with self.assertRaises(ValueError):
            self.crm.save_document(contract,extra,1)
        extra['document_status'] = 'Assinado'
        self.crm.save_document(contract,extra,2)
        with self.assertRaises(ValueError):
            self.crm.save_document(contract,extra,3)
        with self.assertRaises(ValueError):
            self.db.update_contract(contract)
        with self.assertRaises(ValueError):
            self.db.delete_contract(ident)
        duplicate = replace(contract,id=None)
        extra['document_status']='Rascunho'
        new_id = self.crm.save_document(duplicate,extra)
        self.assertNotEqual(new_id,ident)
        self.crm.set_document_state(self.client,ident,'Arquivado')
        self.assertEqual(self.crm.document(self.client,ident)['archived'],1)

    def test_cross_client_links_and_account_isolation(self):
        ident = self.service()
        with self.assertRaises(ValueError):
            self.crm.save_document(Contract(None,self.other,'Contrato'),dict(service_id=ident))
        contract = Contract(None,self.client,'Contrato')
        cid = self.crm.save_document(contract,{})
        with self.assertRaises(ValueError):
            self.crm.document(self.other,cid)
        with self.assertRaises(ValueError):
            self.crm.add_charge(self.other,'Cobrança',100,'2026-09-07',contract_id=cid)
        other_db = Database(Path(self.folder.name)/'account-b'/'db.sqlite')
        with self.assertRaises(ValueError):
            CRM(other_db).document(self.client,cid)
        with self.assertRaises(ValueError):
            CRM(other_db).profile(self.client)

    def test_partial_receipts_idempotency_and_overdue(self):
        yesterday = (date.today()-timedelta(days=1)).isoformat()
        charge = self.crm.add_charge(self.client,'Parcela',10000,yesterday,operation_id='charge-op')
        self.assertEqual(self.crm.add_charge(self.client,'Parcela',10000,yesterday,operation_id='charge-op'),charge)
        receipt = self.crm.receive(self.client,charge,2500,date.today().isoformat(),operation_id='receipt-op')
        self.assertEqual(self.crm.receive(self.client,charge,2500,date.today().isoformat(),operation_id='receipt-op'),receipt)
        summary = self.crm.finance(self.client)
        self.assertEqual((summary['billed'],summary['received'],summary['pending'],summary['overdue']),(10000,2500,7500,7500))
        with self.assertRaises(ValueError):
            self.crm.receive(self.client,charge,8000,date.today().isoformat())
        with self.assertRaises(ValueError):
            self.crm.receive(self.other,charge,100,date.today().isoformat())
        with self.assertRaises(ValueError):
            self.crm.cancel_charge(self.client,charge)
        self.crm.receive(self.client,charge,7500,date.today().isoformat())
        self.assertEqual(self.crm.finance(self.client)['pending'],0)
        self.assertEqual(self.crm.finance(self.other)['received'],0)

    def test_finance_relationships_and_cancellation(self):
        service = self.service()
        contract = Contract(None,self.client,'Contrato')
        cid = self.crm.save_document(contract,dict(service_id=service))
        charge = self.crm.add_charge(self.client,'Parcela',500,date.today().isoformat(),contract_id=cid)
        self.assertEqual(self.crm.finance(self.client,service)['billed'],500)
        with self.assertRaises(ValueError):
            self.db.delete_contract(cid)
        self.crm.cancel_charge(self.client,charge)
        self.assertEqual(self.crm.finance(self.client)['billed'],0)
        self.assertEqual(len(self.crm.finance(self.client)['charges']),1)
        with self.assertRaises(ValueError):
            self.crm.receive(self.client,charge,100,date.today().isoformat())

    def test_profiles_notes_templates_and_persistence(self):
        self.crm.save_profile(self.client,'11999999999','design, recorrente')
        self.crm.add_note(self.client,'Prefere WhatsApp')
        template = self.crm.save_template('Meu modelo','Olá {{cliente_nome}}')
        self.crm.save_template('Meu modelo revisado','Texto revisado',template)
        reopened = CRM(Database(self.path))
        self.assertEqual(reopened.profile(self.client)['whatsapp'],'11999999999')
        self.assertEqual(reopened.history(self.client)['notes'][0]['content'],'Prefere WhatsApp')
        self.assertEqual(reopened.history(self.other)['notes'],[])
        self.assertEqual(reopened.templates()[0]['content'],'Texto revisado')
        self.assertEqual(fill_template('{{cliente_nome}} {{desconhecido}}',{'cliente_nome':'<Nome>'}),'<Nome> {{desconhecido}}')
        self.assertGreaterEqual(len(reopened.history(self.client)['activities']),3)

    def test_recurring_customer_and_nonmonthly_contract_dashboard(self):
        client = self.db.get_client(self.client)
        client.status='Recorrente'
        self.db.update_client(client)
        self.assertEqual(len(self.db.search_clients(status='Recorrente')),1)
        self.crm.save_document(Contract(None,self.client,'Avulso',value_cents=200,status='Ativo'),dict(billing='Única'))
        self.crm.save_document(Contract(None,self.client,'Mensal',value_cents=300,status='Ativo'),dict(billing='Mensal'))
        self.assertEqual(self.db.dashboard_stats()['monthly_revenue_cents'],300)

    def test_empty_and_draft_only_ai(self):
        self.assertEqual(self.crm.services(self.client),[])
        self.assertEqual(self.crm.finance(self.client)['billed'],0)
        with self.assertRaises(ValueError):
            self.crm.save_document(Contract(None,self.client,'IA'),dict(document_status='Assinado'),source='ia')

    def test_contract_service_cannot_change_after_charge(self):
        first = self.service()
        second = self.service(name='Outro serviço')
        contract = Contract(None,self.client,'Contrato')
        self.crm.save_document(contract,dict(service_id=first))
        self.crm.add_charge(self.client,'Parcela',100,date.today().isoformat(),contract_id=contract.id)
        with self.assertRaises(ValueError):
            self.crm.save_document(contract,dict(service_id=second),1)
        self.assertEqual(self.crm.document(self.client,contract.id)['service_id'],first)
        with self.assertRaises(ValueError):
            self.db.delete_client(self.client)

    def test_money_rejects_nan(self):
        from content_planner.client_management import parse_money_to_cents
        with self.assertRaises(ValueError):
            parse_money_to_cents('NaN')
