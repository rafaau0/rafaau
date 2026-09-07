"""Modal reutilizável para formulários do aplicativo desktop."""
from __future__ import annotations

import customtkinter as ctk

from .design_system import COLORS as UI


class FormModal(ctk.CTkToplevel):
    def __init__(self, master: ctk.CTk, title: str, width: int, height: int) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=UI["canvas"])
        self.body = ctk.CTkScrollableFrame(self, fg_color=UI["canvas"])
        self.body.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(self.body, text=title, font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", pady=(0, 14))

    def entry(self, label: str, value: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(self.body, text=label, text_color=UI["text"]).pack(anchor="w", pady=(8, 4))
        entry = ctk.CTkEntry(self.body, height=38)
        entry.insert(0, value)
        entry.pack(fill="x")
        return entry

    def text(self, label: str, value: str = "", height: int = 100) -> ctk.CTkTextbox:
        ctk.CTkLabel(self.body, text=label, text_color=UI["text"]).pack(anchor="w", pady=(8, 4))
        textbox = ctk.CTkTextbox(self.body, height=height)
        textbox.insert("1.0", value)
        textbox.pack(fill="x")
        return textbox

    def option(self, label: str, values: list[str], value: str) -> ctk.CTkOptionMenu:
        ctk.CTkLabel(self.body, text=label, text_color=UI["text"]).pack(anchor="w", pady=(8, 4))
        option = ctk.CTkOptionMenu(self.body, values=values)
        option.set(value)
        option.pack(fill="x")
        return option

    def actions(self, save_command) -> None:
        actions = ctk.CTkFrame(self.body, fg_color="transparent")
        actions.pack(fill="x", pady=(18, 0))
        ctk.CTkButton(actions, text="Cancelar", fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(actions, text="Salvar", command=save_command).pack(side="right")
