"""CRM local por conta. Regras e transações ficam fora da interface."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import asdict
from datetime import date

SERVICE_STATUSES = ['Orçamento', 'Aguardando início', 'Em andamento', 'Pausado', 'Concluído', 'Cancelado']
BILLING_TYPES = ['Única', 'Mensal', 'Por entrega', 'Personalizada']
DOCUMENT_STATUSES = ['Rascunho', 'Enviado', 'Assinado', 'Encerrado', 'Cancelado']
CLIENT_STATUSES = ['Lead', 'Ativo', 'Recorrente', 'Inativo', 'Arquivado']


def migrate(db):
    """Migração aditiva, transacional e repetível; não altera registros legados."""
    with db.connect() as probe:
        versioned = probe.execute("SELECT 1 FROM sqlite_master WHERE name='crm_migrations'").fetchone()
        needed = not versioned or not probe.execute('SELECT 1 FROM crm_migrations WHERE version=1').fetchone()
        if needed and probe.execute('SELECT 1 FROM clientes LIMIT 1').fetchone():
            backup = db.db_path.with_name(f'{db.db_path.stem}.pre-crm-{uuid.uuid4().hex}.bak')
            with closing(sqlite3.connect(backup)) as destination:
                probe.backup(destination)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('CREATE TABLE IF NOT EXISTS crm_migrations(version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        if conn.execute('SELECT 1 FROM crm_migrations WHERE version=1').fetchone():
            return
        statements = [
            '''CREATE TABLE crm_profiles(client_id INTEGER PRIMARY KEY REFERENCES clientes(id) ON DELETE CASCADE,
               whatsapp TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '')''',
            '''CREATE TABLE crm_services(id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
               name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', scope TEXT NOT NULL DEFAULT '',
               value_cents INTEGER NOT NULL CHECK(value_cents>=0), billing TEXT NOT NULL,
               start_date TEXT NOT NULL DEFAULT '', end_date TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
               notes TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
               created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
               UNIQUE(id,client_id))''',
            '''CREATE TABLE crm_documents(contract_id INTEGER PRIMARY KEY REFERENCES contracts(id) ON DELETE CASCADE,
               client_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE, service_id INTEGER,
               kind TEXT NOT NULL DEFAULT 'Prestação de serviços', content TEXT NOT NULL DEFAULT '',
               document_status TEXT NOT NULL DEFAULT 'Rascunho', billing TEXT NOT NULL DEFAULT 'Mensal',
               archived INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 0,
               FOREIGN KEY(service_id,client_id) REFERENCES crm_services(id,client_id))''',
            '''CREATE TABLE crm_contract_versions(id INTEGER PRIMARY KEY, contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
               revision INTEGER NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
               UNIQUE(contract_id,revision))''',
            '''CREATE TABLE crm_templates(id INTEGER PRIMARY KEY, name TEXT NOT NULL, content TEXT NOT NULL,
               updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
            '''CREATE TABLE crm_charges(id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
               service_id INTEGER, contract_id INTEGER REFERENCES contracts(id), title TEXT NOT NULL,
               amount_cents INTEGER NOT NULL CHECK(amount_cents>0), due_date TEXT NOT NULL, method TEXT NOT NULL DEFAULT '',
               cancelled INTEGER NOT NULL DEFAULT 0, operation_id TEXT NOT NULL UNIQUE,
               created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
               FOREIGN KEY(service_id,client_id) REFERENCES crm_services(id,client_id))''',
            '''CREATE TABLE crm_receipts(id INTEGER PRIMARY KEY, charge_id INTEGER NOT NULL REFERENCES crm_charges(id) ON DELETE CASCADE,
               amount_cents INTEGER NOT NULL CHECK(amount_cents>0), paid_date TEXT NOT NULL,
               method TEXT NOT NULL DEFAULT '', operation_id TEXT NOT NULL UNIQUE,
               created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
            '''CREATE TABLE crm_notes(id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
               content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
            '''CREATE TABLE crm_activities(id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
               event TEXT NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
            'CREATE INDEX idx_crm_services_client ON crm_services(client_id)',
            'CREATE INDEX idx_crm_charges_client ON crm_charges(client_id,due_date)',
            'CREATE INDEX idx_crm_receipts_charge ON crm_receipts(charge_id)',
            'CREATE INDEX idx_crm_activities_client ON crm_activities(client_id,id)',
            '''CREATE TRIGGER crm_client_created AFTER INSERT ON clientes BEGIN
               INSERT INTO crm_activities(client_id,event,description) VALUES(NEW.id,'cliente_criado','Cliente cadastrado'); END''',
            '''CREATE TRIGGER crm_client_updated AFTER UPDATE ON clientes BEGIN
               INSERT INTO crm_activities(client_id,event,description) VALUES(NEW.id,'cliente_alterado','Cadastro ou situação do cliente atualizado'); END''',
            '''CREATE TRIGGER crm_contract_created AFTER INSERT ON contracts BEGIN
               INSERT INTO crm_activities(client_id,event,description) VALUES(NEW.client_id,'contrato_criado','Contrato cadastrado'); END''',
            '''CREATE TRIGGER crm_document_owner_insert BEFORE INSERT ON crm_documents
               WHEN NOT EXISTS(SELECT 1 FROM contracts WHERE id=NEW.contract_id AND client_id=NEW.client_id)
               BEGIN SELECT RAISE(ABORT,'Contrato de outro cliente'); END''',
            '''CREATE TRIGGER crm_document_owner_update BEFORE UPDATE ON crm_documents
               WHEN NOT EXISTS(SELECT 1 FROM contracts WHERE id=NEW.contract_id AND client_id=NEW.client_id)
               BEGIN SELECT RAISE(ABORT,'Contrato de outro cliente'); END''',
            '''CREATE TRIGGER crm_charge_owner BEFORE INSERT ON crm_charges
               WHEN NEW.contract_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM contracts WHERE id=NEW.contract_id AND client_id=NEW.client_id)
               BEGIN SELECT RAISE(ABORT,'Contrato de outro cliente'); END''',
        ]
        for statement in statements:
            conn.execute(statement)
        conn.execute('INSERT INTO crm_migrations(version) VALUES(1)')


def clean(value, limit=10000, required=False):
    value = str(value or '').strip()
    if (required and not value) or len(value) > limit or any(ord(c) < 32 and c not in '\n\r\t' for c in value):
        raise ValueError('Preencha os campos obrigatórios e respeite o tamanho permitido.')
    return value


def money(value, positive=False):
    if type(value) is not int or value < (1 if positive else 0) or value > 100_000_000_000:
        raise ValueError('Valor monetário inválido.')
    return value


def dates(start, end):
    for value in (start, end):
        if value:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError('Use datas ISO válidas.')
    if start and end and end < start:
        raise ValueError('A data final deve ser igual ou posterior ao início.')


class CRM:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _client(conn, client_id):
        row = conn.execute('SELECT * FROM clientes WHERE id=?', (client_id,)).fetchone()
        if not row:
            raise ValueError('Cliente indisponível nesta conta.')
        return row

    @staticmethod
    def _owned(conn, table, record_id, client_id):
        if table not in {'crm_services', 'contracts', 'crm_charges'}:
            raise ValueError('Registro inválido.')
        row = conn.execute(f'SELECT * FROM {table} WHERE id=? AND client_id=?', (record_id, client_id)).fetchone()
        if not row:
            raise ValueError('Registro indisponível para este cliente.')
        return row

    @staticmethod
    def _event(conn, client_id, event, description):
        conn.execute('INSERT INTO crm_activities(client_id,event,description) VALUES(?,?,?)', (client_id,event,description))

    def profile(self, client_id):
        with self.db.connect() as conn:
            client = dict(self._client(conn, client_id))
            extra = conn.execute('SELECT whatsapp,tags FROM crm_profiles WHERE client_id=?', (client_id,)).fetchone()
        return {**client, **(dict(extra) if extra else dict(whatsapp='', tags=''))}

    def save_profile(self, client_id, whatsapp, tags):
        with self.db.connect() as conn:
            self._client(conn, client_id)
            conn.execute('INSERT INTO crm_profiles VALUES(?,?,?) ON CONFLICT(client_id) DO UPDATE SET whatsapp=excluded.whatsapp,tags=excluded.tags',
                         (client_id,clean(whatsapp,80),clean(tags,1000)))
            self._event(conn, client_id, 'perfil_alterado', 'WhatsApp ou tags atualizados')

    def services(self, client_id):
        with self.db.connect() as conn:
            self._client(conn, client_id)
            return [dict(r) for r in conn.execute('SELECT * FROM crm_services WHERE client_id=? ORDER BY id DESC', (client_id,))]

    def save_service(self, client_id, data, service_id=None, revision=None):
        event = 'servico_atualizado' if service_id else 'servico_criado'
        status, billing = data.get('status'), data.get('billing')
        if status not in SERVICE_STATUSES or billing not in BILLING_TYPES:
            raise ValueError('Situação ou forma de cobrança inválida.')
        start, end = data.get('start_date',''), data.get('end_date','')
        dates(start,end)
        values = (clean(data.get('name'),200,True),clean(data.get('description')),clean(data.get('scope')),
                  money(data.get('value_cents')),billing,start,end,status,clean(data.get('notes')))
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._client(conn,client_id)
            if service_id:
                previous = self._owned(conn,'crm_services',service_id,client_id)
                if previous['revision'] != revision:
                    raise ValueError('O serviço mudou. Reabra antes de salvar.')
                conn.execute('UPDATE crm_services SET name=?,description=?,scope=?,value_cents=?,billing=?,start_date=?,end_date=?,status=?,notes=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND client_id=?', (*values,service_id,client_id))
            else:
                service_id = conn.execute('INSERT INTO crm_services(name,description,scope,value_cents,billing,start_date,end_date,status,notes,client_id) VALUES(?,?,?,?,?,?,?,?,?,?)', (*values,client_id)).lastrowid
            self._event(conn,client_id,event,f'Serviço #{service_id}: {status}')
        return service_id

    def document(self, client_id, contract_id):
        with self.db.connect() as conn:
            base = dict(self._owned(conn,'contracts',contract_id,client_id))
            extra = conn.execute('SELECT * FROM crm_documents WHERE contract_id=? AND client_id=?', (contract_id,client_id)).fetchone()
            version = conn.execute('SELECT snapshot FROM crm_contract_versions WHERE contract_id=? ORDER BY revision DESC LIMIT 1', (contract_id,)).fetchone()
        defaults = dict(service_id=None,kind='Prestação de serviços',content=base['description'],document_status='Rascunho',billing='Mensal',archived=0,revision=0)
        snapshot = json.loads(version['snapshot']) if version else {}
        return {**base, **defaults, **(dict(extra) if extra else {}), 'parties':snapshot.get('parties',{}), 'payment_method':snapshot.get('payment_method','')}

    def save_document(self, contract, extra, expected_revision=0, source='manual'):
        self.db._validate_contract(contract)
        money(contract.value_cents)
        content = clean(extra.get('content'),80000)
        doc_status = extra.get('document_status','Rascunho')
        billing = extra.get('billing','Mensal')
        if doc_status not in DOCUMENT_STATUSES or billing not in BILLING_TYPES:
            raise ValueError('Situação documental ou cobrança inválida.')
        if source == 'ia' and doc_status != 'Rascunho':
            raise ValueError('A IA somente pode criar rascunhos.')
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._client(conn,contract.client_id)
            service_id = extra.get('service_id')
            if service_id:
                self._owned(conn,'crm_services',service_id,contract.client_id)
            old = None
            if contract.id:
                old = dict(self._owned(conn,'contracts',contract.id,contract.client_id))
                meta = conn.execute('SELECT * FROM crm_documents WHERE contract_id=?', (contract.id,)).fetchone()
                revision = meta['revision'] if meta else 0
                old_service = meta['service_id'] if meta else None
                if old_service != service_id and conn.execute('SELECT 1 FROM crm_charges WHERE contract_id=? LIMIT 1', (contract.id,)).fetchone():
                    raise ValueError('Contrato com financeiro vinculado: não é possível trocar o serviço.')
                if revision != expected_revision:
                    raise ValueError('Outra edição foi salva. Reabra o contrato para continuar.')
                if meta and (meta['archived'] or meta['document_status'] in {'Assinado','Encerrado','Cancelado'}):
                    raise ValueError('Documento finalizado: duplique para criar um novo rascunho.')
                if revision == 0:
                    conn.execute('INSERT INTO crm_contract_versions(contract_id,revision,snapshot) VALUES(?,?,?)',
                                 (contract.id,0,json.dumps(old,ensure_ascii=False)))
            else:
                revision = 0
                contract.id = conn.execute('INSERT INTO contracts(client_id,title) VALUES(?,?)', (contract.client_id,contract.title)).lastrowid
            conn.execute('UPDATE contracts SET title=?,description=?,value_cents=?,start_date=?,end_date=?,due_day=?,status=?,attachment_path=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND client_id=?',
                         (contract.title,contract.description,contract.value_cents,contract.start_date,contract.end_date,contract.due_day,contract.status,contract.attachment_path,contract.notes,contract.id,contract.client_id))
            conn.execute('''INSERT INTO crm_documents(contract_id,client_id,service_id,kind,content,document_status,billing,revision)
                         VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(contract_id) DO UPDATE SET service_id=excluded.service_id,kind=excluded.kind,
                         content=excluded.content,document_status=excluded.document_status,billing=excluded.billing,revision=excluded.revision''',
                         (contract.id,contract.client_id,service_id,clean(extra.get('kind'),200),content,doc_status,billing,revision+1))
            snapshot = {**asdict(contract),**extra,'revision':revision+1}
            conn.execute('INSERT INTO crm_contract_versions(contract_id,revision,snapshot) VALUES(?,?,?)', (contract.id,revision+1,json.dumps(snapshot,ensure_ascii=False)))
            self._event(conn,contract.client_id,'contrato_ia' if source=='ia' else 'contrato_atualizado',f'Contrato #{contract.id}: {doc_status}, versão {revision+1}')
        return contract.id

    def set_document_state(self, client_id, contract_id, state):
        if state not in {'Encerrado','Cancelado','Arquivado'}:
            raise ValueError('Transição inválida.')
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            previous = dict(self._owned(conn,'contracts',contract_id,client_id))
            previous_meta = conn.execute('SELECT * FROM crm_documents WHERE contract_id=?', (contract_id,)).fetchone()
            previous_version = conn.execute('SELECT snapshot FROM crm_contract_versions WHERE contract_id=? ORDER BY revision DESC LIMIT 1', (contract_id,)).fetchone()
            preserved = json.loads(previous_version['snapshot']) if previous_version else {}
            if not previous_version:
                conn.execute('INSERT INTO crm_contract_versions(contract_id,revision,snapshot) VALUES(?,?,?)',
                             (contract_id,0,json.dumps({**previous,**(dict(previous_meta) if previous_meta else {})},ensure_ascii=False)))
            conn.execute('INSERT OR IGNORE INTO crm_documents(contract_id,client_id) VALUES(?,?)', (contract_id,client_id))
            if state == 'Arquivado':
                conn.execute('UPDATE crm_documents SET archived=1 WHERE contract_id=?', (contract_id,))
            else:
                conn.execute('UPDATE crm_documents SET document_status=?,revision=revision+1 WHERE contract_id=?', (state,contract_id))
                conn.execute('UPDATE contracts SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?', (state,contract_id))
            self._event(conn,client_id,'contrato_status',f'Contrato #{contract_id}: {state}')
            snapshot = dict(conn.execute('SELECT * FROM contracts WHERE id=?', (contract_id,)).fetchone())
            meta = dict(conn.execute('SELECT * FROM crm_documents WHERE contract_id=?', (contract_id,)).fetchone())
            revision = conn.execute('SELECT COALESCE(MAX(revision),-1)+1 FROM crm_contract_versions WHERE contract_id=?', (contract_id,)).fetchone()[0]
            conn.execute('UPDATE crm_documents SET revision=? WHERE contract_id=?', (revision,contract_id))
            conn.execute('INSERT INTO crm_contract_versions(contract_id,revision,snapshot) VALUES(?,?,?)', (contract_id,revision,json.dumps({**preserved,**snapshot,**meta,'revision':revision},ensure_ascii=False)))

    def versions(self, client_id, contract_id):
        with self.db.connect() as conn:
            self._owned(conn,'contracts',contract_id,client_id)
            return [dict(r) for r in conn.execute('SELECT * FROM crm_contract_versions WHERE contract_id=? ORDER BY revision DESC', (contract_id,))]

    def templates(self):
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute('SELECT * FROM crm_templates ORDER BY name,id')]

    def save_template(self, name, content, template_id=None):
        values = (clean(name,200,True),clean(content,80000,True))
        with self.db.connect() as conn:
            if template_id:
                if conn.execute('UPDATE crm_templates SET name=?,content=?,updated_at=CURRENT_TIMESTAMP WHERE id=?', (*values,template_id)).rowcount != 1:
                    raise ValueError('Modelo indisponível nesta conta.')
            else:
                template_id = conn.execute('INSERT INTO crm_templates(name,content) VALUES(?,?)',values).lastrowid
        return template_id

    def add_charge(self, client_id, title, amount_cents, due_date, method='', service_id=None, contract_id=None, operation_id=None):
        dates(due_date,due_date)
        if not due_date:
            raise ValueError('Informe o vencimento.')
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._client(conn,client_id)
            if service_id:
                self._owned(conn,'crm_services',service_id,client_id)
            if contract_id:
                self._owned(conn,'contracts',contract_id,client_id)
                meta = conn.execute('SELECT service_id FROM crm_documents WHERE contract_id=?', (contract_id,)).fetchone()
                if meta and meta['service_id']:
                    if service_id and meta['service_id'] != service_id:
                        raise ValueError('O contrato pertence a outro serviço.')
                    service_id = meta['service_id']
            operation_id = operation_id or uuid.uuid4().hex
            previous = conn.execute('SELECT id,client_id FROM crm_charges WHERE operation_id=?', (operation_id,)).fetchone()
            if previous:
                if previous['client_id'] != client_id:
                    raise ValueError('Operação de outro cliente.')
                return previous['id']
            ident = conn.execute('INSERT INTO crm_charges(client_id,service_id,contract_id,title,amount_cents,due_date,method,operation_id) VALUES(?,?,?,?,?,?,?,?)',
                                 (client_id,service_id,contract_id,clean(title,200,True),money(amount_cents,True),due_date,clean(method,200),operation_id)).lastrowid
            self._event(conn,client_id,'cobranca_criada',f'Cobrança #{ident} registrada')
            return ident

    def receive(self, client_id, charge_id, amount_cents, paid_date, method='', operation_id=None):
        dates(paid_date,paid_date)
        if not paid_date or paid_date > date.today().isoformat():
            raise ValueError('Informe a data real do recebimento, até hoje.')
        amount_cents = money(amount_cents,True)
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            charge = self._owned(conn,'crm_charges',charge_id,client_id)
            operation_id = operation_id or uuid.uuid4().hex
            previous = conn.execute('SELECT id,charge_id FROM crm_receipts WHERE operation_id=?', (operation_id,)).fetchone()
            if previous:
                if previous['charge_id'] != charge_id:
                    raise ValueError('Operação de outra cobrança.')
                return previous['id']
            received = conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM crm_receipts WHERE charge_id=?', (charge_id,)).fetchone()[0]
            if charge['cancelled'] or received + amount_cents > charge['amount_cents']:
                raise ValueError('Cobrança cancelada ou recebimento maior que o saldo pendente.')
            ident = conn.execute('INSERT INTO crm_receipts(charge_id,amount_cents,paid_date,method,operation_id) VALUES(?,?,?,?,?)',
                                 (charge_id,amount_cents,paid_date,clean(method,200),operation_id)).lastrowid
            self._event(conn,client_id,'pagamento_registrado',f'Recebimento registrado na cobrança #{charge_id}')
            return ident

    def cancel_charge(self, client_id, charge_id):
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._owned(conn,'crm_charges',charge_id,client_id)
            if conn.execute('SELECT 1 FROM crm_receipts WHERE charge_id=?', (charge_id,)).fetchone():
                raise ValueError('Não é possível cancelar uma cobrança com recebimentos registrados.')
            conn.execute('UPDATE crm_charges SET cancelled=1 WHERE id=?', (charge_id,))
            self._event(conn,client_id,'cobranca_cancelada',f'Cobrança #{charge_id} cancelada')

    def finance(self, client_id, service_id=None):
        with self.db.connect() as conn:
            self._client(conn,client_id)
            if service_id:
                self._owned(conn,'crm_services',service_id,client_id)
            rows = [dict(r) for r in conn.execute('''SELECT c.*,COALESCE((SELECT SUM(r.amount_cents) FROM crm_receipts r WHERE r.charge_id=c.id),0) received
                       FROM crm_charges c WHERE client_id=? ORDER BY due_date,id''', (client_id,)) if service_id is None or r['service_id']==service_id]
            receipts = [dict(r) for r in conn.execute('''SELECT r.*,c.title,c.service_id FROM crm_receipts r JOIN crm_charges c ON c.id=r.charge_id
                        WHERE c.client_id=? ORDER BY paid_date DESC,r.id DESC''', (client_id,)) if service_id is None or r['service_id']==service_id]
        active = [r for r in rows if not r['cancelled']]
        pending = [r for r in active if r['amount_cents'] > r['received']]
        return dict(charges=rows,receipts=receipts,billed=sum(r['amount_cents'] for r in active),received=sum(r['received'] for r in active),
                    pending=sum(r['amount_cents']-r['received'] for r in pending),
                    overdue=sum(r['amount_cents']-r['received'] for r in pending if r['due_date'] < date.today().isoformat()),
                    next_payment=next((r for r in pending if r['due_date'] >= date.today().isoformat()),None))

    def add_note(self, client_id, content):
        with self.db.connect() as conn:
            self._client(conn,client_id)
            conn.execute('INSERT INTO crm_notes(client_id,content) VALUES(?,?)', (client_id,clean(content,10000,True)))
            self._event(conn,client_id,'anotacao_adicionada','Anotação interna adicionada')

    def history(self, client_id):
        with self.db.connect() as conn:
            self._client(conn,client_id)
            return {name:[dict(r) for r in conn.execute(f'SELECT * FROM crm_{name} WHERE client_id=? ORDER BY id DESC', (client_id,))]
                    for name in ('notes','activities')}
