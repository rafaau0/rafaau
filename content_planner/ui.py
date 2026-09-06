from __future__ import annotations

import calendar
import copy
import hashlib
import json
import os
import sys
import webbrowser
import threading
import uuid
from datetime import date, datetime
from pathlib import Path
from tkinter import DoubleVar, IntVar, TclError, filedialog, messagebox, ttk

import customtkinter as ctk
import requests
from PIL import Image

from .database import Client, Database, Post
from .pdf_generator import PDFGenerator
from .trello_api import TrelloAPI, TrelloConfig
from .trello_auth import TrelloBoard, authorize as authorize_trello, get_app_key as get_trello_app_key, get_identity as get_trello_identity, list_boards as list_trello_boards
from .video_subtitles import VideoError, VideoProject, probe, render, transcribe, write_captions
from .youtube_downloader import DownloadError, download as download_youtube, duration as youtube_duration, fetch_info, is_youtube_url
from .clip_finder import ClipSuggestion, find_suggestions
from .clip_ai import analyze_cuts
from .video_editor import find_davinci, launch_davinci, validate_davinci_executable
from .davinci_integration import install_integration, integration_status
from .secrets import get_secret, set_secret
from .account_manager import AccountManagerDialog
from .account_sessions import account_secret_key, current_account
from .plan_rules import current_plan_rules
from .silence_editor import SilenceSettings, apply_cuts, detect_silences, output_segments, plan_cuts, remap_subtitles
from .paths import EXPORTS_DIR
from .design_system import COLORS as UI, RADIUS, font, primary_button, secondary_button


CONTENT_TYPES = ["Reels", "Story", "Carrossel", "Feed", "Promoção"]
PLATFORMS = ["Instagram", "Facebook", "TikTok", "LinkedIn", "YouTube", "Pinterest"]
STATUSES = ["Pendente", "Em andamento", "Concluído"]
NEIVA_AI_API_URL = "https://neiva-ai-api.onrender.com"
SITE_URL = "https://rafaau.site"
MONTHS = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]
ROOT_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
PACKAGED_DIR = Path(getattr(sys, "_MEIPASS", ROOT_DIR))


def _asset_path(filename: str) -> Path:
    for base_dir in (ROOT_DIR, PACKAGED_DIR):
        path = base_dir / "assets" / filename
        if path.exists():
            return path
    return ROOT_DIR / "assets" / filename


LOGO_PATH = _asset_path("neiva_logo.png")
ICON_PATH = _asset_path("neiva_logo.ico")

