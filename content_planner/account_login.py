"""Tela de entrada da conta Neiva antes de abrir o Planner."""
from __future__ import annotations

import secrets
import threading
import webbrowser

import customtkinter as ctk
import requests

from .secrets import get_secret, set_secret


API_URL = "https://neiva-ai-api.onrender.com"
SITE_URL = "https://rafaau.site"
ACCENT = "#FF263D"


def _device_id() -> str:
    value = get_secret("NEIVA_DEVICE_ID")
    if value:
        return value
    value = secrets.token_urlsafe(32)
    set_secret("NEIVA_DEVICE_ID", value)
    return value


def saved_session_is_valid() -> bool:
    token = get_secret("NEIVA_AI_CLIENT_TOKEN")
    if not token:
        return False
    try:
        response = requests.get(f"{API_URL}/v1/auth/session", headers={"Authorization": f"Bearer {token}"}, timeout=8)
        return response.ok and bool(response.json().get("license_active"))
    except requests.RequestException:
        return False


class LoginWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.authenticated = False
        self.title("Entrar - Neiva Planner")
        self.geometry("460x500")
        self.resizable(False, False)
        self.configure(fg_color="#F7F8FA")
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        card = ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=14, border_width=1, border_color="#DDE1E7")
        card.pack(fill="both", expand=True, padx=28, pady=28)
        ctk.CTkLabel(card, text="NEIVA PLANNER", font=ctk.CTkFont(family="Segoe UI", size=23, weight="bold"), text_color="#17191F").pack(pady=(34, 7))
        ctk.CTkLabel(card, text="Entre com a conta vinculada à sua assinatura.", text_color="#68707D").pack(pady=(0, 24))

        ctk.CTkLabel(card, text="E-mail", anchor="w").pack(fill="x", padx=32)
        self.email = ctk.CTkEntry(card, placeholder_text="voce@empresa.com", height=40)
        self.email.pack(fill="x", padx=32, pady=(5, 14))
        ctk.CTkLabel(card, text="Senha", anchor="w").pack(fill="x", padx=32)
        self.password = ctk.CTkEntry(card, placeholder_text="Sua senha", show="●", height=40)
        self.password.pack(fill="x", padx=32, pady=(5, 10))
        self.password.bind("<Return>", lambda _event: self._submit())
        self.activation_code = ctk.CTkEntry(card, placeholder_text="Codigo de ativacao antigo", show="●", height=40)
        self.message = ctk.CTkLabel(card, text="", text_color="#C92A3D", wraplength=350, justify="center")
        self.message.pack(padx=25, pady=(0, 8))
        self.submit = ctk.CTkButton(card, text="ENTRAR NO PLANNER", fg_color=ACCENT, hover_color="#D91E32", height=42, command=self._submit)
        self.submit.pack(fill="x", padx=32, pady=(4, 12))
        self.legacy_button = ctk.CTkButton(card, text="Tenho um codigo de ativacao antigo", fg_color="transparent", text_color="#68707D", hover=False, command=self._show_legacy_activation)
        self.legacy_button.pack()
        self.activate_legacy_button = ctk.CTkButton(card, text="ATIVAR CODIGO", fg_color=ACCENT, hover_color="#D91E32", height=40, command=self._activate_legacy)
        ctk.CTkButton(card, text="Ainda não tenho conta", fg_color="transparent", text_color=ACCENT, hover=False, command=lambda: webbrowser.open(SITE_URL)).pack()
        ctk.CTkLabel(card, text="Crie sua conta ao assinar no site.", text_color="#68707D", font=ctk.CTkFont(size=11)).pack(pady=(4, 20))
        self.after(150, self.email.focus_set)

    def _cancel(self) -> None:
        self.authenticated = False
        self.destroy()

    def _submit(self) -> None:
        email, password = self.email.get().strip(), self.password.get()
        if not email or not password:
            self.message.configure(text="Informe seu e-mail e senha.")
            return
        self.message.configure(text="")
        self.submit.configure(state="disabled", text="ENTRANDO...")
        threading.Thread(target=self._login, args=(email, password), daemon=True).start()

    def _show_legacy_activation(self) -> None:
        """Transicao para quem comprou antes de existir conta e senha."""
        self.email.pack_forget()
        self.password.pack_forget()
        self.submit.pack_forget()
        self.legacy_button.pack_forget()
        self.activation_code.pack(fill="x", padx=32, pady=(5, 12))
        self.activate_legacy_button.pack(fill="x", padx=32, pady=(4, 12))
        self.activation_code.focus_set()

    def _activate_legacy(self) -> None:
        code = self.activation_code.get().strip()
        if not code:
            self.message.configure(text="Informe o codigo de ativacao.")
            return
        self.message.configure(text="")
        self.activate_legacy_button.configure(state="disabled", text="ATIVANDO...")
        threading.Thread(target=self._activate_legacy_request, args=(code,), daemon=True).start()

    def _activate_legacy_request(self, code: str) -> None:
        try:
            response = requests.post(f"{API_URL}/v1/activate", json={"activation_code": code}, timeout=20)
            if not response.ok:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                raise RuntimeError(detail or "Nao foi possivel ativar o codigo.")
            set_secret("NEIVA_AI_CLIENT_TOKEN", response.json()["access_token"])
            self.authenticated = True
            self.after(0, self.destroy)
        except Exception as exc:
            self.after(0, lambda: (self.message.configure(text=str(exc)), self.activate_legacy_button.configure(state="normal", text="ATIVAR CODIGO")))

    def _login(self, email: str, password: str) -> None:
        try:
            response = requests.post(
                f"{API_URL}/v1/auth/app-login",
                json={"email": email, "password": password, "device_id": _device_id()},
                timeout=20,
            )
            if not response.ok:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                raise RuntimeError(detail or "Nao foi possivel entrar.")
            data = response.json()
            set_secret("NEIVA_AI_CLIENT_TOKEN", data["access_token"])
            set_secret("NEIVA_ACCOUNT_EMAIL", email)
            self.authenticated = True
            self.after(0, self.destroy)
        except Exception as exc:
            self.after(0, lambda: (self.message.configure(text=str(exc)), self.submit.configure(state="normal", text="ENTRAR NO PLANNER")))


def require_login() -> bool:
    """Permite abrir o programa apenas com uma sessao/licenca valida."""
    if saved_session_is_valid():
        return True
    window = LoginWindow()
    window.mainloop()
    return window.authenticated
