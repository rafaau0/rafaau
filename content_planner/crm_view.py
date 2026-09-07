"""Abas do CRM, reaproveitando formulários, tema, conta e banco do desktop."""
from __future__ import annotations

import json
import queue
import shutil
import sqlite3
import threading
import uuid
from dataclasses import replace
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import requests

from .account_sessions import current_token
from .client_management import format_date_br, format_money, parse_date_input, parse_money_to_cents, CONTRACT_STATUSES
from .contract_documents import BASE_TEMPLATE, TEMPLATE_NAMES, REVIEW_NOTICE, fill_template, variables, generate_pdf
from .crm import CRM, BILLING_TYPES, DOCUMENT_STATUSES, SERVICE_STATUSES
from .database import Contract
from .design_system import COLORS as UI, font, primary_button, secondary_button
from .form_modal import FormModal
from .plan_rules import API_URL


class CRMMixin:
    @property
    def crm(self):
        return CRM(self.db)

    def _crm_run(self, action, after=None):
        try:
            result = action()
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._show_warning('Gestão de clientes', str(exc) if not isinstance(exc,sqlite3.Error) else 'Não foi possível salvar. Verifique os vínculos e tente novamente.')
            return None
        if after:
            after()
        return result

    @staticmethod
    def _crm_text(parent, text, heading=False):
        label = ctk.CTkLabel(parent,text=text,justify='left',anchor='w',font=font(16 if heading else 12,'bold' if heading else 'normal'),
                             text_color=UI['text'] if heading else UI['muted'])
        label.pack(fill='x',padx=12,pady=(8,4))
        label.bind('<Configure>',lambda e: label.configure(wraplength=max(180,e.width-24)))
        return label

    @staticmethod
    def _crm_button(parent, text, command, primary=False):
        button = ctk.CTkButton(parent,text=text,command=command,**(primary_button() if primary else secondary_button()))
        button.pack(fill='x',padx=12,pady=5)
        return button

    @staticmethod
    def _crm_box(parent):
        box = ctk.CTkFrame(parent,fg_color=UI['surface'],border_width=1,border_color=UI['border'],corner_radius=6)
        box.pack(fill='x',padx=4,pady=8)
        return box

    def _open_client_profile(self, client, tab='Visão Geral'):
        fresh = self.db.get_client(client.id)
        if fresh is None:
            self._show_warning('Cliente','Cliente indisponível nesta conta.')
            self.show_clients()
            return
        frame = self._set_active_view('Clientes',fresh.name,'Relacionamento, serviços, contratos e recebimentos deste cliente.')
        self._crm_button(frame,'Voltar para clientes',self.show_clients)
        tabs = ctk.CTkTabview(frame,fg_color=UI['surface_alt'])
        tabs.pack(fill='both',expand=True,pady=10)
        names = ['Visão Geral','Serviços / Projetos','Contratos','Financeiro','Histórico / Anotações']
        for name in names:
            tabs.add(name)
        profile = self.crm.profile(fresh.id)
        services = self.crm.services(fresh.id)
        contracts = self.db.list_contracts(fresh.id)
        finance = self.crm.finance(fresh.id)
        history = self.crm.history(fresh.id)
        overview = tabs.tab(names[0])
        self._crm_text(overview,f"{fresh.status} · Cliente desde {profile['created_at'][:10]}",True)
        self._crm_text(overview,' · '.join(f'{label}: {value}' for label,value in [('Empresa',fresh.company_name),('Documento',fresh.document),('E-mail',fresh.email),('Telefone',fresh.phone),('WhatsApp',profile['whatsapp']),('Contato',fresh.contact_name),('Endereço',fresh.address),('Tags',profile['tags'])] if value))
        self._crm_text(overview,f'Nicho: {fresh.niche or "—"} · Instagram: {fresh.instagram or "—"} · Frequência: {fresh.posting_frequency or "—"}\nObjetivo: {fresh.objective or "—"}\nObservações: {fresh.notes or "—"}')
        docs = [self.crm.document(fresh.id,c.id) for c in contracts]
        contracted = sum(s['value_cents'] for s in services if s['status'] not in {'Orçamento','Cancelado'})
        contracted += sum(d['value_cents'] for d in docs if not d['service_id'] and d['status'] not in {'Rascunho','Cancelado'})
        self._crm_text(overview,f"Valor contratado de referência: {format_money(contracted)}\nCobranças registradas: {format_money(finance['billed'])} · Recebido: {format_money(finance['received'])}\nPendente: {format_money(finance['pending'])} · Vencido: {format_money(finance['overdue'])}",True)
        self._crm_text(overview,'O valor contratado soma serviços aprovados e contratos avulsos, sem somar novamente contratos vinculados. Valores mensais representam um mês; cobranças e recebimentos são lançados no Financeiro.')
        active = [s for s in services if s['status'] in {'Aguardando início','Em andamento','Pausado'}]
        self._crm_text(overview,f"{len(services)} serviços · {len(active)} ativos · {len(contracts)} contratos\nÚltimo serviço: {services[0]['name'] if services else 'Nenhum'}")
        for title, lines in [
            ('Serviços ativos',[f"{s['name']} · {s['status']} · prazo {format_date_br(s['end_date'])}" for s in active[:5]]),
            ('Contratos recentes',[f"{d['title']} · {d['document_status']}" for d in sorted(docs,key=lambda d:d['id'],reverse=True)[:5]]),
            ('Recebimentos recentes',[f"{format_date_br(r['paid_date'])} · {r['title']} · {format_money(r['amount_cents'])}" for r in finance['receipts'][:5]]),
            ('Próximas pendências',[f"{format_date_br(r['due_date'])} · {r['title']} · saldo {format_money(r['amount_cents']-r['received'])}" for r in finance['charges'] if not r['cancelled'] and r['amount_cents']>r['received']][:5]),
            ('Últimas atividades',[f"{r['created_at']} UTC · {r['description']}" for r in history['activities'][:5]]),
        ]:
            self._crm_text(overview,title,True)
            self._crm_text(overview,'\n'.join(lines) or 'Nenhum registro.')
        self._crm_button(overview,'Editar cadastro',lambda:self._open_client_modal(fresh))
        self._crm_button(overview,'WhatsApp e tags',lambda:self._crm_profile_extra(fresh))
        self._crm_button(overview,'Abrir planejamento',lambda:self._select_client_calendar(fresh))
        self._crm_button(overview,'Excluir cliente',lambda:self._delete_client(fresh))

        services_tab = tabs.tab(names[1])
        self._crm_button(services_tab,'Novo serviço / projeto',lambda:self._crm_service_form(fresh),True)
        if not services:
            self._crm_text(services_tab,'Nenhum serviço cadastrado.')
        for service in services:
            box = self._crm_box(services_tab)
            self._crm_text(box,service['name'],True)
            self._crm_text(box,f"{service['status']} · {format_money(service['value_cents'])} · {service['billing']}\n{format_date_br(service['start_date'])} até {format_date_br(service['end_date'])}\n{service['description']}\nEscopo: {service['scope']}\nObservações: {service['notes']}")
            self._crm_button(box,'Editar / concluir / cancelar',lambda s=service:self._crm_service_form(fresh,s))
            self._crm_button(box,'Criar contrato para este serviço',lambda s=service:self._open_contract_modal(fresh,service=s))
            self._crm_button(box,'Pagamentos deste serviço',lambda s=service:self._crm_service_finance(fresh,s))
            related = [d['title'] for d in docs if d['service_id']==service['id']]
            self._crm_text(box,'Contratos: '+(', '.join(related) or 'Nenhum'))

        contracts_tab = tabs.tab(names[2])
        self._crm_button(contracts_tab,'Novo contrato / usar modelo',lambda:self._open_contract_modal(fresh),True)
        self._crm_button(contracts_tab,'Gerar contrato com IA',lambda:self._crm_ai_form(fresh))
        self._crm_button(contracts_tab,'Meus modelos',self._crm_templates)
        self._crm_button(contracts_tab,'Dados do prestador',self._crm_provider)
        if not docs:
            self._crm_text(contracts_tab,'Nenhum contrato cadastrado.')
        for doc in docs:
            box = self._crm_box(contracts_tab)
            self._crm_text(box,doc['title']+(' · Arquivado' if doc['archived'] else ''),True)
            self._crm_text(box,f"Documento: {doc['document_status']} · Comercial: {doc['status']} · Versão {doc['revision']}\n{format_money(doc['value_cents'])} · {doc['billing']} · {format_date_br(doc['start_date'])} até {format_date_br(doc['end_date'])}")
            c = next(c for c in contracts if c.id==doc['id'])
            self._crm_button(box,'Visualizar / editar conteúdo',lambda c=c:self._open_contract_modal(fresh,c))
            self._crm_button(box,'Duplicar como rascunho',lambda c=c,d=doc:self._open_contract_modal(fresh,replace(c,id=None,status='Rascunho',operation_id=None),draft={**d,'document_status':'Rascunho','revision':0,'archived':0}))
            self._crm_button(box,'Gerar PDF',lambda d=doc:self._crm_export_pdf(fresh,d))
            if c.attachment_path:
                self._crm_button(box,'Abrir PDF anexado',lambda c=c:self._open_contract_attachment(c))
                self._crm_button(box,'Salvar cópia do PDF anexado',lambda c=c:self._crm_copy_pdf(c))
            self._crm_button(box,'Histórico de versões',lambda d=doc:self._crm_versions(fresh,d))
            self._crm_button(box,'Alterar situação / arquivar',lambda d=doc:self._crm_document_state(fresh,d))
            self._crm_button(box,'Excluir rascunho',lambda c=c:self._crm_delete_contract(fresh,c))

        self._crm_finance_tab(tabs.tab(names[3]),fresh,finance)
        history_tab = tabs.tab(names[4])
        self._crm_button(history_tab,'Adicionar anotação',lambda:self._crm_note(fresh),True)
        self._crm_text(history_tab,'Anotações internas',True)
        for note in history['notes']:
            self._crm_text(history_tab,f"{note['created_at']} UTC\n{note['content']}")
        self._crm_text(history_tab,'Histórico de atividades',True)
        self._crm_text(history_tab,'Os eventos são registrados a partir da atualização do CRM; o passado não foi reconstruído.')
        for event in history['activities']:
            self._crm_text(history_tab,f"{event['created_at']} UTC · {event['event']}\n{event['description']}")
        tabs.set(tab if tab in names else names[0])

    def _crm_profile_extra(self, client):
        data = self.crm.profile(client.id)
        modal = FormModal(self,'Contato e tags',500,360)
        whatsapp = modal.entry('WhatsApp',data['whatsapp'])
        tags = modal.entry('Tags (separadas por vírgula)',data['tags'])
        modal.actions(lambda:self._crm_run(lambda:self.crm.save_profile(client.id,whatsapp.get(),tags.get()),lambda:(modal.destroy(),self._open_client_profile(client))))

    def _crm_service_form(self, client, service=None):
        data = service or {}
        modal = FormModal(self,'Serviço / projeto',680,760)
        entries = {key:modal.entry(label,str(data.get(key,''))) for key,label in [('name','Nome'),('description','Descrição'),('scope','Escopo')]}
        value = modal.entry('Valor',format_money(data.get('value_cents',0)))
        billing = modal.option('Forma de cobrança',BILLING_TYPES,data.get('billing','Única'))
        start = modal.entry('Início (DD/MM/AAAA)',format_date_br(data.get('start_date','')).replace('—',''))
        end = modal.entry('Prazo (DD/MM/AAAA)',format_date_br(data.get('end_date','')).replace('—',''))
        status = modal.option('Situação',SERVICE_STATUSES,data.get('status','Orçamento'))
        notes = modal.text('Observações',data.get('notes',''))
        def save():
            payload = {key:widget.get() for key,widget in entries.items()}
            payload.update(value_cents=parse_money_to_cents(value.get()),billing=billing.get(),start_date=parse_date_input(start.get()),end_date=parse_date_input(end.get()),status=status.get(),notes=notes.get('1.0','end').strip())
            return self.crm.save_service(client.id,payload,data.get('id'),data.get('revision'))
        modal.actions(lambda:self._crm_run(save,lambda:(modal.destroy(),self._open_client_profile(client,'Serviços / Projetos'))))

    def _crm_provider_data(self):
        try:
            data = json.loads(self.db.get_setting('CRM_PROVIDER','{}'))
            return data if isinstance(data,dict) else {}
        except ValueError:
            return {}

    def _crm_provider(self):
        data = self._crm_provider_data()
        modal = FormModal(self,'Dados do prestador',500,420)
        fields = {key:modal.entry(label,data.get(key,'')) for key,label in [('name','Nome / empresa'),('document','CPF/CNPJ'),('address','Endereço')]}
        modal.actions(lambda:self._crm_run(lambda:self.db.set_setting('CRM_PROVIDER',json.dumps({k:w.get().strip() for k,w in fields.items()},ensure_ascii=False)),modal.destroy))

    def _crm_templates(self):
        modal = FormModal(self,'Modelos reutilizáveis',650,650)
        self._crm_text(modal.body,'Modelos são pontos de partida editáveis. Revise e complete as condições antes de usar.')
        self._crm_button(modal.body,'Criar modelo personalizado',lambda:(modal.destroy(),self._crm_template_form()))
        for item in self.crm.templates():
            self._crm_button(modal.body,item['name'],lambda item=item:(modal.destroy(),self._crm_template_form(item)))
        for name in TEMPLATE_NAMES:
            self._crm_button(modal.body,'Criar a partir de: '+name,lambda name=name:(modal.destroy(),self._crm_template_form({'name':name,'content':name+'\n\n'+BASE_TEMPLATE})))

    def _crm_template_form(self, item=None):
        item = item or {}
        modal = FormModal(self,'Editar modelo',760,760)
        name = modal.entry('Nome',item.get('name',''))
        self._crm_text(modal.body,'Variáveis: {{cliente_nome}}, {{cliente_documento}}, {{cliente_endereco}}, {{prestador_nome}}, {{prestador_documento}}, {{servico_nome}}, {{servico_descricao}}, {{servico_valor}}, {{forma_pagamento}}, {{data_inicio}}, {{data_fim}}')
        content = modal.text('Conteúdo',item.get('content',BASE_TEMPLATE),380)
        modal.actions(lambda:self._crm_run(lambda:self.crm.save_template(name.get(),content.get('1.0','end').strip(),item.get('id')),modal.destroy))

    def _open_contract_modal(self, client, contract=None, service=None, draft=None, source='manual'):
        data = self.crm.document(client.id,contract.id) if contract and contract.id else (draft or {})
        service = service or next((s for s in self.crm.services(client.id) if s['id']==data.get('service_id')),None)
        contract = contract or Contract(None,client.id,data.get('title','Prestação de serviços'),
                                        value_cents=(service or {}).get('value_cents',0),start_date=(service or {}).get('start_date',''),end_date=(service or {}).get('end_date',''))
        locked = data.get('document_status') in {'Assinado','Encerrado','Cancelado'} or data.get('archived')
        modal = FormModal(self,'Contrato',800,820)
        title = modal.entry('Título',contract.title)
        kind = modal.entry('Tipo',data.get('kind','Prestação de serviços'))
        services = {'Sem serviço vinculado':None,**{f"{s['name']} · #{s['id']}":s for s in self.crm.services(client.id)}}
        service_menu = modal.option('Serviço / projeto',list(services),next((k for k,v in services.items() if v and service and v['id']==service['id']),'Sem serviço vinculado'))
        description = modal.text('Descrição / escopo',contract.description or (service or {}).get('scope',''),70)
        value = modal.entry('Valor de referência',format_money(contract.value_cents))
        billing = modal.option('Periodicidade do valor',BILLING_TYPES,data.get('billing',(service or {}).get('billing','Mensal')))
        payment = modal.entry('Condições de pagamento',data.get('payment_method') or (service or {}).get('billing',''))
        start = modal.entry('Início (DD/MM/AAAA)',format_date_br(contract.start_date).replace('—',''))
        end = modal.entry('Término (DD/MM/AAAA)',format_date_br(contract.end_date).replace('—',''))
        due = modal.entry('Dia de vencimento (1 a 31)',str(contract.due_day or ''))
        status = modal.option('Situação comercial (controla vigência)',CONTRACT_STATUSES,contract.status)
        doc_status = modal.option('Situação do documento',DOCUMENT_STATUSES,data.get('document_status','Rascunho'))
        notes = modal.text('Observações',contract.notes,70)
        templates = {**{name:name+'\n\n'+BASE_TEMPLATE for name in TEMPLATE_NAMES},**{f"{t['name']} · #{t['id']}":t['content'] for t in self.crm.templates()}}
        template = modal.option('Modelo',list(templates),next(iter(templates)))
        content = modal.text('Conteúdo do contrato',data.get('content',contract.description),380)
        self._crm_text(modal.body,REVIEW_NOTICE)
        attachment = ctk.StringVar(value=contract.attachment_path)
        attachment_label = self._crm_text(modal.body,Path(attachment.get()).name if attachment.get() else 'Sem PDF anexado')

        def apply_template():
            if content.get('1.0','end').strip() and not messagebox.askyesno('Aplicar modelo','Substituir o texto não salvo pelo modelo selecionado?',parent=modal):
                return
            selected = services[service_menu.get()]
            values = variables(client,self._crm_provider_data(),selected,dict(title=title.get(),description=description.get('1.0','end').strip(),value_cents=parse_money_to_cents(value.get()),payment_method=payment.get(),start_date=parse_date_input(start.get()),end_date=parse_date_input(end.get())))
            content.delete('1.0','end')
            content.insert('1.0',fill_template(templates[template.get()],values))

        def attach():
            path = filedialog.askopenfilename(parent=modal,filetypes=[('PDF','*.pdf')])
            if path:
                attachment.set(path)
                attachment_label.configure(text=Path(path).name)

        if not locked:
            self._crm_button(modal.body,'Aplicar modelo com dados reais',lambda:self._crm_run(apply_template))
            self._crm_button(modal.body,'Anexar PDF existente',attach)
            self._crm_button(modal.body,'Remover anexo desta versão',lambda:(attachment.set(''),attachment_label.configure(text='Sem PDF anexado')))
        else:
            self._crm_text(modal.body,'Documento finalizado ou arquivado. Duplique para criar um novo rascunho; alterações nesta visualização não serão salvas.')
            content.configure(state='disabled')

        def save():
            selected = services[service_menu.get()]
            payload = replace(contract,title=title.get().strip(),description=description.get('1.0','end').strip(),value_cents=parse_money_to_cents(value.get()),
                              start_date=parse_date_input(start.get()),end_date=parse_date_input(end.get()),due_day=int(due.get()) if due.get().strip() else None,
                              status=status.get(),notes=notes.get('1.0','end').strip())
            self.db._validate_contract(payload)
            extra = dict(service_id=selected['id'] if selected else None,kind=kind.get(),content=content.get('1.0','end').strip(),document_status=doc_status.get(),billing=billing.get())
            extra['payment_method'] = payment.get().strip()
            extra['parties'] = variables(client,self._crm_provider_data(),selected,{**extra,'title':payload.title,'description':payload.description,'value_cents':payload.value_cents,'start_date':payload.start_date,'end_date':payload.end_date})
            if source=='ia' and doc_status.get()!='Rascunho':
                raise ValueError('Salve primeiro o rascunho gerado por IA para revisão.')
            imported = None
            if attachment.get() and (attachment.get()!=contract.attachment_path or contract.id is None):
                imported = self.db.import_contract_attachment(Path(attachment.get()),client.id)
            payload.attachment_path = imported or attachment.get()
            try:
                return self.crm.save_document(payload,extra,data.get('revision',0),source)
            except Exception:
                if imported:
                    self.db._delete_managed_attachment(imported)
                raise
        if not locked:
            modal.actions(lambda:self._crm_run(save,lambda:(modal.destroy(),self._open_client_profile(client,'Contratos'))))

    def _crm_document_state(self, client, doc):
        modal = FormModal(self,'Situação do contrato',500,320)
        state = modal.option('Ação',['Encerrado','Cancelado','Arquivado'],'Arquivado')
        self._crm_text(modal.body,'Encerrar/cancelar altera também a situação comercial. Arquivar apenas organiza a lista e preserva valores e histórico.')
        def save():
            if messagebox.askyesno('Confirmar',f"Aplicar {state.get()} ao contrato?",parent=modal):
                self._crm_run(lambda:self.crm.set_document_state(client.id,doc['id'],state.get()),lambda:(modal.destroy(),self._open_client_profile(client,'Contratos')))
        modal.actions(save)

    def _crm_delete_contract(self, client, contract):
        if messagebox.askyesno('Excluir rascunho','Excluir este rascunho e seu anexo? Contratos com financeiro ou finalizados devem ser arquivados.'):
            self._crm_run(lambda:self.db.delete_contract(contract.id),lambda:self._open_client_profile(client,'Contratos'))

    def _crm_versions(self, client, doc):
        modal = FormModal(self,'Versões do contrato',760,760)
        versions = self.crm.versions(client.id,doc['id'])
        if not versions:
            self._crm_text(modal.body,'Contrato anterior ao versionamento. A primeira edição preservará a versão original.')
        for version in versions:
            snapshot = json.loads(version['snapshot'])
            self._crm_text(modal.body,f"Versão {version['revision']} · {version['created_at']} UTC",True)
            self._crm_text(modal.body,snapshot.get('content') or snapshot.get('description') or 'Sem conteúdo textual.')

    def _crm_export_pdf(self, client, doc):
        def export():
            if '{{' in doc.get('content','') or '[Definir' in doc.get('content','') or '[Revisar' in doc.get('content',''):
                if not messagebox.askyesno('Campos a revisar','O contrato ainda contém campos ou condições a preencher. Gerar o PDF para revisão mesmo assim?'):
                    return
            directory = self.db.contracts_dir / str(client.id) / 'generated'
            printable = {**doc,'parties':doc.get('parties') or variables(client,self._crm_provider_data(),contract=doc)}
            path = generate_pdf(printable,directory)
            target = filedialog.asksaveasfilename(defaultextension='.pdf',filetypes=[('PDF','*.pdf')],initialfile=path.name)
            if target and Path(target).resolve()!=path.resolve():
                shutil.copy2(path,target)
            self._show_info('PDF gerado',f'Arquivo salvo em:\n{path}')
            self._open_contract_attachment(Contract(None,client.id,doc['title'],attachment_path=str(path)))
        self._crm_run(export)

    def _crm_copy_pdf(self, contract):
        target = filedialog.asksaveasfilename(defaultextension='.pdf',filetypes=[('PDF','*.pdf')],initialfile='contrato.pdf')
        if target:
            self._crm_run(lambda:shutil.copy2(contract.attachment_path,target),lambda:self._show_info('PDF','Cópia salva.'))

    def _crm_finance_tab(self, parent, client, finance, service=None):
        self._crm_text(parent,f"Cobrado: {format_money(finance['billed'])} · Recebido: {format_money(finance['received'])}\nPendente: {format_money(finance['pending'])} · Vencido: {format_money(finance['overdue'])}",True)
        next_payment = finance['next_payment']
        self._crm_text(parent,'Próximo pagamento: '+(f"{format_date_br(next_payment['due_date'])} · {next_payment['title']}" if next_payment else 'Nenhum'))
        self._crm_text(parent,'Controle manual. Nenhuma cobrança bancária é enviada; registre cada parcela ou competência uma única vez.')
        self._crm_button(parent,'Registrar cobrança / parcela',lambda:self._crm_charge_form(client,service),True)
        for charge in finance['charges']:
            box = self._crm_box(parent)
            balance = charge['amount_cents']-charge['received']
            status = 'Cancelada' if charge['cancelled'] else 'Recebida' if balance==0 else 'Vencida' if charge['due_date']<date.today().isoformat() else 'Pendente'
            self._crm_text(box,f"{charge['title']} · {status}",True)
            self._crm_text(box,f"Vencimento: {format_date_br(charge['due_date'])} · {charge['method']}\nValor: {format_money(charge['amount_cents'])} · Recebido: {format_money(charge['received'])} · Saldo: {format_money(balance)}\nServiço: #{charge['service_id'] or '—'} · Contrato: #{charge['contract_id'] or '—'}")
            if balance>0 and not charge['cancelled']:
                self._crm_button(box,'Registrar recebimento',lambda c=charge:self._crm_receipt_form(client,c))
            if not charge['cancelled'] and not charge['received']:
                self._crm_button(box,'Cancelar cobrança',lambda c=charge:self._crm_cancel_charge(client,c))
        self._crm_text(parent,'Histórico de recebimentos',True)
        for receipt in finance['receipts']:
            self._crm_text(parent,f"{format_date_br(receipt['paid_date'])} · {receipt['title']} · {format_money(receipt['amount_cents'])} · {receipt['method']}")

    def _crm_service_finance(self, client, service):
        modal = FormModal(self,'Financeiro do serviço: '+service['name'],760,760)
        self._crm_finance_tab(modal.body,client,self.crm.finance(client.id,service['id']),service)

    def _crm_charge_form(self, client, service=None):
        modal = FormModal(self,'Registrar cobrança',620,650)
        title = modal.entry('Descrição / competência')
        value = modal.entry('Valor')
        due = modal.entry('Vencimento (DD/MM/AAAA)')
        method = modal.entry('Forma de pagamento')
        services = {'Nenhum':None,**{f"{s['name']} · #{s['id']}":s['id'] for s in self.crm.services(client.id)}}
        selection = modal.option('Serviço',list(services),next((k for k,v in services.items() if service and v==service['id']),'Nenhum'))
        contracts = {'Nenhum':None,**{f'{c.title} · #{c.id}':c.id for c in self.db.list_contracts(client.id)}}
        contract = modal.option('Contrato',list(contracts),'Nenhum')
        operation_id = uuid.uuid4().hex
        def save():
            return self.crm.add_charge(client.id,title.get(),parse_money_to_cents(value.get()),parse_date_input(due.get(),required=True),method.get(),services[selection.get()],contracts[contract.get()],operation_id)
        modal.actions(lambda:self._crm_run(save,lambda:(modal.destroy(),self._open_client_profile(client,'Financeiro'))))

    def _crm_receipt_form(self, client, charge):
        modal = FormModal(self,'Registrar recebimento',500,440)
        value = modal.entry('Valor recebido',format_money(charge['amount_cents']-charge['received']))
        paid = modal.entry('Data do recebimento',format_date_br(date.today().isoformat()))
        method = modal.entry('Forma de pagamento',charge['method'])
        operation_id = uuid.uuid4().hex
        modal.actions(lambda:self._crm_run(lambda:self.crm.receive(client.id,charge['id'],parse_money_to_cents(value.get()),parse_date_input(paid.get(),required=True),method.get(),operation_id),lambda:(modal.destroy(),self._open_client_profile(client,'Financeiro'))))

    def _crm_cancel_charge(self, client, charge):
        if messagebox.askyesno('Cancelar cobrança','Cancelar a cobrança sem apagar seu histórico?'):
            self._crm_run(lambda:self.crm.cancel_charge(client.id,charge['id']),lambda:self._open_client_profile(client,'Financeiro'))

    def _crm_note(self, client):
        modal = FormModal(self,'Anotação interna',620,420)
        content = modal.text('Anotação','',220)
        modal.actions(lambda:self._crm_run(lambda:self.crm.add_note(client.id,content.get('1.0','end').strip()),lambda:(modal.destroy(),self._open_client_profile(client,'Histórico / Anotações'))))

    def _crm_ai_form(self, client):
        modal = FormModal(self,'Gerar rascunho com IA',700,800)
        self._crm_text(modal.body,REVIEW_NOTICE)
        self._crm_text(modal.body,'Escopo e condições abaixo serão enviados à API/IA. Não inclua CPF, endereço ou credenciais. Identificação das partes será preenchida localmente.')
        services = {'Sem serviço':None,**{f"{s['name']} · #{s['id']}":s for s in self.crm.services(client.id)}}
        selection = modal.option('Serviço',list(services),'Sem serviço')
        kind = modal.option('Tipo de contrato',TEMPLATE_NAMES,TEMPLATE_NAMES[0])
        scope = modal.text('Descrição / escopo','',120)
        fields = {key:modal.entry(label) for key,label in [('value','Valor'),('payment','Forma de pagamento'),('start','Início (DD/MM/AAAA)'),('end','Fim (DD/MM/AAAA)'),('deliveries','Quantidade de entregas'),('revisions','Política de alterações'),('cancel','Condições de cancelamento')]}
        extra = modal.text('Observações adicionais','',80)
        def autofill():
            service = services[selection.get()]
            if service:
                scope.delete('1.0','end'); scope.insert('1.0',service['scope'] or service['description'])
                for key,value in [('value',format_money(service['value_cents'])),('payment',service['billing']),('start',format_date_br(service['start_date']).replace('—','')),('end',format_date_br(service['end_date']).replace('—',''))]:
                    fields[key].delete(0,'end'); fields[key].insert(0,value)
        self._crm_button(modal.body,'Preencher com dados do serviço',autofill)
        feedback = self._crm_text(modal.body,'')
        result_queue = queue.Queue()

        def start():
            try:
                token = current_token()
                if not token:
                    raise ValueError('Entre na conta do aplicativo para usar a IA.')
                start_date = parse_date_input(fields['start'].get())
                end_date = parse_date_input(fields['end'].get())
                amount = parse_money_to_cents(fields['value'].get())
                selected_service = services[selection.get()]
                values = variables(client,self._crm_provider_data(),selected_service,dict(value_cents=amount,payment_method=fields['payment'].get(),start_date=start_date,end_date=end_date))
                conditions = '\n'.join(f'{key}: {widget.get()}' for key,widget in fields.items())+'\n'+extra.get('1.0','end').strip()
                payload = dict(kind=kind.get(),scope=scope.get('1.0','end').strip(),terms=conditions)
                for key in payload:
                    for placeholder,value in sorted(values.items(),key=lambda pair:len(str(pair[1])),reverse=True):
                        if placeholder in {'cliente_nome','cliente_documento','cliente_endereco','prestador_nome','prestador_documento'} and value:
                            payload[key] = payload[key].replace(str(value),'{{'+placeholder+'}}')
                if not payload['scope'] or len(payload['scope'])>6000 or len(payload['terms'])>6000:
                    raise ValueError('Preencha o escopo e limite escopo e condições a 6.000 caracteres cada.')
            except ValueError as exc:
                feedback.configure(text=str(exc))
                return
            button.configure(state='disabled')
            feedback.configure(text='Gerando rascunho… você pode fechar esta janela para descartar o resultado.')
            def worker():
                try:
                    response = requests.post(API_URL+'/v1/contracts/draft',headers={'Authorization':'Bearer '+token},json=payload,timeout=105)
                    body = response.json()
                    if not response.ok:
                        detail = body.get('detail') if isinstance(body,dict) else None
                        raise ValueError(detail if isinstance(detail,str) else 'Não foi possível gerar. Verifique os dados e tente novamente.')
                    if not isinstance(body,dict) or body.get('status')!='Rascunho' or not isinstance(body.get('content'),str) or not isinstance(body.get('title'),str):
                        raise ValueError('Resposta de IA inválida.')
                    result_queue.put((body,None))
                except (requests.RequestException,ValueError):
                    # Não revelar conteúdo de respostas, credenciais ou exceções de transporte.
                    result_queue.put((None,'Geração indisponível ou limite atingido. Confira a configuração da API ou utilize um modelo manual.'))
            threading.Thread(target=worker,daemon=True).start()
            def poll():
                if not modal.winfo_exists():
                    return
                try:
                    body,error = result_queue.get_nowait()
                except queue.Empty:
                    self.after(150,poll)
                    return
                button.configure(state='normal')
                if error:
                    feedback.configure(text=error)
                    return
                content = fill_template(body['content'],values)
                contract = Contract(None,client.id,body['title'],value_cents=amount,start_date=start_date,end_date=end_date)
                modal.destroy()
                self._open_contract_modal(client,contract,selected_service,dict(content=content,kind=payload['kind'],document_status='Rascunho'),source='ia')
            self.after(150,poll)
        button = self._crm_button(modal.body,'Gerar contrato',start,True)
