"""Janela externa usada pelo comando do DaVinci Resolve gratuito."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import customtkinter as ctk

from .design_system import COLORS, RADIUS, SPACE, font, primary_button, secondary_button


def _result_path(request_path: Path) -> Path:
    return request_path.with_suffix(".result.json")


def _write_result(request_path: Path, approved: bool, error: str | None = None) -> None:
    result_path = _result_path(request_path)
    temporary = result_path.with_suffix(".json.tmp")
    payload: dict[str, Any] = {"ok": error is None, "approved": bool(approved)}
    if error:
        payload["error"] = error
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(result_path)


class DavinciDialog(ctk.CTk):
    def __init__(self, request_path: Path, request: dict[str, Any]) -> None:
        super().__init__(fg_color=COLORS["canvas"])
        self.request_path = request_path
        self.finished = False
        self.kind = str(request.get("kind", "info"))

        self.title(str(request.get("title") or "rafaau"))
        self.geometry("620x440")
        self.minsize(540, 360)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: self.finish(False))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color=COLORS["sidebar"], corner_radius=0, height=76)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(
            header,
            text="rafaau.",
            text_color="#FFFFFF",
            font=font(25, "bold", heading=True),
        ).pack(side="left", padx=SPACE["xl"], pady=SPACE["lg"])
        ctk.CTkLabel(
            header,
            text="DAVINCI RESOLVE",
            text_color=COLORS["sidebar_text"],
            font=font(11, "bold"),
        ).pack(side="right", padx=SPACE["xl"])

        body = ctk.CTkFrame(
            self,
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RADIUS["lg"],
        )
        body.grid(row=1, column=0, sticky="nsew", padx=SPACE["xl"], pady=SPACE["xl"])
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        color = {
            "error": COLORS["error"],
            "confirm": COLORS["accent"],
        }.get(self.kind, COLORS["success"])
        heading = {
            "error": "Algo não saiu como esperado",
            "confirm": "Confirme para continuar",
        }.get(self.kind, "Informação")
        ctk.CTkLabel(
            body,
            text=heading,
            text_color=color,
            font=font(17, "bold", heading=True),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=SPACE["xl"], pady=(SPACE["xl"], SPACE["md"]))
        ctk.CTkLabel(
            body,
            text=str(request.get("message") or ""),
            text_color=COLORS["text"],
            font=font(13),
            justify="left",
            anchor="nw",
            wraplength=530,
        ).grid(row=1, column=0, sticky="nsew", padx=SPACE["xl"])

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="e", padx=SPACE["xl"], pady=SPACE["xl"])
        if self.kind == "confirm":
            ctk.CTkButton(
                actions,
                text=str(request.get("cancel_text") or "CANCELAR"),
                command=lambda: self.finish(False),
                **secondary_button(width=120),
            ).pack(side="left", padx=(0, SPACE["sm"]))
            ctk.CTkButton(
                actions,
                text=str(request.get("confirm_text") or "CONTINUAR"),
                command=lambda: self.finish(True),
                **primary_button(width=130),
            ).pack(side="left")
        else:
            ctk.CTkButton(
                actions,
                text="OK",
                command=lambda: self.finish(True),
                **primary_button(width=110),
            ).pack(side="left")

        self.bind("<Escape>", lambda _event: self.finish(False))
        self.bind("<Return>", lambda _event: self.finish(True))
        self.after(10, self._position_and_focus)

    def _position_and_focus(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.after(500, lambda: self.attributes("-topmost", False))

    def finish(self, approved: bool) -> None:
        if self.finished:
            return
        self.finished = True
        _write_result(self.request_path, approved)
        self.destroy()


def run_dialog(request_path: Path) -> int:
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise ValueError("Solicitação de janela inválida.")
        ctk.set_appearance_mode("light")
        DavinciDialog(request_path, request).mainloop()
        return 0
    except Exception as exc:
        try:
            _write_result(request_path, False, str(exc))
        except OSError:
            pass
        return 1
