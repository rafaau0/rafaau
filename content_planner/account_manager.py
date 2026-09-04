"""Janela compacta para alternar e remover contas deste computador."""
from __future__ import annotations

from collections.abc import Callable
import customtkinter as ctk
from tkinter import messagebox

from .account_sessions import activate_account, current_account, remove_account, saved_accounts
from .design_system import COLORS as UI, RADIUS, font, primary_button, secondary_button


class AccountManagerDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_restart: Callable[[str], None]) -> None:
        super().__init__(parent)
        self._on_restart = on_restart
        self.title("Contas neste computador")
        self.geometry("520x520")
        self.minsize(460, 420)
        self.configure(fg_color=UI["canvas"])
        self.transient(parent)
        self.grab_set()
        self.after(80, self.focus_force)
        self._render()

    def _render(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        ctk.CTkLabel(self, text="Suas contas", font=font(27, "bold", heading=True)).pack(anchor="w", padx=24, pady=(24, 3))
        ctk.CTkLabel(self, text="Alterne de perfil sem informar a senha novamente.", text_color="#68707D").pack(anchor="w", padx=24, pady=(0, 16))
        current = current_account()
        accounts_frame = ctk.CTkScrollableFrame(self, fg_color=UI["surface"], corner_radius=RADIUS["md"], border_width=1, border_color=UI["border"])
        accounts_frame.pack(fill="both", expand=True, padx=24)
        for account in saved_accounts():
            row = ctk.CTkFrame(accounts_frame, fg_color="transparent", corner_radius=0)
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=account.name, font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(11, 1))
            detail = account.email + (f"  ·  Plano {account.plan.title()}" if account.plan else "")
            ctk.CTkLabel(row, text=detail, text_color="#68707D", font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 11))
            if current and current.account_id == account.account_id:
                ctk.CTkLabel(row, text="● Em uso", text_color="#168A5B", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, rowspan=2, padx=14)
            else:
                ctk.CTkButton(row, text="Usar", width=70, command=lambda value=account.account_id: self._switch(value)).grid(row=0, column=1, rowspan=2, padx=(4, 6))
                ctk.CTkButton(row, text="×", width=34, fg_color="transparent", hover_color="#FFF0F2", text_color="#C92A3D", command=lambda value=account.account_id: self._remove(value)).grid(row=0, column=2, rowspan=2, padx=(0, 8))
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=20)
        ctk.CTkButton(actions, text="ADICIONAR OUTRA CONTA", command=lambda: self._restart("add"), **primary_button()).pack(side="left")
        if current:
            ctk.CTkButton(actions, text="Sair desta conta", fg_color="#E7EAF0", hover_color="#D8DDE5", text_color="#17191F", command=lambda: self._logout(current.account_id)).pack(side="right")

    def _switch(self, account_id: str) -> None:
        activate_account(account_id)
        self._restart("switch")

    def _remove(self, account_id: str) -> None:
        if not messagebox.askyesno("Remover conta", "Remover esta conta salva deste computador?", parent=self):
            return
        remove_account(account_id)
        self._render()

    def _logout(self, account_id: str) -> None:
        if not messagebox.askyesno("Sair da conta", "Sair desta conta neste computador? As outras contas continuarão salvas.", parent=self):
            return
        remove_account(account_id)
        self._restart("logout")

    def _restart(self, action: str) -> None:
        self.grab_release()
        self.destroy()
        self._on_restart(action)
