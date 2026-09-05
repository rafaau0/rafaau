"""Entrada e criação de contas rafaau, com painel deslizante nativo."""
from __future__ import annotations

import re
import secrets
import threading
from queue import Empty, Queue

import customtkinter as ctk
import requests

from .secrets import get_secret, set_secret
from .account_sessions import current_token, save_account
from .design_system import COLORS as UI, RADIUS, font, primary_button


API_URL = "https://neiva-ai-api.onrender.com"
def _device_id() -> str:
    value = get_secret("NEIVA_DEVICE_ID")
    if value:
        return value
    value = secrets.token_urlsafe(32)
    set_secret("NEIVA_DEVICE_ID", value)
    return value


def saved_session_is_valid() -> bool:
    token = current_token()
    if not token:
        return False
    try:
        response = requests.get(f"{API_URL}/v1/auth/session", headers={"Authorization": f"Bearer {token}"}, timeout=8)
        if not response.ok or not response.json().get("license_active"):
            return False
        data = response.json()
        if data.get("account"):
            save_account(data["account"], token)
        return True
    except requests.RequestException:
        return False


class LoginWindow(ctk.CTk):
    """Card de login/cadastro com o painel de marca animado sobre os formulários."""
    def __init__(self) -> None:
        super().__init__()
        self.authenticated = False
        self.showing_signup = False
        self._animating = False
        self._result_queue: Queue[tuple[str, str]] = Queue()
        self.title("rafaau | Entrar")
        self.geometry("760x680")
        self.minsize(620, 600)
        self.configure(fg_color=UI["canvas"])
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        ctk.set_appearance_mode("light")

        self.card = ctk.CTkFrame(self, width=520, fg_color=UI["surface"], corner_radius=RADIUS["lg"], border_width=1, border_color=UI["border"])
        self.card.place(relx=.5, rely=.5, anchor="center", relheight=.88)
        self.card.bind("<Configure>", lambda _event: self._resize_panels())
        self._build_forms()
        self._resize_panels()
        self.after(80, self._poll_results)
        self.after(150, self.login_email.focus_set)

    def _poll_results(self) -> None:
        """Atualiza o Tk apenas na thread principal; chamadas de rede rodam em segundo plano."""
        try:
            while True:
                action, value = self._result_queue.get_nowait()
                if action == "login_success" or action == "legacy_success":
                    self.authenticated = True
                    self.destroy()
                    return
                if action == "login_error":
                    self._show_login_error(value)
                    self.login_button.configure(state="normal", text="ENTRAR")
                elif action == "signup_success":
                    self._signup_success(value)
                elif action == "signup_error":
                    self.signup_error.configure(text=value)
                    self.signup_button.configure(state="normal", text="CRIAR CONTA")
        except Empty:
            pass
        if self.winfo_exists():
            self.after(80, self._poll_results)

    def _resize_panels(self) -> None:
        active = self.signup_form if self.showing_signup else self.login_form
        inactive = self.login_form if self.showing_signup else self.signup_form
        inactive.place_forget()
        active.place(relx=0, rely=0, relwidth=1, relheight=1)

    @staticmethod
    def _title(parent: ctk.CTkFrame, title: str, subtitle: str) -> None:
        ctk.CTkLabel(parent, text=title, text_color=UI["text"], font=ctk.CTkFont(family="Segoe UI", size=30, weight="bold")).pack(pady=(34, 4))
        ctk.CTkLabel(parent, text=subtitle, text_color=UI["muted"], font=ctk.CTkFont(size=13)).pack(pady=(0, 18))

    def _entry(self, parent: ctk.CTkFrame, label: str, placeholder: str, password: bool = False) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, text_color=UI["text"], anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", padx=46, pady=(6, 3))
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, show="●" if password else "", height=38, border_color=UI["border"], fg_color="#FFFFFF")
        entry.pack(fill="x", padx=46)
        return entry

    def _message(self, parent: ctk.CTkFrame) -> ctk.CTkLabel:
        label = ctk.CTkLabel(parent, text="", text_color=UI["error"], wraplength=320, justify="center", font=ctk.CTkFont(size=11))
        label.pack(padx=36, pady=(8, 0))
        return label

    def _build_forms(self) -> None:
        self.login_form = ctk.CTkFrame(self.card, fg_color=UI["surface"], corner_radius=0)
        self.signup_form = ctk.CTkFrame(self.card, fg_color=UI["surface"], corner_radius=0)
        self._title(self.login_form, "Entrar", "Acesse sua conta rafaau.")
        self.login_email = self._entry(self.login_form, "E-mail", "voce@empresa.com")
        self.login_password = self._entry(self.login_form, "Senha", "Sua senha", password=True)
        self.login_password.bind("<Return>", lambda _event: self._submit_login())
        self.login_error = self._message(self.login_form)
        self.login_button = ctk.CTkButton(self.login_form, text="ENTRAR", height=41, fg_color=UI["accent"], hover_color=UI["accent_hover"], command=self._submit_login)
        self.login_button.pack(fill="x", padx=46, pady=(8, 9))
        ctk.CTkButton(self.login_form, text="Criar uma conta", fg_color="transparent", hover=False,
                      text_color=UI["accent"], font=font(12, "bold"), command=self._toggle_slider).pack(pady=(0, 4))
        ctk.CTkButton(self.login_form, text="Tenho um código de ativação antigo", fg_color="transparent", hover=False, text_color=UI["muted"], font=ctk.CTkFont(size=11), command=self._show_legacy_prompt).pack(pady=(0, 18))

        self._title(self.signup_form, "Criar conta", "Comece organizando sua operação.")
        self.signup_name = self._entry(self.signup_form, "Nome", "Como podemos te chamar?")
        self.signup_email = self._entry(self.signup_form, "E-mail", "voce@empresa.com")
        self.signup_password = self._entry(self.signup_form, "Senha", "Mínimo de 8 caracteres", password=True)
        self.signup_password.bind("<Return>", lambda _event: self._submit_signup())
        self.signup_error = self._message(self.signup_form)
        self.signup_button = ctk.CTkButton(self.signup_form, text="CRIAR CONTA", height=41, fg_color=UI["accent"], hover_color=UI["accent_hover"], command=self._submit_signup)
        self.signup_button.pack(fill="x", padx=46, pady=(10, 8))
        ctk.CTkButton(self.signup_form, text="Voltar para o login", fg_color="transparent", hover=False,
                      text_color=UI["accent"], font=font(12, "bold"), command=self._toggle_slider).pack(pady=(0, 4))
        ctk.CTkLabel(self.signup_form, text="Sua conta começa no plano Grátis. Você pode fazer upgrade quando quiser.", text_color=UI["muted"], wraplength=300, justify="center", font=ctk.CTkFont(size=11)).pack(padx=35, pady=(0, 16))

    def _toggle_slider(self) -> None:
        self.showing_signup = not self.showing_signup
        self._resize_panels()
        (self.signup_name if self.showing_signup else self.login_email).focus_set()

    @staticmethod
    def _valid_email(email: str) -> bool:
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))

    def _show_login_error(self, message: str) -> None:
        self.login_error.configure(text=message)

    def _submit_login(self) -> None:
        email, password = self.login_email.get().strip().lower(), self.login_password.get()
        if not self._valid_email(email):
            self._show_login_error("Informe um e-mail válido.")
            return
        if not password:
            self._show_login_error("Informe sua senha.")
            return
        self.login_error.configure(text="Conectando...")
        self.login_button.configure(state="disabled", text="ENTRANDO...")
        threading.Thread(target=self._login_request, args=(email, password), daemon=True).start()

    def _login_request(self, email: str, password: str) -> None:
        try:
            response = requests.post(f"{API_URL}/v1/auth/app-login", json={"email": email, "password": password, "device_id": _device_id()}, timeout=20)
            if not response.ok:
                try: detail = response.json().get("detail", response.text)
                except ValueError: detail = response.text
                raise RuntimeError(detail or "Não foi possível entrar.")
            data = response.json()
            save_account(data["account"], data["access_token"])
            self._result_queue.put(("login_success", ""))
        except Exception as exc:
            self._result_queue.put(("login_error", str(exc)))

    def _submit_signup(self) -> None:
        name, email, password = self.signup_name.get().strip(), self.signup_email.get().strip().lower(), self.signup_password.get()
        if len(name) < 2: self.signup_error.configure(text="Informe seu nome."); return
        if not self._valid_email(email): self.signup_error.configure(text="Informe um e-mail válido."); return
        if len(password) < 8: self.signup_error.configure(text="A senha deve ter pelo menos 8 caracteres."); return
        self.signup_error.configure(text="Criando sua conta...")
        self.signup_button.configure(state="disabled", text="CRIANDO...")
        threading.Thread(target=self._signup_request, args=(name, email, password), daemon=True).start()

    def _signup_request(self, name: str, email: str, password: str) -> None:
        try:
            response = requests.post(f"{API_URL}/v1/auth/register", json={"name": name, "email": email, "password": password}, timeout=20)
            if not response.ok:
                try: detail = response.json().get("detail", response.text)
                except ValueError: detail = response.text
                raise RuntimeError(detail or "Não foi possível criar sua conta.")
            self._result_queue.put(("signup_success", email))
        except Exception as exc:
            self._result_queue.put(("signup_error", str(exc)))

    def _signup_success(self, email: str) -> None:
        self.signup_error.configure(text="Conta criada no plano Grátis. Entre para começar.", text_color="#168A5B")
        self.signup_button.configure(state="normal", text="ENTRAR NA MINHA CONTA", command=self._toggle_slider)
        self.login_email.delete(0, "end"); self.login_email.insert(0, email)

    def _show_legacy_prompt(self) -> None:
        dialog = ctk.CTkInputDialog(text="Informe seu código de ativação antigo:", title="Ativar código legado")
        code = dialog.get_input()
        if not code:
            return
        self.login_button.configure(state="disabled", text="ATIVANDO...")
        threading.Thread(target=self._legacy_request, args=(code.strip(),), daemon=True).start()

    def _legacy_request(self, code: str) -> None:
        try:
            response = requests.post(f"{API_URL}/v1/activate", json={"activation_code": code}, timeout=20)
            if not response.ok:
                try: detail = response.json().get("detail", response.text)
                except ValueError: detail = response.text
                raise RuntimeError(detail or "Não foi possível ativar o código.")
            set_secret("NEIVA_AI_CLIENT_TOKEN", response.json()["access_token"])
            self._result_queue.put(("legacy_success", ""))
        except Exception as exc:
            self._result_queue.put(("login_error", str(exc)))

    def _cancel(self) -> None:
        self.authenticated = False
        self.destroy()


def require_login(force: bool = False) -> bool:
    if not force and saved_session_is_valid():
        return True
    window = LoginWindow()
    window.mainloop()
    return window.authenticated
