"""Interface da central local de clientes e contratos."""
from __future__ import annotations

import os
import uuid
from datetime import date
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
from .crm_view import CRMMixin


class ClientManagementMixin(CRMMixin):
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
            active_contracts = [item for item in contracts if contract_display_status(item.status, item.end_date) in {"Ativo", "Vence em breve"} and (not item.start_date or item.start_date <= date.today().isoformat())]
            revenue = sum(item.value_cents for item in active_contracts if client.status in {'Ativo','Recorrente'} and self.crm.document(client.id,item.id)['billing']=='Mensal')
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
