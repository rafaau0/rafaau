"""Interface da central local de clientes e contratos."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .client_management import (
    CLIENT_STATUSES,
    CONTRACT_STATUSES,
    contract_display_status,
    format_date_br,
    format_money,
    parse_date_input,
    parse_money_to_cents,
)
from .database import Client, Contract
from .design_system import COLORS as UI, RADIUS, font, secondary_button
from .form_modal import FormModal


class ClientManagementMixin:
    """Telas de cadastro, perfil e contratos usadas pelo aplicativo principal."""

    def show_clients(self) -> None:
        frame = self._set_active_view("Clientes", "Gestão de clientes", "Cadastros, contatos, contratos e histórico comercial em um só lugar.")
        stats = self.db.dashboard_stats()
        summary = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=RADIUS["md"], border_width=1, border_color=UI["border"])
        summary.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        for index in range(5):
            summary.grid_columnconfigure(index, weight=1)
        for col, (label, value, color) in enumerate([
            ("Clientes", stats["clients"], UI["text"]),
            ("Contratos ativos", stats["active_contracts"], UI["success"]),
            ("Vencem em 30 dias", stats["expiring_contracts"], UI["warning"]),
            ("Vencidos", stats["expired_contracts"], UI["error"]),
            ("Receita mensal", format_money(stats["monthly_revenue_cents"]), UI["accent"]),
        ]):
            box = ctk.CTkFrame(summary, fg_color="transparent")
            box.grid(row=0, column=col, sticky="ew", padx=14, pady=14)
            ctk.CTkLabel(box, text=label.upper(), text_color=UI["muted"], font=font(9, "bold")).pack(anchor="w")
            ctk.CTkLabel(box, text=str(value), text_color=color, font=font(23, "bold", heading=True)).pack(anchor="w", pady=(3, 0))

        toolbar = ctk.CTkFrame(frame, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        toolbar.grid_columnconfigure(0, weight=1)

        search = ctk.CTkEntry(toolbar, placeholder_text="Pesquisar nome, empresa, documento, contato ou Instagram")
        search.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        status = ctk.CTkOptionMenu(toolbar, values=["Todos", *CLIENT_STATUSES], width=120)
        status.set("Todos")
        status.grid(row=0, column=1, padx=(0, 12))
        ctk.CTkButton(
            toolbar,
            text="Pesquisar",
            width=120,
            command=lambda: self._render_clients_list(list_frame, search.get(), "" if status.get() == "Todos" else status.get()),
        ).grid(row=0, column=2, padx=(0, 12))
        ctk.CTkButton(toolbar, text="Novo cliente", width=140, command=self._open_client_modal).grid(row=0, column=3)

        list_frame = ctk.CTkFrame(frame, fg_color="transparent")
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        self._render_clients_list(list_frame)

    def _render_clients_list(self, parent: ctk.CTkFrame, term: str = "", status: str = "") -> None:
        for child in parent.winfo_children():
            child.destroy()

        clients = self.db.search_clients(term, status)
        if not clients:
            ctk.CTkLabel(parent, text="Nenhum cliente encontrado.", text_color=UI["muted"]).grid(row=0, column=0, sticky="w", pady=20)
            return

        for row, client in enumerate(clients):
            contracts = self.db.list_contracts(client.id) if client.id else []
            active_contracts = [item for item in contracts if contract_display_status(item.status, item.end_date) in {"Ativo", "Vence em breve"}]
            revenue = sum(item.value_cents for item in active_contracts)
            item = ctk.CTkFrame(parent, fg_color=UI["surface"], corner_radius=RADIUS["md"], border_width=1, border_color=UI["border"])
            item.grid(row=row, column=0, sticky="ew", pady=6)
            item.grid_columnconfigure(0, weight=1)
            title = client.name + (f" · {client.company_name}" if client.company_name else "")
            ctk.CTkLabel(item, text=title, font=ctk.CTkFont(size=17, weight="bold")).grid(
                row=0, column=0, sticky="w", padx=16, pady=(12, 0)
            )
            ctk.CTkLabel(
                item,
                text="  ·  ".join(value for value in (client.email, client.phone, client.instagram, client.niche) if value) or "Cadastro sem informações de contato",
                text_color=UI["muted"],
            ).grid(row=1, column=0, sticky="w", padx=16, pady=(2, 12))
            ctk.CTkLabel(
                item,
                text=f"{client.status}  ·  {len(active_contracts)} contrato(s) ativo(s)  ·  {format_money(revenue)}/mês",
                text_color=UI["success"] if client.status == "Ativo" else UI["muted"],
                font=font(11, "bold"),
            ).grid(row=0, column=1, rowspan=2, padx=12, pady=12)
            ctk.CTkButton(item, text="Planejamento", width=110, command=lambda c=client: self._select_client_calendar(c)).grid(
                row=0, column=2, rowspan=2, padx=(0, 8), pady=12
            )
            ctk.CTkButton(
                item,
                text="Abrir cliente",
                width=115,
                fg_color=UI["secondary"],
                hover_color=UI["secondary_hover"],
                text_color=UI["text"],
                command=lambda c=client: self._open_client_profile(c),
            ).grid(row=0, column=3, rowspan=2, padx=(0, 16), pady=12)

    def _open_client_modal(self, client: Client | None = None) -> None:
        if client is None and self.plan.max_clients is not None and len(self.db.search_clients()) >= self.plan.max_clients:
            self._show_warning("Limite do plano", f"O plano {self.plan.name} permite até {self.plan.max_clients} cliente. Faça upgrade para cadastrar mais.")
            return
        modal = FormModal(self, "Cadastro do cliente", width=680, height=780)
        fields = {
            "name": modal.entry("Nome", client.name if client else ""),
            "company_name": modal.entry("Empresa / razão social", client.company_name if client else ""),
            "document": modal.entry("CPF ou CNPJ", client.document if client else ""),
            "contact_name": modal.entry("Pessoa de contato", client.contact_name if client else ""),
            "email": modal.entry("E-mail", client.email if client else ""),
            "phone": modal.entry("Telefone / WhatsApp", client.phone if client else ""),
            "address": modal.entry("Endereço", client.address if client else ""),
            "niche": modal.entry("Nicho", client.niche if client else ""),
            "instagram": modal.entry("Instagram", client.instagram if client else ""),
            "posting_frequency": modal.entry("Frequência de postagem", client.posting_frequency if client else ""),
            "status": modal.option("Situação do cliente", CLIENT_STATUSES, client.status if client else "Ativo"),
            "objective": modal.text("Objetivo", client.objective if client else "", height=90),
            "notes": modal.text("Observações", client.notes if client else "", height=120),
        }
        operation_id = uuid.uuid4().hex

        def save() -> None:
            if not fields["name"].get().strip():
                self._show_warning("Validação", "Nome é obrigatório.")
                return
            payload = Client(
                id=client.id if client else None,
                name=fields["name"].get(),
                niche=fields["niche"].get(),
                instagram=fields["instagram"].get(),
                posting_frequency=fields["posting_frequency"].get(),
                objective=fields["objective"].get("1.0", "end").strip(),
                notes=fields["notes"].get("1.0", "end").strip(),
                operation_id=client.operation_id if client else operation_id,
                company_name=fields["company_name"].get(),
                document=fields["document"].get(),
                email=fields["email"].get(),
                phone=fields["phone"].get(),
                address=fields["address"].get(),
                contact_name=fields["contact_name"].get(),
                status=fields["status"].get(),
            )
            if client:
                self.db.update_client(payload)
            else:
                self.selected_client_id = self.db.create_client(payload)
            modal.destroy()
            self._refresh_active_view()

        modal.actions(save)

    def _open_client_profile(self, client: Client) -> None:
        if client.id is None:
            return
        fresh = self.db.get_client(client.id)
        if fresh is None:
            self._show_warning("Cliente", "Este cliente não existe mais.")
            self.show_clients()
            return
        modal = FormModal(self, fresh.name, width=860, height=760)

        status_color = UI["success"] if fresh.status == "Ativo" else UI["muted"]
        ctk.CTkLabel(modal.body, text=fresh.status.upper(), text_color=status_color, font=font(10, "bold")).pack(anchor="w", pady=(0, 12))
        info = ctk.CTkFrame(modal.body, fg_color=UI["surface"], corner_radius=RADIUS["md"], border_width=1, border_color=UI["border"])
        info.pack(fill="x", pady=(0, 14))
        details = [
            ("Empresa", fresh.company_name), ("CPF / CNPJ", fresh.document),
            ("Contato", fresh.contact_name), ("E-mail", fresh.email),
            ("Telefone", fresh.phone), ("Endereço", fresh.address),
            ("Nicho", fresh.niche), ("Instagram", fresh.instagram),
            ("Frequência", fresh.posting_frequency),
        ]
        for index, (label, value) in enumerate(details):
            row, column = divmod(index, 2)
            info.grid_columnconfigure(column, weight=1)
            cell = ctk.CTkFrame(info, fg_color="transparent")
            cell.grid(row=row, column=column, sticky="ew", padx=16, pady=10)
            ctk.CTkLabel(cell, text=label.upper(), text_color=UI["muted"], font=font(9, "bold")).pack(anchor="w")
            ctk.CTkLabel(cell, text=value or "—", text_color=UI["text"], font=font(12), wraplength=350, justify="left").pack(anchor="w", pady=(2, 0))

        if fresh.objective or fresh.notes:
            ctk.CTkLabel(
                modal.body,
                text="\n".join(part for part in (f"Objetivo: {fresh.objective}" if fresh.objective else "", f"Observações: {fresh.notes}" if fresh.notes else "") if part),
                text_color=UI["muted"], justify="left", wraplength=780,
            ).pack(anchor="w", pady=(0, 14))

        header = ctk.CTkFrame(modal.body, fg_color="transparent")
        header.pack(fill="x", pady=(6, 8))
        ctk.CTkLabel(header, text="CONTRATOS", text_color=UI["text"], font=font(13, "bold")).pack(side="left")
        ctk.CTkButton(
            header, text="Novo contrato", width=130,
            command=lambda: (modal.destroy(), self._open_contract_modal(fresh)),
        ).pack(side="right")

        contracts = self.db.list_contracts(fresh.id)
        if not contracts:
            ctk.CTkLabel(modal.body, text="Nenhum contrato cadastrado.", text_color=UI["muted"]).pack(anchor="w", pady=12)
        for contract in contracts:
            display_status = contract_display_status(contract.status, contract.end_date)
            contract_box = ctk.CTkFrame(modal.body, fg_color=UI["surface"], corner_radius=RADIUS["md"], border_width=1, border_color=UI["border"])
            contract_box.pack(fill="x", pady=5)
            contract_box.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(contract_box, text=contract.title, text_color=UI["text"], font=font(14, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 2))
            ctk.CTkLabel(
                contract_box,
                text=f"{format_money(contract.value_cents)}/mês  ·  {format_date_br(contract.start_date)} até {format_date_br(contract.end_date)}  ·  {display_status}",
                text_color=UI["warning"] if display_status in {"Vencido", "Vence em breve"} else UI["muted"],
                font=font(11, "bold"),
            ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
            actions = ctk.CTkFrame(contract_box, fg_color="transparent")
            actions.grid(row=0, column=1, rowspan=2, padx=10, pady=8)
            if contract.attachment_path:
                ctk.CTkButton(actions, text="Abrir PDF", width=88, command=lambda c=contract: self._open_contract_attachment(c), **secondary_button()).pack(side="left", padx=3)
            ctk.CTkButton(actions, text="Editar", width=78, command=lambda c=contract: (modal.destroy(), self._open_contract_modal(fresh, c)), **secondary_button()).pack(side="left", padx=3)
            ctk.CTkButton(actions, text="Excluir", width=78, fg_color=UI["error"], hover_color="#972C3A", command=lambda c=contract: self._delete_contract(c, modal)).pack(side="left", padx=3)

        footer = ctk.CTkFrame(modal.body, fg_color="transparent")
        footer.pack(fill="x", pady=(18, 0))
        ctk.CTkButton(footer, text="Excluir cliente", width=120, fg_color=UI["error"], hover_color="#972C3A", command=lambda: (modal.destroy(), self._delete_client(fresh))).pack(side="left")
        ctk.CTkButton(footer, text="Fechar", width=100, command=modal.destroy, **secondary_button()).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Editar cadastro", width=130, command=lambda: (modal.destroy(), self._open_client_modal(fresh))).pack(side="right")

    def _open_contract_modal(self, client: Client, contract: Contract | None = None) -> None:
        if client.id is None:
            return
        modal = FormModal(self, "Contrato", width=680, height=760)
        title = modal.entry("Título do contrato", contract.title if contract else "Prestação de serviços")
        description = modal.text("Descrição / escopo", contract.description if contract else "", height=90)
        value = modal.entry("Valor mensal", format_money(contract.value_cents) if contract else "")
        start_date = modal.entry("Data de início (DD/MM/AAAA)", format_date_br(contract.start_date) if contract else "")
        end_date = modal.entry("Data final (DD/MM/AAAA)", format_date_br(contract.end_date) if contract else "")
        due_day = modal.entry("Dia de vencimento (1 a 31)", str(contract.due_day) if contract and contract.due_day else "")
        status = modal.option("Situação", CONTRACT_STATUSES, contract.status if contract else "Rascunho")
        notes = modal.text("Observações", contract.notes if contract else "", height=80)
        attachment = ctk.StringVar(value=contract.attachment_path if contract else "")
        attachment_label = ctk.CTkLabel(modal.body, text=Path(attachment.get()).name if attachment.get() else "Nenhum PDF anexado", text_color=UI["muted"])
        attachment_label.pack(anchor="w", pady=(12, 4))
        attachment_actions = ctk.CTkFrame(modal.body, fg_color="transparent")
        attachment_actions.pack(fill="x")

        def select_attachment() -> None:
            selected = filedialog.askopenfilename(parent=modal, title="Selecionar contrato", filetypes=[("Documento PDF", "*.pdf")])
            if selected:
                attachment.set(selected)
                attachment_label.configure(text=Path(selected).name)

        def remove_attachment() -> None:
            attachment.set("")
            attachment_label.configure(text="Nenhum PDF anexado")

        ctk.CTkButton(attachment_actions, text="Selecionar PDF", width=120, command=select_attachment, **secondary_button()).pack(side="left")
        ctk.CTkButton(attachment_actions, text="Remover anexo", width=120, command=remove_attachment, **secondary_button()).pack(side="left", padx=8)
        operation_id = uuid.uuid4().hex

        def save() -> None:
            imported_path = attachment.get()
            try:
                if not title.get().strip():
                    raise ValueError("O título do contrato é obrigatório.")
                parsed_start = parse_date_input(start_date.get())
                parsed_end = parse_date_input(end_date.get())
                parsed_due_day = int(due_day.get()) if due_day.get().strip() else None
                if parsed_due_day is not None and not 1 <= parsed_due_day <= 31:
                    raise ValueError("O dia de vencimento deve estar entre 1 e 31.")
                if parsed_start and parsed_end and parsed_end < parsed_start:
                    raise ValueError("A data final não pode ser anterior à data inicial.")
                value_cents = parse_money_to_cents(value.get())
                if imported_path and imported_path != (contract.attachment_path if contract else ""):
                    imported_path = self.db.import_contract_attachment(Path(imported_path), client.id)
                payload = Contract(
                    id=contract.id if contract else None,
                    client_id=client.id,
                    title=title.get(),
                    description=description.get("1.0", "end").strip(),
                    value_cents=value_cents,
                    start_date=parsed_start,
                    end_date=parsed_end,
                    due_day=parsed_due_day,
                    status=status.get(),
                    attachment_path=imported_path,
                    notes=notes.get("1.0", "end").strip(),
                    operation_id=contract.operation_id if contract else operation_id,
                )
                if contract:
                    self.db.update_contract(payload)
                else:
                    self.db.create_contract(payload)
            except (OSError, ValueError) as exc:
                self._show_warning("Contrato", str(exc))
                return
            modal.destroy()
            self.show_clients()

        modal.actions(save)

    def _open_contract_attachment(self, contract: Contract) -> None:
        path = Path(contract.attachment_path)
        if not path.is_file():
            self._show_warning("Contrato", "O PDF anexado não foi encontrado neste computador.")
            return
        try:
            startfile = getattr(os, "startfile")
            startfile(str(path))
        except (AttributeError, OSError) as exc:
            self._show_error("Contrato", f"Não foi possível abrir o PDF: {exc}")

    def _delete_contract(self, contract: Contract, modal: ctk.CTkToplevel) -> None:
        if contract.id is None:
            return
        if messagebox.askyesno("Excluir contrato", f"Excluir o contrato '{contract.title}' e seu PDF anexado?", parent=modal):
            self.db.delete_contract(contract.id)
            modal.destroy()
            self.show_clients()