# Tokens visuais centralizados. Não participam de nenhuma regra de negócio.
class ContentPlannerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.db = Database()
        self.pdf = PDFGenerator()
        self.selected_client_id: int | None = None
        today = date.today()
        self.current_year = today.year
        self.current_month = today.month
        self.active_view = "Dashboard"
        self._compact_layout = False
        self._navigation: list[tuple[str, object]] = []
        self.video_project: VideoProject | None = None
        self.video_busy = False
        self.video_studio_section = "Importar"
        self.auth_action: str | None = None
        self.plan = current_plan_rules()

        ctk.set_appearance_mode("light")
        theme_path = _asset_path("neiva_light.json")
        ctk.set_default_color_theme(str(theme_path) if theme_path.exists() else "blue")
        self.title("Neiva Planner")
        if ICON_PATH.exists():
            self.iconbitmap(ICON_PATH)
        screen_width, screen_height = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1320, max(900, int(screen_width * .92)))}x{min(820, max(620, int(screen_height * .88)))}")
        self.minsize(960, 640)
        self.configure(fg_color=UI["canvas"])
        self._configure_native_widgets()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color=UI["canvas"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

        self.mobile_view = ctk.StringVar(value="Dashboard")
        self.mobile_navigation = ctk.CTkOptionMenu(self, variable=self.mobile_view, values=[], command=self._navigate_compact, width=185)
        self.mobile_navigation.configure(values=[label for label, _ in self._navigation])
        self.bind("<Configure>", self._on_window_resize)

        self.show_dashboard()

    def _configure_native_widgets(self) -> None:
        """Mantém a tabela de legendas coerente com o restante da UI."""
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Neiva.Treeview", background=UI["surface"], fieldbackground=UI["surface"],
                        foreground=UI["text"], rowheight=38, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Neiva.Treeview.Heading", background=UI["surface_alt"], foreground=UI["text"],
                        relief="flat", font=("Segoe UI Semibold", 9), padding=(12, 10))
        style.map("Neiva.Treeview", background=[("selected", UI["selection"])], foreground=[("selected", UI["text"])])

    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(self, width=224, corner_radius=0, fg_color=UI["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        sidebar = self.sidebar

        if LOGO_PATH.exists():
            self.logo_image = ctk.CTkImage(Image.open(LOGO_PATH), size=(92, 58))
            ctk.CTkLabel(sidebar, text="", image=self.logo_image).pack(pady=(24, 8))
        else:
            ctk.CTkLabel(sidebar, text="NEIVA", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold")).pack(pady=(28, 2))
        ctk.CTkLabel(sidebar, text="PLANNER EDITORIAL", text_color=UI["muted"], font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold")).pack(pady=(0, 28))
        ctk.CTkLabel(sidebar, text="NAVEGAÇÃO", text_color=UI["muted"], font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold")).pack(anchor="w", padx=22, pady=(0, 7))

        self._navigation = [
            ("Dashboard", self.show_dashboard),
            ("Clientes", self.show_clients),
            ("Planejamento", self.show_planning),
            ("Estúdio de Vídeo", self.show_video_studio),
            ("Configurações", self.show_settings),
        ]
        self.nav_buttons: list[ctk.CTkButton] = []
        self.nav_indicators: list[ctk.CTkFrame] = []
        for label, handler in self._navigation:
            row = ctk.CTkFrame(sidebar, height=42, corner_radius=0, fg_color="transparent")
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            indicator = ctk.CTkFrame(row, width=3, corner_radius=0, fg_color="transparent")
            indicator.pack(side="left", fill="y")
            button = ctk.CTkButton(
                row,
                text=label,
                height=40,
                corner_radius=0,
                anchor="w",
                fg_color="transparent",
                hover_color=UI["sidebar_hover"],
                text_color=UI["sidebar_text"],
                font=font(12, "bold"),
                command=handler,
            )
            button.pack(side="left", fill="both", expand=True, padx=(0, 12))
            self.nav_buttons.append(button)
            self.nav_indicators.append(indicator)

        account = current_account()
        account_name = account.name if account else "Conta Neiva"
        account_email = f"{account.email}  ·  {self.plan.name}" if account else "Gerenciar conta"
        ctk.CTkButton(
            sidebar,
            text=f"{account_name}\n{account_email}",
            anchor="w",
            height=58,
            corner_radius=0,
            border_width=1,
            border_color=UI["sidebar_hover"],
            fg_color="transparent",
            hover_color=UI["sidebar_hover"],
            text_color="#FFFFFF",
            font=font(11, "bold"),
            command=self._open_account_manager,
        ).pack(side="bottom", fill="x", padx=18, pady=20)

    def _open_account_manager(self) -> None:
        AccountManagerDialog(self, self._restart_for_account)

    def _restart_for_account(self, action: str) -> None:
        self.auth_action = action
        self.destroy()

    def _require_feature(self, feature: str, label: str) -> bool:
        if getattr(self.plan, feature):
            return True
        if messagebox.askyesno(
            f"{label} · Recurso premium",
            f"{label} não está incluído no plano Grátis.\n\nDeseja conhecer os planos Essencial e Pro?",
        ):
            webbrowser.open(SITE_URL + "#planos")
        return False

    def _navigate_compact(self, view_name: str) -> None:
        handler = next((action for label, action in self._navigation if label == view_name), None)
        if handler:
            handler()

    def _on_window_resize(self, event) -> None:
        if event.widget is not self:
            return
        compact = event.width < 1040
        if compact == self._compact_layout:
            return
        self._compact_layout = compact
        if compact:
            self.sidebar.grid_remove()
            self.content.grid_configure(column=0, columnspan=2)
            self.mobile_view.set(self.active_view)
            self.mobile_navigation.place(x=12, y=12)
        else:
            self.mobile_navigation.place_forget()
            self.content.grid_configure(column=1, columnspan=1)
            self.sidebar.grid()
        if hasattr(self, "_content_header"):
            self._content_header.grid_configure(padx=(215 if compact else 28, 28))

    def _clear_content(self, title: str, subtitle: str = "") -> ctk.CTkFrame:
        for child in self.content.winfo_children():
            child.destroy()

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        self._content_header = header
        header.grid(row=0, column=0, sticky="ew", padx=(215 if self._compact_layout else 28, 28), pady=(24, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=title, text_color=UI["text"], font=font(30, "bold", heading=True)).grid(row=0, column=0, sticky="w")
        if subtitle:
            ctk.CTkLabel(header, text=subtitle, text_color=UI["muted"], font=ctk.CTkFont(family="Segoe UI", size=13)).grid(row=1, column=0, sticky="w", pady=(4, 0))

        frame = ctk.CTkScrollableFrame(self.content, fg_color=UI["canvas"])
        frame.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _clients(self) -> list[Client]:
        return self.db.search_clients()

    def _client_choices(self) -> list[tuple[str, Client]]:
        clients = self._clients()
        counts: dict[str, int] = {}
        for client in clients:
            counts[client.name] = counts.get(client.name, 0) + 1
        return [
            (f"{client.name} · #{client.id}" if counts[client.name] > 1 else client.name, client)
            for client in clients
        ]

    def _get_client_by_name(self, name: str) -> Client | None:
        return next((client for label, client in self._client_choices() if label == name), None)

    @staticmethod
    def _trello_secret(key: str) -> str:
        return account_secret_key(key)

    def _set_active_view(self, view_name: str, title: str, subtitle: str) -> ctk.CTkFrame:
        self.active_view = view_name
        if hasattr(self, "mobile_view"):
            self.mobile_view.set(view_name)
        for label, button, indicator in zip((item[0] for item in self._navigation), self.nav_buttons, self.nav_indicators):
            selected = label == view_name
            button.configure(fg_color=UI["sidebar_hover"] if selected else "transparent", text_color="#FFFFFF" if selected else UI["sidebar_text"])
            indicator.configure(fg_color=UI["accent"] if selected else "transparent")
        return self._clear_content(title, subtitle)

    def _show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    def _show_warning(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message)

    def _show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)

    def show_dashboard(self) -> None:
        frame = self._set_active_view("Dashboard", "Dashboard", "Visão executiva do calendário editorial.")
        stats = self.db.dashboard_stats()

        cards = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=RADIUS["md"], border_width=1, border_color=UI["border"])
        cards.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        for index in range(4):
            cards.grid_columnconfigure(index, weight=1)

        metrics = [
            ("Clientes", stats["clients"], UI["text"]),
            ("Conteúdos", stats["posts"], UI["text"]),
            ("Pendentes", stats["pending"], UI["warning"]),
            ("Concluídos", stats["done"], UI["success"]),
        ]
        for col, (label, value, color) in enumerate(metrics):
            card = ctk.CTkFrame(cards, fg_color="transparent", corner_radius=0)
            card.grid(row=0, column=col, sticky="ew")
            ctk.CTkLabel(card, text=label.upper(), text_color=UI["muted"], font=font(9, "bold")).pack(anchor="w", padx=22, pady=(18, 2))
            ctk.CTkLabel(card, text=str(value), text_color=color, font=font(32, "bold", heading=True)).pack(
                anchor="w", padx=18, pady=(0, 18)
            )

        quick = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=RADIUS["md"], border_width=1, border_color=UI["border"])
        quick.grid(row=1, column=0, sticky="ew")
        for index in range(3):
            quick.grid_columnconfigure(index, weight=1)

        ctk.CTkLabel(quick, text="AÇÕES RÁPIDAS", text_color=UI["text"], font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 10)
        )
        ctk.CTkButton(quick, text="Novo cliente", command=self._open_client_modal).grid(
            row=1, column=0, sticky="ew", padx=18, pady=(0, 18)
        )
        ctk.CTkButton(quick, text="Abrir planejamento", command=self.show_planning).grid(
            row=1, column=1, sticky="ew", padx=18, pady=(0, 18)
        )
        ctk.CTkButton(quick, text="Exportar PDF", command=self.show_export).grid(
            row=1, column=2, sticky="ew", padx=18, pady=(0, 18)
        )

    def show_clients(self) -> None:
        frame = self._set_active_view("Clientes", "Clientes", "Cadastre, edite e pesquise contas atendidas.")
        toolbar = ctk.CTkFrame(frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.grid_columnconfigure(0, weight=1)

        search = ctk.CTkEntry(toolbar, placeholder_text="Pesquisar por nome, nicho ou Instagram")
        search.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        ctk.CTkButton(
            toolbar,
            text="Pesquisar",
            width=120,
            command=lambda: self._render_clients_list(list_frame, search.get()),
        ).grid(row=0, column=1, padx=(0, 12))
        ctk.CTkButton(toolbar, text="Novo cliente", width=140, command=self._open_client_modal).grid(row=0, column=2)

        list_frame = ctk.CTkFrame(frame, fg_color="transparent")
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        self._render_clients_list(list_frame)

    def _render_clients_list(self, parent: ctk.CTkFrame, term: str = "") -> None:
        for child in parent.winfo_children():
            child.destroy()

        clients = self.db.search_clients(term)
        if not clients:
            ctk.CTkLabel(parent, text="Nenhum cliente encontrado.", text_color=UI["muted"]).grid(row=0, column=0, sticky="w", pady=20)
            return

        for row, client in enumerate(clients):
            item = ctk.CTkFrame(parent, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"])
            item.grid(row=row, column=0, sticky="ew", pady=6)
            item.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(item, text=client.name, font=ctk.CTkFont(size=17, weight="bold")).grid(
                row=0, column=0, sticky="w", padx=16, pady=(12, 0)
            )
            ctk.CTkLabel(
                item,
                text=f"{client.niche}  |  {client.instagram}  |  {client.posting_frequency}",
                text_color=UI["muted"],
            ).grid(row=1, column=0, sticky="w", padx=16, pady=(2, 12))
            ctk.CTkButton(item, text="Planejamento", width=110, command=lambda c=client: self._select_client_calendar(c)).grid(
                row=0, column=1, rowspan=2, padx=(0, 8), pady=12
            )
            ctk.CTkButton(
                item,
                text="Editar",
                width=90,
                fg_color=UI["secondary"],
                hover_color=UI["secondary_hover"],
                text_color=UI["text"],
                command=lambda c=client: self._open_client_modal(c),
            ).grid(row=0, column=2, rowspan=2, padx=(0, 8), pady=12)
            ctk.CTkButton(
                item,
                text="Excluir",
                width=90,
                fg_color=UI["error"],
                hover_color="#A91F30",
                command=lambda c=client: self._delete_client(c),
            ).grid(row=0, column=3, rowspan=2, padx=(0, 16), pady=12)

    def show_planning(self) -> None:
        frame = self._set_active_view("Planejamento", "Planejamento Editorial", "Organize conteúdos e, no mesmo lugar, exporte o PDF ou envie ao Trello.")
        self._build_calendar_controls(frame)
        self._render_calendar_grid(frame)
        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        ctk.CTkButton(actions, text="+ NOVO CONTEÚDO", fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._open_today_post).pack(side="left")
        ctk.CTkButton(actions, text="EXPORTAR PDF", command=self._export_current_planning).pack(side="right", padx=(8, 0))
        self.trello_action_button = ctk.CTkButton(actions, text="ENVIAR AO TRELLO", fg_color=UI["success"], command=self._trello_current_planning)
        self.trello_action_button.pack(side="right")

    def show_calendar(self) -> None:
        """Compatibilidade com atalhos internos e versões anteriores."""
        self.show_planning()

    def _selected_planning_client(self) -> Client | None:
        if self.selected_client_id is None:
            return None
        return self.db.get_client(self.selected_client_id)

    def _open_today_post(self) -> None:
        client = self._selected_planning_client()
        if client is None:
            self._show_warning("Planejamento", "Cadastre ou selecione um cliente primeiro.")
            return
        today = date.today()
        day = today.day if (today.year, today.month) == (self.current_year, self.current_month) else 1
        self._open_post_modal(f"{self.current_year:04d}-{self.current_month:02d}-{day:02d}", None)

    def _export_current_planning(self) -> None:
        client = self._selected_planning_client()
        if client is None:
            self._show_warning("Planejamento", "Cadastre ou selecione um cliente primeiro.")
            return
        self._export_pdf(client, self.current_year, self.current_month)

    def _trello_current_planning(self) -> None:
        client = self._selected_planning_client()
        if client is None:
            self._show_warning("Planejamento", "Cadastre ou selecione um cliente primeiro.")
            return
        self._send_to_trello(client, self.current_year, self.current_month)

    def _build_calendar_controls(self, frame: ctk.CTkFrame) -> None:
        controls = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"])
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        controls.grid_columnconfigure(1, weight=1)

        choices = self._client_choices()
        clients = [client for _label, client in choices]
        names = [label for label, _client in choices] or ["Nenhum cliente"]
        if self.selected_client_id is None and clients:
            self.selected_client_id = clients[0].id

        selected_name = next((label for label, client in choices if client.id == self.selected_client_id), names[0])
        client_menu = ctk.CTkOptionMenu(controls, values=names, command=self._set_selected_client_by_name)
        client_menu.set(selected_name)
        client_menu.grid(row=0, column=0, padx=12, pady=12)

        ctk.CTkButton(controls, text="<", width=44, command=self._previous_month).grid(row=0, column=2, padx=(8, 4))
        ctk.CTkLabel(
            controls,
            text=f"{MONTHS[self.current_month - 1]} {self.current_year}",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=3, padx=12)
        ctk.CTkButton(controls, text=">", width=44, command=self._next_month).grid(row=0, column=4, padx=(4, 12))

    def _render_calendar_grid(self, frame: ctk.CTkFrame) -> None:
        grid = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"])
        grid.grid(row=1, column=0, sticky="nsew")
        for col in range(7):
            grid.grid_columnconfigure(col, weight=1, uniform="calendar")

        for col, label in enumerate(["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]):
            ctk.CTkLabel(grid, text=label, text_color=UI["text"], font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=col, sticky="ew", padx=6, pady=(12, 8)
            )

        if self.selected_client_id is None:
            ctk.CTkLabel(grid, text="Cadastre um cliente para usar o calendário.", text_color=UI["muted"]).grid(
                row=1, column=0, columnspan=7, pady=40
            )
            return

        posts = self.db.get_posts_for_client_month(self.selected_client_id, self.current_year, self.current_month)
        posts_by_day: dict[int, list[Post]] = {}
        for post in posts:
            posts_by_day.setdefault(int(post.post_date[-2:]), []).append(post)

        calendar.setfirstweekday(calendar.SUNDAY)
        for row_index, week in enumerate(calendar.monthcalendar(self.current_year, self.current_month), start=1):
            for col_index, day in enumerate(week):
                if day == 0:
                    ctk.CTkFrame(grid, height=116, fg_color=UI["surface_alt"], corner_radius=8).grid(
                        row=row_index, column=col_index, sticky="nsew", padx=6, pady=6
                    )
                    continue

                day_posts = posts_by_day.get(day, [])
                color = UI["selection"] if day_posts else UI["surface_alt"]
                cell = ctk.CTkFrame(grid, height=116, fg_color=color, corner_radius=8)
                cell.grid(row=row_index, column=col_index, sticky="nsew", padx=6, pady=6)
                cell.grid_propagate(False)
                ctk.CTkLabel(cell, text=str(day), font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="nw", padx=10, pady=(8, 2))
                for post in day_posts[:3]:
                    ctk.CTkLabel(cell, text=f"{post.content_type} · {post.status}", text_color="#9F1D2C", anchor="w").pack(
                        fill="x", padx=10
                    )
                if len(day_posts) > 3:
                    ctk.CTkLabel(cell, text=f"+{len(day_posts) - 3} conteúdos", text_color=UI["accent_hover"]).pack(anchor="w", padx=10)
                ctk.CTkButton(
                    cell,
                    text="Abrir",
                    height=26,
                    command=lambda d=day: self._open_day_modal(d),
                ).pack(side="bottom", fill="x", padx=8, pady=8)

    def show_export(self) -> None:
        self.show_planning()

    def show_trello(self) -> None:
        self.show_planning()

    def show_video_studio(self) -> None:
        if not self._require_feature("video", "Estúdio de Vídeo"):
            return
        frame = self._set_active_view(
            "Estúdio de Vídeo",
            "Editar no DaVinci Resolve",
            "Abra o editor instalado no computador e continue todo o trabalho diretamente nele.",
        )
        configured = self.db.get_setting("DAVINCI_RESOLVE_PATH")
        executable = find_davinci(configured)
        panel_status = integration_status()

        box = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=12, border_width=1, border_color=UI["border"])
        box.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text="DAVINCI RESOLVE", font=font(18, "bold", heading=True)).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 5))
        status_text = f"Pronto para abrir\n{executable}" if executable else "DaVinci Resolve não encontrado neste computador."
        status_color = UI["success"] if executable else UI["warning"]
        ctk.CTkLabel(box, text=status_text, text_color=status_color, justify="left").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 16))

        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        ctk.CTkButton(
            actions,
            text="ABRIR DAVINCI RESOLVE",
            command=self._launch_davinci,
            state="normal" if executable else "disabled",
            width=220,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="CONFIGURAR CAMINHO",
            command=self.show_settings,
            fg_color=UI["secondary"],
            hover_color=UI["secondary_hover"],
            text_color=UI["text"],
        ).pack(side="left", padx=10)

        integration_text = (
            "Comando instalado. No DaVinci, abra Espaço de trabalho → Scripts → Edit → rafaau_timeline."
            if panel_status.installed
            else "Instale o comando para remover silêncios e criar legendas a partir da timeline atual."
        )
        ctk.CTkLabel(
            box,
            text=integration_text,
            text_color=UI["success"] if panel_status.installed else UI["muted"],
            justify="left",
            wraplength=850,
        ).grid(row=3, column=0, sticky="w", padx=20, pady=(0, 10))
        ctk.CTkButton(
            box,
            text="ATUALIZAR COMANDO NO DAVINCI" if panel_status.installed else "INSTALAR COMANDO NO DAVINCI",
            command=self._install_davinci_integration,
            width=250,
        ).grid(row=4, column=0, sticky="w", padx=20, pady=(0, 20))

        ctk.CTkLabel(
            frame,
            text="O painel trabalha na timeline aberta e sempre cria uma cópia. Nesta primeira versão, use uma timeline simples com um único vídeo e seu áudio vinculado.",
            text_color=UI["muted"],
            justify="left",
            wraplength=850,
        ).grid(row=1, column=0, sticky="w")

    def _install_davinci_integration(self) -> None:
        try:
            status = install_integration()
        except Exception as exc:
            self._show_error("Comando do DaVinci", str(exc))
            return
        self._show_info(
            "Comando do DaVinci",
            "Comando instalado com sucesso.\n\n"
            "Reinicie o DaVinci Resolve e abra:\n"
            "Espaço de trabalho → Scripts → Edit → rafaau_timeline\n\n"
            f"Arquivo instalado em:\n{status.script_path}",
        )
        self.show_video_studio()

    def _launch_davinci(self) -> None:
        try:
            executable = launch_davinci(self.db.get_setting("DAVINCI_RESOLVE_PATH"))
            self.db.set_setting("DAVINCI_RESOLVE_PATH", str(executable))
        except Exception as exc:
            self._show_error("DaVinci Resolve", str(exc))

    def _select_davinci(self) -> None:
        filename = filedialog.askopenfilename(
            title="Selecione o Resolve.exe",
            filetypes=(("DaVinci Resolve", "Resolve.exe"), ("Executáveis", "*.exe")),
        )
        if not filename:
            return
        try:
            executable = validate_davinci_executable(filename)
            self.db.set_setting("DAVINCI_RESOLVE_PATH", str(executable))
        except Exception as exc:
            self._show_error("DaVinci Resolve", str(exc))
            return
        self.show_settings()

    def _detect_davinci(self) -> None:
        executable = find_davinci()
        if executable is None:
            self._show_warning("DaVinci Resolve", "Não encontrei o Resolve.exe nas pastas padrão de instalação.")
            return
        self.db.set_setting("DAVINCI_RESOLVE_PATH", str(executable))
        self.show_settings()

    def _video_studio_frame(self, section: str, subtitle: str) -> ctk.CTkFrame:
        self._persist_video_controls()
        self.video_studio_section = section
        outer = self._set_active_view("Estúdio de Vídeo", "Estúdio de Vídeo", subtitle)
        tabs = ctk.CTkFrame(outer, fg_color=UI["surface"], corner_radius=10)
        tabs.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        for label, handler in (("Importar", self.show_youtube_downloader), ("Legendas", self.show_video_subtitles), ("Cortes", self.show_clip_finder)):
            selected = label == section
            ctk.CTkButton(
                tabs, text=label.upper(), width=120, command=handler,
                fg_color=UI["accent"] if selected else UI["surface_alt"],
                hover_color=UI["accent_hover"] if selected else UI["secondary_hover"],
                text_color="#FFFFFF" if selected else UI["text"],
                border_width=1,
                border_color=UI["accent"] if selected else UI["border"],
            ).pack(side="left", padx=6, pady=8)
        current = self.video_project.video_path.name if self.video_project else "Nenhum vídeo carregado"
        ctk.CTkLabel(tabs, text=f"Vídeo atual: {current}", text_color=UI["muted"]).pack(side="right", padx=12)
        ctk.CTkButton(tabs, text="ARQUIVO LOCAL", width=120, fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._import_local_video).pack(side="right", padx=6, pady=8)
        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        return body

    def _persist_video_controls(self) -> None:
        project = self.video_project
        if not project or not hasattr(self, "video_format"):
            return
        try:
            project.video_format = self.video_format.get(); project.fit_mode = self.video_fit.get()
            project.caption_font = self.caption_font.get(); project.caption_style = self.caption_style.get()
            project.caption_position = self.caption_position.get(); project.caption_size = self.caption_size.get()
            project.effect_preset = self.effect_preset.get(); project.animation = self.effect_animation.get()
            project.export_quality = self.export_quality.get(); project.dynamic_edit_enabled = self.dynamic_edit_enabled.get()
            project.dynamic_zoom_enabled = self.dynamic_zoom_enabled.get(); project.dynamic_zoom_amount = self.dynamic_zoom_amount.get()
            project.effect_speed = self.effect_speed.get(); project.video_motion = self.video_motion.get()
            project.video_motion_enabled = self.video_motion_enabled.get(); project.motion_smoothing_enabled = self.motion_smoothing_enabled.get()
            project.caption_fixed = self.caption_fixed.get()
            project.keywords = {item.strip().lower() for item in self.effect_keywords.get().split(",") if item.strip()}
        except TclError:
            pass

    def _import_local_video(self) -> None:
        filename = filedialog.askopenfilename(title="Selecionar vídeo", filetypes=(("Vídeos", "*.mp4 *.mov *.mkv *.avi *.webm"), ("Todos", "*.*")))
        if not filename:
            return
        try:
            path = Path(filename)
            probe(path)
            self.video_project = VideoProject(path)
        except Exception as exc:
            self._show_error("Vídeo inválido", str(exc))
            return
        self.show_video_subtitles()

    def show_video_subtitles(self) -> None:
        frame = self._video_studio_frame("Legendas", "Transcreva, revise, remova silêncios e exporte o vídeo atual.")
        project = self.video_project
        self.video_model = ctk.StringVar(value="base")
        self.video_format = ctk.StringVar(value=getattr(project, "video_format", "Original"))
        self.video_fit = ctk.StringVar(value=getattr(project, "fit_mode", "Preencher"))
        self.caption_font = ctk.StringVar(value=getattr(project, "caption_font", "Arial"))
        self.caption_style = ctk.StringVar(value=getattr(project, "caption_style", "Viral"))
        self.caption_position = ctk.StringVar(value=getattr(project, "caption_position", "Centro"))
        self.caption_size = IntVar(value=getattr(project, "caption_size", 42))
        self.export_with_captions = ctk.BooleanVar(value=True)
        self.effect_preset = ctk.StringVar(value=getattr(project, "effect_preset", "Viral"))
        self.effect_animation = ctk.StringVar(value=getattr(project, "animation", "Word Highlight"))
        self.export_quality = ctk.StringVar(value=getattr(project, "export_quality", "Alta"))
        self.effect_keywords = ctk.StringVar(value=", ".join(sorted(getattr(project, "keywords", set()))))
        self.dynamic_edit_enabled = ctk.BooleanVar(value=getattr(project, "dynamic_edit_enabled", True) if project else True)
        self.dynamic_zoom_enabled = ctk.BooleanVar(value=getattr(project, "dynamic_zoom_enabled", True) if project else True)
        self.dynamic_zoom_amount = IntVar(value=getattr(project, "dynamic_zoom_amount", 8))
        self.effect_speed = DoubleVar(value=getattr(project, "effect_speed", 1.0))
        self.video_motion = ctk.StringVar(value=getattr(project, "video_motion", "Auto Mix"))
        self.video_motion_enabled = ctk.BooleanVar(value=getattr(project, "video_motion_enabled", True) if project else True)
        self.motion_smoothing_enabled = ctk.BooleanVar(value=getattr(project, "motion_smoothing_enabled", True) if project else True)
        self.caption_fixed = ctk.BooleanVar(value=getattr(project, "caption_fixed", True) if project else True)
        source = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=12, border_width=1, border_color=UI["border"]); source.grid(row=0, column=0, sticky="ew", pady=(0, 12)); source.grid_columnconfigure(0, weight=1)
        self.video_info = ctk.CTkLabel(source, text="Selecione um vídeo para iniciar a transcrição local.", text_color=UI["text"], justify="left")
        self.video_info.grid(row=0, column=0, padx=18, pady=16, sticky="w")
        ctk.CTkButton(source, text="Selecionar vídeo", command=self._select_video).grid(row=0, column=1, padx=18, pady=16)
        settings = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=12, border_width=1, border_color=UI["border"]); settings.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for col, (label, variable, values) in enumerate((("Modelo", self.video_model, ["tiny", "base", "small", "medium"]), ("Formato", self.video_format, ["Original", "Vertical 9:16", "Quadrado", "Horizontal"]), ("Enquadramento", self.video_fit, ["Preencher", "Ajustar"]))):
            settings.grid_columnconfigure(col, weight=1); ctk.CTkLabel(settings, text=label, text_color=UI["text"]).grid(row=0, column=col, padx=15, pady=(12, 3), sticky="w"); ctk.CTkOptionMenu(settings, variable=variable, values=values).grid(row=1, column=col, padx=15, pady=(0, 12), sticky="ew")
        for col, (label, variable, values) in enumerate((("Fonte", self.caption_font, ["Arial", "Impact", "Verdana", "Tahoma"]), ("Estilo", self.caption_style, ["Viral", "Clean", "Impacto"]), ("Posição", self.caption_position, ["Superior", "Centro", "Inferior"]))):
            ctk.CTkLabel(settings, text=label, text_color=UI["text"]).grid(row=2, column=col, padx=15, pady=(0, 3), sticky="w"); ctk.CTkOptionMenu(settings, variable=variable, values=values).grid(row=3, column=col, padx=15, pady=(0, 12), sticky="ew")
        ctk.CTkLabel(settings, text="Tamanho", text_color=UI["text"]).grid(row=2, column=3, padx=15, pady=(0, 3), sticky="w")
        self.caption_size_label = ctk.CTkLabel(settings, text=str(self.caption_size.get()), text_color=UI["warning"])
        self.caption_size_label.grid(row=2, column=3, padx=(0,15), pady=(0,3), sticky="e")
        ctk.CTkSlider(settings, from_=0, to=72, number_of_steps=72, variable=self.caption_size, command=lambda value: self.caption_size_label.configure(text=str(round(value)))).grid(row=3, column=3, padx=15, pady=(0,12), sticky="ew")
        ctk.CTkCheckBox(settings, text="Incluir legendas no vídeo exportado", variable=self.export_with_captions).grid(row=4, column=0, columnspan=2, padx=15, pady=(0,12), sticky="w")
        effects = ctk.CTkFrame(frame,fg_color=UI["surface"],corner_radius=12,border_width=1,border_color=UI["border"]); effects.grid(row=7,column=0,sticky="ew",pady=(16,0));
        ctk.CTkLabel(effects,text="EDIÇÃO DINÂMICA DO VÍDEO",font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,columnspan=4,sticky="w",padx=14,pady=(12,4))
        for col,(label,var,values) in enumerate((("Preset",self.effect_preset,["Viral","Clean","Impacto","Meme"]),("Animação",self.effect_animation,["Auto Mix","Pop","Bounce","Fade","Scale","Slide","Word Highlight","Typewriter"]),("Qualidade",self.export_quality,["Alta","Média","Baixa"]))):
            effects.grid_columnconfigure(col,weight=1); ctk.CTkLabel(effects,text=label,text_color=UI["text"]).grid(row=1,column=col,padx=14,sticky="w"); ctk.CTkOptionMenu(effects,variable=var,values=values).grid(row=2,column=col,padx=14,pady=(2,10),sticky="ew")
        ctk.CTkLabel(effects,text="Palavras-chave (separe por vírgula)",text_color=UI["text"]).grid(row=3,column=0,columnspan=2,padx=14,sticky="w")
        ctk.CTkEntry(effects,textvariable=self.effect_keywords,placeholder_text="CARA, INSANO").grid(row=4,column=0,columnspan=3,padx=14,pady=(2,12),sticky="ew")
        ctk.CTkCheckBox(effects,text="Ativar edição dinâmica",variable=self.dynamic_edit_enabled).grid(row=5,column=0,padx=14,pady=(0,8),sticky="w")
        ctk.CTkCheckBox(effects,text="Manter legenda fixa",variable=self.caption_fixed).grid(row=5,column=1,padx=14,pady=(0,8),sticky="w")
        ctk.CTkButton(effects,text="APLICAR EDIÇÃO DINÂMICA",command=self._apply_dynamic_edit).grid(row=5,column=2,columnspan=2,padx=14,pady=(0,8),sticky="e")
        ctk.CTkCheckBox(effects,text="Zoom gradual",variable=self.dynamic_zoom_enabled).grid(row=6,column=0,padx=14,pady=(0,8),sticky="w")
        ctk.CTkLabel(effects,text="Zoom máximo").grid(row=6,column=1,padx=14,sticky="e")
        self.zoom_amount_label=ctk.CTkLabel(effects,text=f"{self.dynamic_zoom_amount.get()}%",text_color=UI["warning"]); self.zoom_amount_label.grid(row=6,column=2,padx=4,sticky="w")
        ctk.CTkSlider(effects,from_=1,to=15,number_of_steps=14,variable=self.dynamic_zoom_amount,command=lambda value:self.zoom_amount_label.configure(text=f"{round(value)}%")).grid(row=6,column=3,padx=14,pady=(0,8),sticky="ew")
        ctk.CTkCheckBox(effects,text="Movimento do vídeo",variable=self.video_motion_enabled).grid(row=7,column=0,padx=14,sticky="w")
        ctk.CTkOptionMenu(effects,variable=self.video_motion,values=["Auto Mix","Zoom In","Zoom Out","Pan Esquerda","Pan Direita","Vertical"]).grid(row=7,column=1,columnspan=2,padx=14,pady=(0,8),sticky="ew")
        ctk.CTkCheckBox(effects,text="Suavizar movimentos (48 FPS)",variable=self.motion_smoothing_enabled).grid(row=8,column=0,columnspan=2,padx=14,pady=(0,8),sticky="w")
        ctk.CTkLabel(effects,text="Velocidade").grid(row=8,column=2,padx=(0,4),sticky="e")
        self.effect_speed_label=ctk.CTkLabel(effects,text=f"{self.effect_speed.get():.1f}x".replace(".",","),text_color=UI["warning"]); self.effect_speed_label.grid(row=8,column=3,padx=(0,14),sticky="e")
        ctk.CTkSlider(effects,from_=0.5,to=2.0,number_of_steps=15,variable=self.effect_speed,command=lambda value:self.effect_speed_label.configure(text=f"{value:.1f}x".replace(".",","))).grid(row=9,column=0,columnspan=4,padx=14,pady=(0,8),sticky="ew")
        self.effects_timeline=ctk.CTkLabel(effects,text="Timeline de vídeo: será atualizada ao gerar legendas.",text_color=UI["muted"]); self.effects_timeline.grid(row=10,column=0,columnspan=4,padx=14,pady=(0,12),sticky="w")
        bar = ctk.CTkFrame(frame, fg_color="transparent"); bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.video_generate_button = ctk.CTkButton(bar, text="Gerar legendas", command=self._generate_video_subtitles)
        self.video_generate_button.pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Exportar SRT / VTT", fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._export_video_captions).pack(side="left")
        self.video_export_button = ctk.CTkButton(bar, text="EXPORTAR VÍDEO", command=self._export_subtitled_video)
        self.video_export_button.pack(side="right")
        self.video_table = ttk.Treeview(frame, style="Neiva.Treeview", columns=("start", "end", "text"), show="headings", height=14)
        for key, label, width in (("start", "Início", 100), ("end", "Fim", 100), ("text", "Texto — duplo clique para editar", 700)):
            self.video_table.heading(key, text=label); self.video_table.column(key, width=width, anchor="w")
        self.video_table.grid(row=3, column=0, sticky="ew"); self.video_table.bind("<Double-1>", self._edit_video_subtitle)
        self.video_status = ctk.CTkLabel(frame, text="Modelos maiores oferecem maior precisão e consomem mais RAM/CPU.", text_color=UI["muted"]); self.video_status.grid(row=4, column=0, sticky="w", pady=(12, 2))
        self.video_progress = ctk.CTkProgressBar(frame); self.video_progress.grid(row=5, column=0, sticky="ew"); self.video_progress.set(0)
        edit = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=12, border_width=1, border_color=UI["border"]); edit.grid(row=6,column=0,sticky="ew",pady=(16,0)); edit.grid_columnconfigure(4,weight=1)
        ctk.CTkLabel(edit,text="EDIÇÃO AUTOMÁTICA",font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,columnspan=5,sticky="w",padx=14,pady=(12,5))
        self.silence_mode=ctk.StringVar(value="Desativado"); self.silence_duration=ctk.StringVar(value="0.4"); self.silence_margin=ctk.StringVar(value="0.15"); self.silence_threshold=ctk.StringVar(value="-35")
        for col,label,var,values in ((0,"Modo",self.silence_mode,["Desativado","Reduzir silêncios","Remover silêncios"]),(1,"Duração mín.",self.silence_duration,None),(2,"Margem",self.silence_margin,None),(3,"Volume dB",self.silence_threshold,None)):
            ctk.CTkLabel(edit,text=label,text_color=UI["text"]).grid(row=1,column=col,sticky="w",padx=14)
            (ctk.CTkOptionMenu(edit,variable=var,values=values) if values else ctk.CTkEntry(edit,textvariable=var,width=80)).grid(row=2,column=col,padx=14,pady=(2,12),sticky="ew")
        ctk.CTkButton(edit,text="ANALISAR",command=self._analyze_silences).grid(row=2,column=4,padx=14,pady=(2,12),sticky="e")
        self.silence_summary=ctk.CTkLabel(edit,text="Silêncios encontrados: —",text_color=UI["muted"]); self.silence_summary.grid(row=3,column=0,columnspan=4,sticky="w",padx=14,pady=(0,12))
        self.silence_apply=ctk.CTkButton(edit,text="APLICAR",state="disabled",command=self._apply_silence_edits); self.silence_apply.grid(row=3,column=4,padx=14,pady=(0,12),sticky="e")
        if self.video_project:
            self.video_info.configure(text=f"{self.video_project.video_path.name}\nVídeo carregado no Estúdio.")
            if self.video_project.subtitles:
                self._refresh_video_table()

    def show_clip_finder(self) -> None:
        frame = self._video_studio_frame("Cortes", "Encontre os trechos com melhor potencial no vídeo atual ou em um link do YouTube.")
        self.clip_url = ctk.CTkEntry(frame, placeholder_text="Link do YouTube (opcional se já houver um vídeo carregado)", height=42)
        self.clip_url.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        actions = ctk.CTkFrame(frame, fg_color="transparent"); actions.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkButton(actions, text="Colar", width=90, fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._paste_clip_url).pack(side="left")
        self.clip_model = ctk.StringVar(value="base")
        self.clip_use_ai = ctk.BooleanVar(value=bool(get_secret("NEIVA_AI_CLIENT_TOKEN")))
        ctk.CTkLabel(actions, text="Modelo de transcrição", text_color=UI["muted"]).pack(side="left", padx=(18, 7))
        ctk.CTkOptionMenu(actions, variable=self.clip_model, values=["tiny", "base", "small", "medium"], width=120).pack(side="left")
        ctk.CTkCheckBox(actions, text="Usar IA Neiva", variable=self.clip_use_ai).pack(side="left", padx=14)
        self.clip_analyze_button = ctk.CTkButton(actions, text="ENCONTRAR CORTES", command=self._start_clip_analysis, fg_color=UI["accent"])
        self.clip_analyze_button.pack(side="right")
        ctk.CTkLabel(frame, text="Use somente vídeos para os quais você possui direito ou autorização. Com IA Neiva marcada, somente a transcrição é enviada para análise.", text_color=UI["muted"], justify="left", wraplength=900).grid(row=2, column=0, sticky="w", pady=(0, 10))
        self.clip_status = ctk.CTkLabel(frame, text="Pronto para analisar.", text_color=UI["text"]); self.clip_status.grid(row=3, column=0, sticky="w")
        self.clip_progress = ctk.CTkProgressBar(frame); self.clip_progress.grid(row=4, column=0, sticky="ew", pady=(5, 13)); self.clip_progress.set(0)
        self.clip_table = ttk.Treeview(frame, style="Neiva.Treeview", columns=("start", "end", "score", "title"), show="headings", height=9)
        for key, label, width in (("start", "Início", 85), ("end", "Fim", 85), ("score", "Potencial", 90), ("title", "Assunto / gancho sugerido", 680)):
            self.clip_table.heading(key, text=label); self.clip_table.column(key, width=width, anchor="w")
        self.clip_table.grid(row=5, column=0, sticky="ew")
        self.clip_table.bind("<<TreeviewSelect>>", self._show_clip_detail)
        detail = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"]); detail.grid(row=6, column=0, sticky="ew", pady=(12, 0)); detail.grid_columnconfigure(0, weight=1)
        self.clip_detail = ctk.CTkLabel(detail, text="Os detalhes do corte selecionado aparecerão aqui.", wraplength=900, justify="left", anchor="w", text_color=UI["text"])
        self.clip_detail.grid(row=0, column=0, padx=14, pady=13, sticky="ew")
        ctk.CTkButton(detail, text="Copiar corte", width=110, fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._copy_selected_clip).grid(row=0, column=1, padx=14, pady=13)
        self.clip_suggestions: list[ClipSuggestion] = []

    def _paste_clip_url(self) -> None:
        try:
            self.clip_url.insert(0, self.clipboard_get().strip())
        except TclError:
            self._show_warning("Área de transferência", "Não há um link de texto para colar.")

    def _clip_progress_update(self, text: str, value: int) -> None:
        self.after(0, lambda: (self.clip_status.configure(text=text), self.clip_progress.set(max(0, min(100, value)) / 100)))

    def _start_clip_analysis(self) -> None:
        url = self.clip_url.get().strip()
        if url and not is_youtube_url(url):
            self._show_warning("Link inválido", "Insira um link válido do YouTube ou deixe vazio para usar o vídeo atual."); return
        if not url and not self.video_project:
            self._show_warning("Encontrar Cortes", "Carregue um vídeo no Estúdio ou informe um link do YouTube."); return
        model_name = self.clip_model.get()
        use_ai = self.clip_use_ai.get()
        api_url = NEIVA_AI_API_URL if use_ai else ""
        access_token = get_secret("NEIVA_AI_CLIENT_TOKEN") if use_ai else ""
        self.clip_analyze_button.configure(state="disabled"); self.clip_progress.set(0)
        self.clip_table.delete(*self.clip_table.get_children()); self.clip_detail.configure(text="Baixando o vídeo e analisando a fala…")
        def download_progress(data) -> None:
            if data.get("status") == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                amount = data.get("downloaded_bytes", 0)
                percent = int(amount / total * 18) if total else 0
                self._clip_progress_update("Baixando vídeo…", percent)
            elif data.get("status") == "finished": self._clip_progress_update("Preparando vídeo…", 20)
        def transcription_progress(text: str, value: int) -> None:
            self._clip_progress_update(text, 20 + int(value * .70))
        def task() -> None:
            try:
                if url:
                    folder = EXPORTS_DIR / "downloads"
                    video = download_youtube(url, folder, download_progress)
                    subtitles = transcribe(video, model_name, 40, transcription_progress)
                else:
                    video = self.video_project.video_path
                    subtitles = self.video_project.subtitles or transcribe(video, model_name, 40, transcription_progress)
                if use_ai:
                    self._clip_progress_update("IA analisando contexto e sugerindo cortes…", 94)
                    suggestions = analyze_cuts(subtitles, api_url, access_token)
                else:
                    self._clip_progress_update("Selecionando trechos promissores…", 94)
                    suggestions = find_suggestions(subtitles)
                self.after(0, lambda: self._display_clip_suggestions(suggestions, video, subtitles))
            except Exception as exc:
                self.after(0, lambda message=str(exc): (self.clip_status.configure(text="Falha na análise."), self.clip_progress.set(0), self._show_error("Encontrar Cortes", message)))
            finally:
                self.after(0, lambda: self.clip_analyze_button.configure(state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def _display_clip_suggestions(self, suggestions: list[ClipSuggestion], video: Path, subtitles: list | None = None) -> None:
        if self.video_project and self.video_project.video_path.resolve() == video.resolve():
            if subtitles is not None:
                self.video_project.subtitles = list(subtitles)
        else:
            self.video_project = VideoProject(video, subtitles=list(subtitles or []))
        self.clip_suggestions = suggestions
        if not suggestions:
            self.clip_status.configure(text="Nenhum trecho longo o bastante foi encontrado. Tente um vídeo com mais fala contínua.")
            self.clip_detail.configure(text=f"Vídeo baixado e analisado: {video.name}")
            return
        for index, item in enumerate(suggestions):
            self.clip_table.insert("", "end", iid=str(index), values=(self._caption_time(item.start), self._caption_time(item.end), f"{item.score}%", item.title))
        report = self._save_clip_analysis(video, suggestions)
        self.clip_progress.set(1); self.clip_status.configure(text=f"Análise concluída: {len(suggestions)} cortes sugeridos. Resultado salvo em {report.name}.")
        self.clip_table.selection_set("0"); self._show_clip_detail()

    def _save_clip_analysis(self, video: Path, suggestions: list[ClipSuggestion]) -> Path:
        folder = EXPORTS_DIR / "analises_de_cortes"; folder.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        output = folder / f"{video.stem}_cortes_{now:%Y%m%d_%H%M%S}.json"
        data = {"video": str(video), "youtube_url": self.clip_url.get().strip(), "created_at": now.isoformat(timespec="seconds"), "cuts": [{"start": item.start, "end": item.end, "title": item.title, "summary": item.summary, "score": item.score} for item in suggestions]}
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    def _show_clip_detail(self, event=None) -> None:
        selected = self.clip_table.selection()
        if not selected: return
        item = self.clip_suggestions[int(selected[0])]
        self.clip_detail.configure(text=f"{self._caption_time(item.start)} até {self._caption_time(item.end)}  •  Potencial: {item.score}%\n\n{item.summary}")

    def _copy_selected_clip(self) -> None:
        selected = self.clip_table.selection()
        if not selected:
            self._show_warning("Encontrar Cortes", "Selecione um corte primeiro."); return
        item = self.clip_suggestions[int(selected[0])]
        value = f"{item.title}\nTempo: {self._caption_time(item.start)}–{self._caption_time(item.end)}\nPotencial: {item.score}%\n\n{item.summary}"
        self.clipboard_clear(); self.clipboard_append(value); self.clip_status.configure(text="Corte copiado para a área de transferência.")

    def show_youtube_downloader(self) -> None:
        frame = self._video_studio_frame("Importar", "Importe um arquivo local ou baixe um vídeo autorizado do YouTube.")
        self.youtube_url = ctk.CTkEntry(frame, placeholder_text="Cole o link do YouTube", height=42); self.youtube_url.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        actions = ctk.CTkFrame(frame, fg_color="transparent"); actions.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkButton(actions, text="Carregar informações", command=self._load_youtube_info).pack(side="left")
        ctk.CTkButton(actions, text="Colar", width=90, fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._paste_youtube_url).pack(side="left", padx=8)
        box = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"]); box.grid(row=2, column=0, sticky="ew", pady=(0, 12)); box.grid_columnconfigure(0, weight=1)
        self.youtube_info = ctk.CTkLabel(box, text="Cole um link e carregue as informações do vídeo.", justify="left", anchor="w", text_color=UI["text"]); self.youtube_info.grid(row=0, column=0, padx=18, pady=18, sticky="ew")
        ctk.CTkLabel(frame, text="Pasta de destino", text_color=UI["text"]).grid(row=3, column=0, sticky="w")
        folder = ctk.CTkFrame(frame, fg_color="transparent"); folder.grid(row=4, column=0, sticky="ew", pady=(4, 16)); folder.grid_columnconfigure(0, weight=1)
        self.youtube_folder = ctk.CTkEntry(folder, height=40); self.youtube_folder.insert(0, str(EXPORTS_DIR / "downloads")); self.youtube_folder.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(folder, text="Escolher pasta", command=self._choose_youtube_folder).grid(row=0, column=1)
        self.youtube_status = ctk.CTkLabel(frame, text="Pronto para baixar.", text_color=UI["muted"]); self.youtube_status.grid(row=5, column=0, sticky="w")
        self.youtube_progress = ctk.CTkProgressBar(frame); self.youtube_progress.grid(row=6, column=0, sticky="ew", pady=(4, 5)); self.youtube_progress.set(0)
        self.youtube_details = ctk.CTkLabel(frame, text="0%", text_color=UI["muted"]); self.youtube_details.grid(row=7, column=0, sticky="w")
        self.youtube_download_button = ctk.CTkButton(frame, text="BAIXAR VÍDEO", height=48, font=ctk.CTkFont(size=16, weight="bold"), command=self._start_youtube_download); self.youtube_download_button.grid(row=8, column=0, sticky="ew", pady=(16, 0))

    def _choose_youtube_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.youtube_folder.get() or str(EXPORTS_DIR))
        if folder: self.youtube_folder.delete(0, "end"); self.youtube_folder.insert(0, folder)

    def _paste_youtube_url(self) -> None:
        try:
            self.youtube_url.insert(0, self.clipboard_get().strip())
        except TclError:
            self._show_warning("Área de transferência", "Não há um link de texto para colar.")

    def _load_youtube_info(self) -> None:
        url = self.youtube_url.get().strip()
        if not is_youtube_url(url): self._show_warning("Link inválido", "Insira um link válido do YouTube."); return
        self.youtube_status.configure(text="Buscando informações…")
        def task() -> None:
            try:
                info = fetch_info(url); self.after(0, lambda: (self.youtube_info.configure(text=f"{info.title}\n\nCanal: {info.channel}\nDuração: {youtube_duration(info.duration)}\nMelhor resolução: {info.resolution}"), self.youtube_status.configure(text="Informações carregadas.")))
            except Exception as exc: self.after(0, lambda message=str(exc): self._show_error("YouTube", message))
        threading.Thread(target=task, daemon=True).start()

    def _start_youtube_download(self) -> None:
        url = self.youtube_url.get().strip(); destination_text = self.youtube_folder.get().strip()
        if not is_youtube_url(url): self._show_warning("Link inválido", "Insira um link válido do YouTube."); return
        if not destination_text: self._show_warning("Pasta de destino", "Escolha uma pasta para salvar o vídeo."); return
        destination = Path(destination_text)
        try: destination.mkdir(parents=True, exist_ok=True)
        except OSError as exc: self._show_error("Pasta de destino", f"Não foi possível criar a pasta:\n{exc}"); return
        self.youtube_download_button.configure(state="disabled"); self.youtube_progress.set(0)
        def progress(data) -> None:
            if data.get("status") == "downloading":
                total, downloaded = data.get("total_bytes") or data.get("total_bytes_estimate"), data.get("downloaded_bytes", 0)
                value = downloaded / total if total else 0; self.after(0, lambda: (self.youtube_progress.set(value), self.youtube_details.configure(text=f"{value * 100:.0f}%"), self.youtube_status.configure(text="Baixando vídeo…")))
            elif data.get("status") == "finished": self.after(0, lambda: self.youtube_status.configure(text="Processando arquivo…"))
        def task() -> None:
            try:
                result = download_youtube(url, destination, progress); self.after(0, lambda: self._finish_youtube_download(result))
            except Exception as exc: self.after(0, lambda message=str(exc): (self.youtube_download_button.configure(state="normal"), self._show_error("Falha no download", message)))
        threading.Thread(target=task, daemon=True).start()

    def _select_video(self) -> None:
        filename = filedialog.askopenfilename(title="Selecionar vídeo", filetypes=(("Vídeos", "*.mp4 *.mov *.mkv *.avi *.webm"), ("Todos", "*.*")))
        if not filename: return
        try:
            path = Path(filename); duration, width, height = probe(path); self.video_project = VideoProject(path)
            self.video_info.configure(text=f"{path.name}\n{width} × {height} · {duration:.1f} segundos"); self.video_status.configure(text="Vídeo carregado. Gere as legendas para continuar.")
        except Exception as exc: self._show_error("Vídeo inválido", str(exc))

    def _video_progress_update(self, text: str, value: int) -> None:
        self.after(0, lambda: (self.video_status.configure(text=text), self.video_progress.set(value / 100)))

    def _generate_video_subtitles(self) -> None:
        if not self.video_project: self._show_warning("Legendas de Vídeo", "Selecione um vídeo primeiro."); return
        if self.video_busy: return
        self.video_busy = True
        self.video_generate_button.configure(state="disabled")
        project = self.video_project
        source = project.video_path
        def task() -> None:
            try:
                subtitles = transcribe(source, self.video_model.get(), 5, self._video_progress_update)
                def apply_result() -> None:
                    if self.video_project is not project:
                        self.video_status.configure(text="A transcrição concluída pertence a outro vídeo e foi descartada.")
                        return
                    project.subtitles = subtitles
                    self._refresh_video_table()
                self.after(0, apply_result)
            except Exception as exc:
                self.after(0, lambda message=str(exc): (self.video_status.configure(text=f"Falha na transcrição: {message}"), self.video_progress.set(0), self._show_error("Falha na transcrição", message)))
            finally:
                self.after(0, self._finish_video_task)
        threading.Thread(target=task, daemon=True).start()

    def _finish_video_task(self) -> None:
        self.video_busy = False
        if hasattr(self, "video_generate_button") and self.video_generate_button.winfo_exists():
            self.video_generate_button.configure(state="normal")

    def _silence_settings(self):
        try:
            settings = SilenceSettings(float(self.silence_threshold.get()),float(self.silence_duration.get()),float(self.silence_margin.get()),float(self.silence_margin.get()),self.silence_mode.get())
            if settings.min_duration <= 0 or settings.before_margin < 0 or settings.after_margin < 0:
                raise ValueError
            return settings
        except ValueError: raise VideoError("Informe números válidos para duração, margem e volume.")

    def _analyze_silences(self) -> None:
        if not self.video_project: self._show_warning("Edição automática","Selecione um vídeo primeiro."); return
        if self.video_busy:
            self._show_warning("Edição automática", "Já existe um trabalho de vídeo em andamento.")
            return
        try: settings=self._silence_settings()
        except Exception as exc: self._show_error("Edição automática",str(exc)); return
        project = self.video_project
        source = project.video_path
        self.video_busy = True
        def task():
            try:
                silences=detect_silences(source,settings.threshold_db,settings.min_duration); cuts=plan_cuts(silences,settings); duration,_,_=probe(source); final=duration-sum(c.end-c.start for c in cuts)
                def apply_result() -> None:
                    if self.video_project is not project:
                        return
                    self.silence_cuts=cuts
                    self.silence_summary.configure(text=f"Silêncios encontrados: {len(silences)} · Tempo original: {duration:.1f}s · Final estimado: {final:.1f}s")
                    self.silence_apply.configure(state="normal" if cuts else "disabled")
                    self.video_status.configure(text="Timeline: cortes de silêncio calculados.")
                self.after(0, apply_result)
            except Exception as exc: self.after(0,lambda message=str(exc):self._show_error("Análise de silêncio",message))
            finally: self.after(0, self._finish_video_task)
        threading.Thread(target=task,daemon=True).start()

    def _apply_silence_edits(self) -> None:
        if not getattr(self,"silence_cuts",None) or not self.video_project: return
        if self.video_busy:
            self._show_warning("Edição automática", "Já existe um trabalho de vídeo em andamento.")
            return
        self.video_busy = True
        project=self.video_project; source=project.video_path; cuts=list(self.silence_cuts); self.silence_cuts=[]; self.silence_apply.configure(state="disabled")
        output=EXPORTS_DIR/f"{source.stem}_sem_silencios_{datetime.now():%Y%m%d_%H%M%S_%f}.mp4"; original_subs=list(project.subtitles)
        def task():
            try:
                duration,_,_=probe(source); segments=output_segments(duration,cuts); apply_cuts(source,cuts,output,self._video_progress_update)
                def apply_result() -> None:
                    if self.video_project is not project:
                        output.unlink(missing_ok=True)
                        return
                    project.video_path=output; project.motion_segments=segments; project.subtitles=remap_subtitles(original_subs,cuts)
                    self._refresh_video_table(); self.video_info.configure(text=f"Prévia editada: {output.name} · Auto Mix: {len(segments)} movimentos")
                self.after(0,apply_result)
            except Exception as exc:
                output.unlink(missing_ok=True)
                def show_failure(message=str(exc)) -> None:
                    if self.video_project is project:
                        self.silence_cuts = cuts
                        self.silence_apply.configure(state="normal")
                    self._show_error("Edição automática",message)
                self.after(0, show_failure)
            finally: self.after(0, self._finish_video_task)
        threading.Thread(target=task,daemon=True).start()

    def _refresh_video_table(self) -> None:
        self.video_table.delete(*self.video_table.get_children())
        for index, subtitle in enumerate(self.video_project.subtitles): self.video_table.insert("", "end", iid=str(index), values=(self._caption_time(subtitle.start), self._caption_time(subtitle.end), subtitle.text))
        self.video_status.configure(text=f"{len(self.video_project.subtitles)} legendas prontas. Duplo clique para editar.")
        if hasattr(self,"effects_timeline"): self.effects_timeline.configure(text=f"Timeline de efeitos: {len(self.video_project.subtitles)} blocos · Word Highlight disponível · preview simplificado na exportação.")

    def _apply_dynamic_edit(self) -> None:
        if not self.video_project or not self.video_project.subtitles:
            self._show_warning("Edição dinâmica", "Gere as legendas antes de aplicar efeitos.")
            return
        self.dynamic_edit_enabled.set(True)
        self.video_project.dynamic_edit_enabled = True
        self.video_project.effect_preset = self.effect_preset.get()
        self.video_project.animation = self.effect_animation.get()
        self.video_project.keywords = {item.strip().lower() for item in self.effect_keywords.get().split(",") if item.strip()}
        self.video_project.dynamic_zoom_enabled = self.dynamic_zoom_enabled.get()
        self.video_project.dynamic_zoom_amount = self.dynamic_zoom_amount.get()
        self.video_project.effect_speed = self.effect_speed.get()
        self.video_project.video_motion = self.video_motion.get()
        self.video_project.video_motion_enabled = self.video_motion_enabled.get()
        self.video_project.motion_smoothing_enabled = self.motion_smoothing_enabled.get()
        self.video_project.caption_fixed = self.caption_fixed.get()
        self.video_status.configure(text="Edição dinâmica aplicada. Exporte o vídeo para renderizar os efeitos.")
        self.effects_timeline.configure(text=f"Timeline de efeitos: {len(self.video_project.subtitles)} blocos · preset {self.effect_preset.get()} · animação {self.effect_animation.get()}.")

    @staticmethod
    def _caption_time(value: float) -> str:
        minutes, seconds = divmod(value, 60); return f"{int(minutes):02}:{seconds:05.2f}"

    def _edit_video_subtitle(self, event) -> None:
        row = self.video_table.identify_row(event.y)
        if not row: return
        subtitle = self.video_project.subtitles[int(row)]; modal = FormModal(self, "Editar legenda", 620, 310); entry = modal.text("Texto", subtitle.text, 110)
        def save() -> None:
            value = entry.get("1.0", "end").strip()
            if value: subtitle.text = value; subtitle.words = []; modal.destroy(); self._refresh_video_table()
        modal.actions(save)

    def _export_video_captions(self) -> None:
        if not self.video_project or not self.video_project.subtitles: self._show_warning("Legendas de Vídeo", "Gere as legendas antes de exportar."); return
        filename = filedialog.asksaveasfilename(defaultextension=".srt", filetypes=(("SRT", "*.srt"), ("WebVTT", "*.vtt")))
        if filename: write_captions(self.video_project.subtitles, Path(filename), filename.lower().endswith(".vtt")); self.video_status.configure(text="Arquivo de legendas exportado.")

    def _export_subtitled_video(self) -> None:
        if not self.video_project: self._show_warning("Vídeo", "Selecione um vídeo antes de exportar."); return
        if self.export_with_captions.get() and not self.video_project.subtitles: self._show_warning("Legendas de Vídeo", "Gere as legendas antes de exportar com legendas."); return
        if self.video_busy:
            self._show_warning("Exportação", "Já existe um trabalho de vídeo em andamento.")
            return
        self.video_project.caption_font = self.caption_font.get()
        self.video_project.caption_style = self.caption_style.get()
        self.video_project.caption_position = self.caption_position.get()
        self.video_project.caption_size = self.caption_size.get()
        self.video_project.effect_preset = self.effect_preset.get()
        self.video_project.animation = self.effect_animation.get()
        self.video_project.export_quality = self.export_quality.get()
        self.video_project.dynamic_edit_enabled = self.dynamic_edit_enabled.get()
        self.video_project.dynamic_zoom_enabled = self.dynamic_zoom_enabled.get()
        self.video_project.dynamic_zoom_amount = self.dynamic_zoom_amount.get()
        self.video_project.effect_speed = self.effect_speed.get()
        self.video_project.video_motion = self.video_motion.get()
        self.video_project.video_motion_enabled = self.video_motion_enabled.get()
        self.video_project.motion_smoothing_enabled = self.motion_smoothing_enabled.get()
        self.video_project.caption_fixed = self.caption_fixed.get()
        self.video_project.video_format = self.video_format.get()
        self.video_project.fit_mode = self.video_fit.get()
        self.video_project.keywords = {item.strip().lower() for item in self.effect_keywords.get().split(",") if item.strip()}
        project = copy.deepcopy(self.video_project)
        burn_subtitles = self.export_with_captions.get()
        output = EXPORTS_DIR / f"{project.video_path.stem}_exportado_{datetime.now():%Y%m%d_%H%M%S_%f}.mp4"
        self.video_busy = True
        self.video_export_button.configure(state="disabled", text="EXPORTANDO...")
        def task() -> None:
            try:
                render(project, output, project.video_format, project.fit_mode, self._video_progress_update, burn_subtitles); self.after(0, lambda: self._show_info("Exportação concluída", f"Vídeo salvo em:\n{output}"))
            except Exception as exc: self.after(0, lambda message=str(exc): self._show_error("Falha na exportação", message))
            finally:
                self.after(0, self._finish_video_export)
        threading.Thread(target=task, daemon=True).start()

    def _finish_video_export(self) -> None:
        self.video_busy = False
        if hasattr(self, "video_export_button") and self.video_export_button.winfo_exists():
            self.video_export_button.configure(state="normal", text="EXPORTAR VÍDEO")

    def show_settings(self) -> None:
        frame = self._set_active_view("Configurações", "Configurações", "Conexões, credenciais e caminhos do projeto.")
        box = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"])
        box.grid(row=0, column=0, sticky="ew")
        box.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(box, text="TRELLO", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        self.trello_connection_status = ctk.CTkLabel(box, text="Verificando conexão...", text_color=UI["muted"])
        self.trello_connection_status.grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=4)
        ctk.CTkLabel(box, text="Quadro para o planejamento").grid(row=2, column=0, sticky="w", padx=16, pady=8)
        self.trello_board_menu = ctk.CTkOptionMenu(box, values=["Conecte sua conta primeiro"], state="disabled", command=self._select_trello_board)
        self.trello_board_menu.grid(row=2, column=1, sticky="ew", padx=16, pady=8)
        trello_actions = ctk.CTkFrame(box, fg_color="transparent")
        trello_actions.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 16))
        self.trello_connect_button = ctk.CTkButton(trello_actions, text="CONECTAR AO TRELLO", command=self._connect_trello)
        self.trello_connect_button.pack(side="left")
        self.trello_disconnect_button = ctk.CTkButton(trello_actions, text="Desconectar", fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._disconnect_trello, state="disabled")
        self.trello_disconnect_button.pack(side="left", padx=8)

        ai_box = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"])
        ai_box.grid(row=1, column=0, sticky="ew", pady=(14, 0)); ai_box.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(ai_box, text="IA NEIVA", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        activated = bool(get_secret("NEIVA_AI_CLIENT_TOKEN"))
        self.ai_activation_status = ctk.CTkLabel(ai_box, text="IA ativada neste computador." if activated else "Ative sua licença para usar a IA.", text_color=UI["success"] if activated else UI["muted"])
        self.ai_activation_status.grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=8)
        ctk.CTkLabel(ai_box, text="Código de ativação").grid(row=2, column=0, sticky="w", padx=16, pady=8)
        activation_entry = ctk.CTkEntry(ai_box, placeholder_text="Ex.: NEIVA-XXXX", show="●")
        activation_entry.grid(row=2, column=1, sticky="ew", padx=16, pady=8)

        def activate_ai() -> None:
            code = activation_entry.get().strip()
            if not code:
                self._show_warning("IA Neiva", "Informe o código de ativação fornecido pela Neiva.")
                return
            activate_button.configure(state="disabled", text="ATIVANDO...")
            def task() -> None:
                try:
                    response = requests.post(f"{NEIVA_AI_API_URL}/v1/activate", json={"activation_code": code}, timeout=30)
                    if not response.ok:
                        try: message = response.json().get("detail", response.text)
                        except ValueError: message = response.text
                        raise RuntimeError(message)
                    set_secret("NEIVA_AI_CLIENT_TOKEN", response.json()["access_token"])
                    self.after(0, lambda: (self.ai_activation_status.configure(text="IA ativada neste computador.", text_color=UI["success"]), activation_entry.delete(0, "end"), self._show_info("IA Neiva", "Licença ativada com sucesso.")))
                except Exception as exc:
                    self.after(0, lambda message=str(exc): self._show_error("Ativar IA Neiva", message))
                finally:
                    self.after(0, lambda: activate_button.configure(state="normal", text="ATIVAR IA"))
            threading.Thread(target=task, daemon=True).start()
        activate_button = ctk.CTkButton(ai_box, text="ATIVAR IA", command=activate_ai)
        activate_button.grid(row=3, column=1, sticky="e", padx=16, pady=(0, 16))

        davinci_box = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"])
        davinci_box.grid(row=2, column=0, sticky="ew", pady=(14, 0)); davinci_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(davinci_box, text="DAVINCI RESOLVE", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))
        configured_davinci = self.db.get_setting("DAVINCI_RESOLVE_PATH")
        detected_davinci = find_davinci(configured_davinci)
        davinci_status = f"Configurado: {detected_davinci}" if detected_davinci else "Resolve.exe não encontrado."
        ctk.CTkLabel(davinci_box, text=davinci_status, text_color=UI["success"] if detected_davinci else UI["warning"], wraplength=820, justify="left").grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))
        davinci_actions = ctk.CTkFrame(davinci_box, fg_color="transparent")
        davinci_actions.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 16))
        ctk.CTkButton(davinci_actions, text="DETECTAR AUTOMATICAMENTE", command=self._detect_davinci).pack(side="left")
        ctk.CTkButton(davinci_actions, text="SELECIONAR RESOLVE.EXE", command=self._select_davinci, fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"]).pack(side="left", padx=8)

        ctk.CTkLabel(
            frame,
            text=f"Banco: {self.db.db_path}\nArquivos gerados: {EXPORTS_DIR}\nA chave OpenAI permanece somente no servidor Neiva.",
            text_color=UI["muted"],
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(14, 0))
        self.after(50, self._load_trello_connection)

    def _load_trello_connection(self) -> None:
        app_key, token = get_trello_app_key(), get_secret(self._trello_secret("TRELLO_TOKEN"), self.db.get_setting("TRELLO_TOKEN"))
        if not app_key or not token:
            self.trello_connection_status.configure(text="Nenhuma conta conectada.")
            return
        self.trello_connect_button.configure(state="disabled", text="VERIFICANDO...")
        def task() -> None:
            try:
                identity = get_trello_identity(app_key, token); boards = list_trello_boards(app_key, token)
                self.after(0, lambda: self._display_trello_connection(identity.full_name or identity.username, boards))
            except Exception as exc:
                self.after(0, lambda message=str(exc): self._trello_connection_failed(message))
        threading.Thread(target=task, daemon=True).start()

    def _connect_trello(self) -> None:
        if not self._require_feature("trello", "Integração com Trello"):
            return
        self.trello_connect_button.configure(state="disabled", text="AGUARDANDO LOGIN...")
        self.trello_connection_status.configure(text="Conclua a autorização na janela do navegador.")
        def task() -> None:
            try:
                app_key, token = authorize_trello(); identity = get_trello_identity(app_key, token); boards = list_trello_boards(app_key, token)
                set_secret(self._trello_secret("TRELLO_API_KEY"), app_key); set_secret(self._trello_secret("TRELLO_TOKEN"), token)
                self.db.delete_setting("TRELLO_API_KEY"); self.db.delete_setting("TRELLO_TOKEN")
                self.after(0, lambda: self._display_trello_connection(identity.full_name or identity.username, boards))
            except Exception as exc:
                self.after(0, lambda message=str(exc): self._trello_connection_failed(message, True))
        threading.Thread(target=task, daemon=True).start()

    def _display_trello_connection(self, account_name: str, boards: list[TrelloBoard]) -> None:
        self.trello_connection_status.configure(text=f"● Conectado como {account_name}", text_color=UI["success"])
        self.trello_connect_button.configure(state="normal", text="TROCAR CONTA")
        self.trello_disconnect_button.configure(state="normal")
        self._trello_boards = {board.name: board.board_id for board in boards}
        if not boards:
            self.trello_board_menu.configure(values=["Nenhum quadro aberto"], state="disabled")
            self.trello_board_menu.set("Nenhum quadro aberto"); return
        names = list(self._trello_boards)
        self.trello_board_menu.configure(values=names, state="normal")
        selected_id = get_secret(self._trello_secret("TRELLO_BOARD_ID"), self.db.get_setting("TRELLO_BOARD_ID"))
        selected_name = next((name for name, board_id in self._trello_boards.items() if board_id == selected_id), names[0])
        self.trello_board_menu.set(selected_name)
        self._select_trello_board(selected_name)

    def _trello_connection_failed(self, message: str, show_dialog: bool = False) -> None:
        self.trello_connection_status.configure(text=message, text_color=UI["error"])
        self.trello_connect_button.configure(state="normal", text="CONECTAR AO TRELLO")
        self.trello_disconnect_button.configure(state="disabled")
        if show_dialog: self._show_error("Conexão com Trello", message)

    def _select_trello_board(self, name: str) -> None:
        board_id = getattr(self, "_trello_boards", {}).get(name)
        if not board_id: return
        try:
            set_secret(self._trello_secret("TRELLO_BOARD_ID"), board_id); self.db.delete_setting("TRELLO_BOARD_ID")
        except Exception as exc: self._show_error("Trello", str(exc))

    def _disconnect_trello(self) -> None:
        try:
            for key in ("TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID"):
                set_secret(self._trello_secret(key), ""); self.db.delete_setting(key)
        except Exception as exc:
            self._show_error("Trello", str(exc)); return
        self.show_settings()

    def _month_action_panel(self, frame: ctk.CTkFrame, button_text: str, action):
        panel = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"])
        panel.grid(row=0, column=0, sticky="ew")
        panel.grid_columnconfigure(1, weight=1)

        choices = self._client_choices()
        names = [label for label, _client in choices] or ["Nenhum cliente"]
        client_menu = ctk.CTkOptionMenu(panel, values=names)
        client_menu.set(names[0])
        client_menu.grid(row=0, column=0, padx=16, pady=16)

        month_menu = ctk.CTkOptionMenu(panel, values=MONTHS)
        month_menu.set(MONTHS[self.current_month - 1])
        month_menu.grid(row=0, column=1, sticky="w", padx=8, pady=16)

        year_entry = ctk.CTkEntry(panel, width=100)
        year_entry.insert(0, str(self.current_year))
        year_entry.grid(row=0, column=2, padx=8, pady=16)

        def run_action() -> None:
            client = self._get_client_by_name(client_menu.get())
            if client is None or client.id is None:
                self._show_warning("Atenção", "Cadastre um cliente primeiro.")
                return
            year = self._parse_year(year_entry.get())
            if year is None:
                self._show_error("Ano inválido", "Informe um ano válido.")
                return
            month = MONTHS.index(month_menu.get()) + 1
            action(client, year, month)

        button = ctk.CTkButton(panel, text=button_text, command=run_action)
        button.grid(row=0, column=3, padx=16, pady=16)
        return button

    def _parse_year(self, value: str) -> int | None:
        try:
            year = int(value)
            return year if 1 <= year <= 9999 else None
        except ValueError:
            return None

    def _open_client_modal(self, client: Client | None = None) -> None:
        if client is None and self.plan.max_clients is not None and len(self.db.search_clients()) >= self.plan.max_clients:
            self._show_warning("Limite do plano", f"O plano {self.plan.name} permite até {self.plan.max_clients} cliente. Faça upgrade para cadastrar mais.")
            return
        modal = FormModal(self, "Cliente", width=620, height=640)
        fields = {
            "name": modal.entry("Nome", client.name if client else ""),
            "niche": modal.entry("Nicho", client.niche if client else ""),
            "instagram": modal.entry("Instagram", client.instagram if client else ""),
            "posting_frequency": modal.entry("Frequência de postagem", client.posting_frequency if client else ""),
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
            )
            if client:
                self.db.update_client(payload)
            else:
                self.selected_client_id = self.db.create_client(payload)
            modal.destroy()
            self._refresh_active_view()

        modal.actions(save)

    def _open_day_modal(self, day: int) -> None:
        if self.selected_client_id is None:
            return
        post_date = f"{self.current_year:04d}-{self.current_month:02d}-{day:02d}"
        modal = FormModal(self, f"Conteúdos de {day:02d}/{self.current_month:02d}", width=760, height=720)
        list_frame = ctk.CTkFrame(modal.body, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, pady=(0, 12))

        def render_posts() -> None:
            for child in list_frame.winfo_children():
                child.destroy()

            posts = self.db.get_posts_for_day(self.selected_client_id, post_date)
            if not posts:
                ctk.CTkLabel(list_frame, text="Nenhum conteúdo neste dia.", text_color=UI["muted"]).pack(anchor="w", pady=8)

            for post in posts:
                item = ctk.CTkFrame(list_frame, fg_color=UI["surface_alt"], corner_radius=8)
                item.pack(fill="x", pady=5)
                ctk.CTkLabel(item, text=post.title, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(8, 0))
                ctk.CTkLabel(
                    item,
                    text=f"{post.content_type} | {post.platform} | {post.status}",
                    text_color=UI["muted"],
                ).pack(anchor="w", padx=12, pady=(0, 8))
                actions = ctk.CTkFrame(item, fg_color="transparent")
                actions.pack(anchor="e", padx=10, pady=(0, 10))
                ctk.CTkButton(
                    actions,
                    text="Editar",
                    width=82,
                    command=lambda p=post: self._open_post_modal(post_date, p, modal),
                ).pack(side="left", padx=4)
                ctk.CTkButton(
                    actions,
                    text="Excluir",
                    width=82,
                    fg_color=UI["error"],
                    hover_color="#A91F30",
                    command=lambda p=post: self._delete_post(p, modal),
                ).pack(side="left", padx=4)

        render_posts()
        ctk.CTkButton(modal.body, text="Adicionar conteúdo", command=lambda: self._open_post_modal(post_date, None, modal)).pack(
            fill="x", pady=(0, 8)
        )
        ctk.CTkButton(modal.body, text="Fechar", fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=modal.destroy).pack(fill="x")

    def _open_post_modal(self, post_date: str, post: Post | None, parent_modal: ctk.CTkToplevel | None = None) -> None:
        if post is None and self.plan.max_monthly_posts is not None:
            year, month = (int(value) for value in post_date.split("-")[:2])
            if self.db.count_posts_month(year, month) >= self.plan.max_monthly_posts:
                self._show_warning("Limite do plano", f"O plano {self.plan.name} permite até {self.plan.max_monthly_posts} conteúdos por mês. Seus conteúdos existentes continuam disponíveis.")
                return
        modal = FormModal(self, "Conteúdo", width=720, height=760)
        title = modal.entry("Título", post.title if post else "")
        content_type = modal.option("Tipo", CONTENT_TYPES, post.content_type if post else CONTENT_TYPES[0])
        platform = modal.option("Plataforma", PLATFORMS, post.platform if post else PLATFORMS[0])
        status = modal.option("Status", STATUSES, post.status if post else STATUSES[0])
        description = modal.text("Descrição", post.description if post else "", height=90)
        caption = modal.text("Legenda", post.caption if post else "", height=120)
        cta = modal.text("CTA", post.cta if post else "", height=70)
        operation_id = uuid.uuid4().hex

        def save() -> None:
            if self.selected_client_id is None:
                return
            if not title.get().strip():
                self._show_warning("Validação", "Título é obrigatório.")
                return
            payload = Post(
                id=post.id if post else None,
                client_id=self.selected_client_id,
                post_date=post_date,
                content_type=content_type.get(),
                platform=platform.get(),
                title=title.get(),
                description=description.get("1.0", "end").strip(),
                caption=caption.get("1.0", "end").strip(),
                cta=cta.get("1.0", "end").strip(),
                status=status.get(),
                operation_id=post.operation_id if post else operation_id,
            )
            if post:
                self.db.update_post(payload)
            else:
                self.db.create_post(payload)
            modal.destroy()
            if parent_modal:
                parent_modal.destroy()
            self.show_calendar()

        modal.actions(save)

    def _delete_client(self, client: Client) -> None:
        if client.id is None:
            return
        if messagebox.askyesno("Excluir cliente", f"Excluir {client.name} e todas as postagens?"):
            self.db.delete_client(client.id)
            if self.selected_client_id == client.id:
                self.selected_client_id = None
            self._refresh_active_view()

    def _delete_post(self, post: Post, modal: ctk.CTkToplevel) -> None:
        if post.id is None:
            return
        if messagebox.askyesno("Excluir conteúdo", f"Excluir '{post.title}'?"):
            self.db.delete_post(post.id)
            modal.destroy()
            self.show_calendar()

    def _select_client_calendar(self, client: Client) -> None:
        self.selected_client_id = client.id
        self.show_calendar()

    def _set_selected_client_by_name(self, name: str) -> None:
        client = self._get_client_by_name(name)
        self.selected_client_id = client.id if client else None
        self.show_calendar()

    def _previous_month(self) -> None:
        self.current_month -= 1
        if self.current_month == 0:
            self.current_month = 12
            self.current_year -= 1
        self.show_calendar()

    def _next_month(self) -> None:
        self.current_month += 1
        if self.current_month == 13:
            self.current_month = 1
            self.current_year += 1
        self.show_calendar()

    def _export_pdf(self, client: Client, year: int, month: int) -> None:
        if client.id is None:
            return
        usage_period = date.today().strftime("%Y-%m")
        usage_key = f"PLAN_PDF_EXPORTS_{usage_period}"
        if self.plan.max_monthly_pdfs is not None and int(self.db.get_setting(usage_key, "0")) >= self.plan.max_monthly_pdfs:
            self._show_warning("Limite do plano", f"O plano {self.plan.name} permite {self.plan.max_monthly_pdfs} PDF por mês. Faça upgrade para exportações ilimitadas.")
            return
        try:
            path = self.pdf.export_month(client, self.db.get_posts_for_client_month(client.id, year, month), year, month)
        except Exception as exc:
            self._show_error("Erro ao exportar PDF", str(exc))
            return
        if self.plan.max_monthly_pdfs is not None:
            self.db.set_setting(usage_key, str(int(self.db.get_setting(usage_key, "0")) + 1))
        self._open_pdf_preview(path)
        self._show_info("PDF exportado", f"Arquivo salvo e aberto para visualização:\n{path}")

    def _open_pdf_preview(self, path: Path) -> None:
        try:
            os.startfile(path)
        except AttributeError:
            webbrowser.open(path.resolve().as_uri())
        except OSError as exc:
            self._show_warning("Visualização do PDF", f"O PDF foi salvo, mas não foi possível abrir automaticamente:\n{exc}")

    def _send_to_trello(self, client: Client, year: int, month: int) -> None:
        if not self._require_feature("trello", "Integração com Trello"):
            return
        if client.id is None:
            return
        posts = self.db.get_posts_for_client_month(client.id, year, month)
        if not posts:
            self._show_warning("Trello", "Não há posts neste mês.")
            return
        selected_board_id = get_secret(self._trello_secret("TRELLO_BOARD_ID"), self.db.get_setting("TRELLO_BOARD_ID"))
        if not selected_board_id:
            self._show_warning("Trello", "Conecte sua conta e selecione um quadro em Configurações antes de enviar.")
            return
        pending_posts = self.db.get_posts_pending_trello(client.id, year, month, selected_board_id)
        if not pending_posts:
            self._show_info("Trello", "Todos os posts deste mês já foram enviados ao Trello.")
            return
        list_name = f"{client.name} - {MONTHS[month - 1]} {year}"
        button = getattr(self, "trello_action_button", None)
        if button and button.winfo_exists():
            button.configure(state="disabled", text="Enviando...")

        def finish(message: str | None = None, error: str | None = None) -> None:
            try:
                if button and button.winfo_exists():
                    button.configure(state="normal", text="Enviar para Trello")
            except TclError:
                pass
            if error:
                self._show_error("Erro no Trello", error)
            elif message:
                self._show_info("Trello", message)

        def task() -> None:
            created: dict[int, str] = {}
            try:
                settings = {
                    "TRELLO_API_KEY": get_trello_app_key(),
                    "TRELLO_TOKEN": get_secret(self._trello_secret("TRELLO_TOKEN"), self.db.get_setting("TRELLO_TOKEN")),
                    "TRELLO_BOARD_ID": selected_board_id,
                }
                account = current_account()
                settings["TRELLO_SOURCE_ID"] = account.account_id if account else hashlib.sha256(str(self.db.db_path.resolve()).encode("utf-8")).hexdigest()[:16]
                api = TrelloAPI(TrelloConfig.from_environment(settings))
                list_setting = f"TRELLO_LIST_{settings['TRELLO_BOARD_ID']}_{client.id}_{year}_{month}"
                list_id = self.db.get_setting(list_setting)
                if not list_id:
                    list_id = api.get_or_create_list(list_name)
                    self.db.set_setting(list_setting, list_id)
                for post in pending_posts:
                    if post.id is not None:
                        card_id = api.get_or_create_card(list_id, post)
                        self.db.update_post_trello_card(post.id, card_id, selected_board_id)
                        created[post.id] = card_id
            except Exception as exc:
                detail = f"{exc} ({len(created)} card(s) enviado(s) antes da falha.)" if created else str(exc)
                self.after(0, lambda message=detail: finish(error=message))
                return
            self.after(0, lambda count=len(created): finish(message=f"{count} cards criados com sucesso."))

        threading.Thread(target=task, daemon=True).start()

    def _finish_youtube_download(self, result: Path) -> None:
        self.video_project = VideoProject(result)
        self.youtube_progress.set(1)
        self.youtube_status.configure(text="Download concluído. O vídeo já está disponível nas etapas Legendas e Cortes.")
        self.youtube_download_button.configure(state="normal")
        self._show_info("Download concluído", f"Arquivo salvo e carregado no Estúdio:\n{result}")

    def _refresh_active_view(self) -> None:
        views = {
            "Dashboard": self.show_dashboard,
            "Clientes": self.show_clients,
            "Planejamento": self.show_planning,
            "Estúdio de Vídeo": self.show_video_studio,
            "Configurações": self.show_settings,
        }
        views.get(self.active_view, self.show_dashboard)()


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
