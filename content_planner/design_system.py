"""Central visual language for the rafaau desktop application."""
from __future__ import annotations

import customtkinter as ctk


COLORS = {
    "canvas": "#F4F2ED", "sidebar": "#191919", "sidebar_hover": "#292929",
    "sidebar_text": "#A8A7A2", "surface": "#FFFFFF", "surface_alt": "#ECEAE5",
    "border": "#D8D5CE", "border_strong": "#B8B4AB", "text": "#181818",
    "muted": "#686761", "accent": "#E23A4A", "accent_hover": "#C92D3C",
    "selection": "#FBE8E9", "success": "#28765A", "warning": "#9A641D",
    "error": "#B52F3B", "secondary": "#ECEAE5", "secondary_hover": "#DFDCD5",
    "disabled": "#A8A59E",
}

SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 40, "4xl": 48}
RADIUS = {"xs": 4, "sm": 6, "md": 8, "lg": 10}


def font(size: int = 13, weight: str = "normal", *, heading: bool = False, mono: bool = False) -> ctk.CTkFont:
    family = "Cascadia Mono" if mono else ("Bahnschrift" if heading else "Segoe UI Variable")
    return ctk.CTkFont(family=family, size=size, weight=weight)


def primary_button(**overrides):
    values = {"height": 40, "corner_radius": RADIUS["sm"], "fg_color": COLORS["accent"],
              "hover_color": COLORS["accent_hover"], "text_color": "#FFFFFF", "font": font(12, "bold")}
    values.update(overrides)
    return values


def secondary_button(**overrides):
    values = {"height": 40, "corner_radius": RADIUS["sm"], "fg_color": COLORS["surface"],
              "hover_color": COLORS["secondary_hover"], "text_color": COLORS["text"],
              "border_width": 1, "border_color": COLORS["border_strong"], "font": font(12, "bold")}
    values.update(overrides)
    return values
