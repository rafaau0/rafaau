"""Fluxos Tk opcionais: CRM_UI_TESTS=1, com banco e plano isolados."""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import customtkinter as ctk

from content_planner.crm import CRM
from content_planner.database import Database
from content_planner.form_modal import FormModal
from content_planner.plan_rules import RULES
from content_planner.ui import ContentPlannerApp


@unittest.skipUnless(os.getenv('CRM_UI_TESTS')=='1','Requer sessão gráfica Windows; execute com CRM_UI_TESTS=1')
class CRMUITests(unittest.TestCase):
    def test_existing_and_new_forms(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder)/'planner.db')
            with patch('content_planner.ui.Database',return_value=db),patch('content_planner.ui.current_plan_rules',return_value=RULES['pro']):
                app=ContentPlannerApp()
                app.withdraw()
                failures=[]
                app.report_callback_exception=lambda *args:failures.append(str(args))
                app._show_warning=lambda title,text:failures.append(f'{title}: {text}')

                def modal():
                    app.update()
                    return next(w for w in reversed(app.winfo_children()) if isinstance(w,FormModal))

                def field(window,label,value):
                    children=window.body.winfo_children()
                    for index,child in enumerate(children[:-1]):
                        if isinstance(child,ctk.CTkLabel) and child.cget('text')==label:
                            widget=children[index+1]
                            if isinstance(widget,ctk.CTkOptionMenu):
                                widget.set(value)
                            elif isinstance(widget,ctk.CTkTextbox):
                                widget.delete('1.0','end'); widget.insert('1.0',value)
                            else:
                                widget.delete(0,'end'); widget.insert(0,value)
                            return
                    raise AssertionError('Campo não encontrado: '+label)

                def click(parent,text):
                    for child in parent.winfo_children():
                        if isinstance(child,ctk.CTkButton) and child.cget('text')==text:
                            child.invoke(); app.update(); return True
                        if click(child,text):
                            return True
                    return False

                try:
                    app._open_client_modal()
                    window=modal(); field(window,'Nome','Cliente UI')
                    self.assertTrue(click(window,'Salvar'))
                    client=db.search_clients()[0]
                    app._open_client_modal(client)
                    window=modal(); field(window,'Empresa / razão social','Empresa UI'); click(window,'Salvar')
                    client=db.get_client(client.id)
                    self.assertEqual(client.company_name,'Empresa UI')
                    app._open_client_profile(client)
                    app.update()
                    app._crm_service_form(client)
                    window=modal(); field(window,'Nome','Serviço UI'); field(window,'Valor','1.000,00')
                    field(window,'Situação','Em andamento'); click(window,'Salvar')
                    service=CRM(db).services(client.id)[0]
                    app._crm_service_form(client,service)
                    window=modal(); field(window,'Situação','Concluído'); click(window,'Salvar')
                    self.assertEqual(CRM(db).services(client.id)[0]['status'],'Concluído')
                    app._open_contract_modal(client,service=service)
                    window=modal(); field(window,'Conteúdo do contrato','Contrato manual\nCláusula revisada.'); click(window,'Salvar')
                    contract=db.list_contracts(client.id)[0]
                    app._open_contract_modal(client,contract)
                    window=modal(); field(window,'Conteúdo do contrato','Segunda versão.'); click(window,'Salvar')
                    self.assertEqual(len(CRM(db).versions(client.id,contract.id)),2)
                    app._crm_charge_form(client,service)
                    window=modal(); field(window,'Descrição / competência','Parcela UI'); field(window,'Valor','1.000,00')
                    field(window,'Vencimento (DD/MM/AAAA)',date.today().strftime('%d/%m/%Y')); click(window,'Salvar')
                    charge=CRM(db).finance(client.id)['charges'][0]
                    app._crm_receipt_form(client,charge)
                    window=modal(); field(window,'Valor recebido','500,00'); click(window,'Salvar')
                    self.assertEqual(CRM(db).finance(client.id)['pending'],50000)
                    app._crm_note(client)
                    window=modal(); field(window,'Anotação','Contato por WhatsApp.'); click(window,'Salvar')
                    self.assertEqual(CRM(db).history(client.id)['notes'][0]['content'],'Contato por WhatsApp.')
                    for tab in ['Visão Geral','Serviços / Projetos','Contratos','Financeiro','Histórico / Anotações']:
                        app._open_client_profile(client,tab); app.update()
                    app._crm_ai_form(client); app.update(); modal().destroy()
                    app._crm_templates(); app.update(); modal().destroy()
                    app._crm_provider(); app.update(); modal().destroy()
                    app.geometry('960x640'); app.update()
                    self.assertEqual(failures,[])
                finally:
                    app.destroy()
