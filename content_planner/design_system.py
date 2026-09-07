"""Linguagem visual compartilhada do aplicativo desktop Vydra."""
from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk


COLORS = {
    "canvas": "#F8F8FB", "sidebar": "#FFFFFF", "sidebar_hover": "#EEEAFE",
    "sidebar_text": "#6E6E7A", "surface": "#FFFFFF", "surface_alt": "#F8F8FB",
    "border": "#E7E7EE", "border_strong": "#D1D1DC", "text": "#18181F",
    "muted": "#6E6E7A", "accent": "#6C5CE7", "accent_hover": "#5848D6",
    "selection": "#EEEAFE", "success": "#22A55A", "warning": "#A36812",
    "error": "#B93848", "secondary": "#FFFFFF", "secondary_hover": "#F1F0F7",
    "disabled": "#A5A5B0", "dark": "#18181F", "primary_soft": "#EEEAFE",
}

SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 40, "4xl": 48}
RADIUS = {"xs": 2, "sm": 4, "md": 6, "lg": 8}


def apply_theme() -> None:
    """Aplica o tema Vydra antes da criação das primeiras janelas."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    theme_path = root / "assets" / "neiva_light.json"
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme(str(theme_path) if theme_path.is_file() else "blue")


def font(size: int = 13, weight: str = "normal", *, heading: bool = False, mono: bool = False) -> ctk.CTkFont:
    family = "Cascadia Mono" if mono else ("Segoe UI Variable Display" if heading else "Segoe UI Variable")
    return ctk.CTkFont(family=family, size=size, weight=weight)


def primary_button(**overrides):
    values = {"height": 40, "corner_radius": RADIUS["xs"], "fg_color": COLORS["accent"],
              "hover_color": COLORS["accent_hover"], "text_color": "#FFFFFF", "font": font(12, "bold")}
    values.update(overrides)
    return values


def secondary_button(**overrides):
    values = {"height": 40, "corner_radius": RADIUS["xs"], "fg_color": COLORS["surface"],
              "hover_color": COLORS["secondary_hover"], "text_color": COLORS["text"],
              "border_width": 1, "border_color": COLORS["border_strong"], "font": font(12, "bold")}
    values.update(overrides)
    return values
