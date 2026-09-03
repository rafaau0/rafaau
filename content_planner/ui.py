from __future__ import annotations

import calendar
import json
import os
import sys
import webbrowser
import threading
from datetime import date, datetime
from pathlib import Path
from tkinter import DoubleVar, IntVar, TclError, filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image

from .database import Client, Database, Post
from .pdf_generator import PDFGenerator
from .trello_api import TrelloAPI, TrelloConfig
from .trello_auth import TrelloBoard, authorize as authorize_trello, get_app_key as get_trello_app_key, get_identity as get_trello_identity, list_boards as list_trello_boards
from .video_subtitles import VideoError, VideoProject, probe, render, transcribe, write_captions
from .youtube_downloader import DownloadError, download as download_youtube, duration as youtube_duration, fetch_info, is_youtube_url
from .clip_finder import ClipSuggestion, find_suggestions
from .clip_ai import analyze_cuts
from .encarte_service import export_files as export_encarte_files, extract_photos, generate as generate_encarte, prepare as prepare_encarte
from .secrets import get_secret, set_secret
from .silence_editor import SilenceSettings, apply_cuts, detect_silences, output_segments, plan_cuts, remap_subtitles


CONTENT_TYPES = ["Reels", "Story", "Carrossel", "Feed", "Promoção"]
PLATFORMS = ["Instagram", "Facebook", "TikTok", "LinkedIn", "YouTube", "Pinterest"]
STATUSES = ["Pendente", "Em andamento", "Concluído"]
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
UI = {
    "canvas": "#F7F8FA", "sidebar": "#FFFFFF", "surface": "#FFFFFF",
    "surface_alt": "#F0F2F5", "border": "#DDE1E7", "text": "#17191F",
    "muted": "#68707D", "accent": "#FF263D", "accent_hover": "#D91E32",
    "success": "#168A5B", "warning": "#C77A08", "error": "#C92A3D",
    "secondary": "#E7EAF0", "secondary_hover": "#D8DDE5", "selection": "#FFF0F2",
}


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
        self.sidebar = ctk.CTkFrame(self, width=244, corner_radius=0, fg_color=UI["sidebar"])
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
            ("Encarte de Ofertas", self.show_offer_flyer),
            ("Configurações", self.show_settings),
        ]
        self.nav_buttons: list[ctk.CTkButton] = []
        for label, handler in self._navigation:
            button = ctk.CTkButton(
                sidebar,
                text=label,
                height=40,
                corner_radius=8,
                anchor="w",
                fg_color="transparent",
                hover_color=UI["surface_alt"],
                text_color=UI["muted"],
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                command=handler,
            )
            button.pack(fill="x", padx=18, pady=6)
            self.nav_buttons.append(button)

        ctk.CTkLabel(
            sidebar,
            text="Planejamento editorial,\nprodução e aprovação\nem um só lugar.",
            justify="left",
            text_color=UI["muted"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(side="bottom", padx=22, pady=24, anchor="w")

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
        ctk.CTkLabel(header, text=title, text_color=UI["text"], font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold")).grid(row=0, column=0, sticky="w")
        if subtitle:
            ctk.CTkLabel(header, text=subtitle, text_color=UI["muted"], font=ctk.CTkFont(family="Segoe UI", size=13)).grid(row=1, column=0, sticky="w", pady=(4, 0))

        frame = ctk.CTkScrollableFrame(self.content, fg_color=UI["canvas"])
        frame.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _clients(self) -> list[Client]:
        return self.db.search_clients()

    def _get_client_by_name(self, name: str) -> Client | None:
        return next((client for client in self._clients() if client.name == name), None)

    def _set_active_view(self, view_name: str, title: str, subtitle: str) -> ctk.CTkFrame:
        self.active_view = view_name
        if hasattr(self, "mobile_view"):
            self.mobile_view.set(view_name)
        for label, button in zip((item[0] for item in self._navigation), self.nav_buttons):
            selected = label == view_name
            button.configure(fg_color=UI["surface_alt"] if selected else "transparent", text_color=UI["text"] if selected else UI["muted"])
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

        cards = ctk.CTkFrame(frame, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        for index in range(4):
            cards.grid_columnconfigure(index, weight=1)

        metrics = [
            ("Clientes", stats["clients"], "#2563EB"),
            ("Conteúdos", stats["posts"], "#7C3AED"),
            ("Pendentes", stats["pending"], "#B45309"),
            ("Concluídos", stats["done"], "#047857"),
        ]
        for col, (label, value, color) in enumerate(metrics):
            card = ctk.CTkFrame(cards, fg_color=UI["surface"], corner_radius=12, border_width=1, border_color=UI["border"])
            card.grid(row=0, column=col, sticky="ew", padx=8)
            ctk.CTkLabel(card, text=label.upper(), text_color=UI["muted"], font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold")).pack(anchor="w", padx=18, pady=(16, 2))
            ctk.CTkLabel(card, text=str(value), text_color=color, font=ctk.CTkFont(family="Segoe UI", size=34, weight="bold")).pack(
                anchor="w", padx=18, pady=(0, 18)
            )

        quick = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=12, border_width=1, border_color=UI["border"])
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

        clients = self._clients()
        names = [client.name for client in clients] or ["Nenhum cliente"]
        if self.selected_client_id is None and clients:
            self.selected_client_id = clients[0].id

        selected_name = next((client.name for client in clients if client.id == self.selected_client_id), names[0])
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
        handlers = {
            "Importar": self.show_youtube_downloader,
            "Legendas": self.show_video_subtitles,
            "Cortes": self.show_clip_finder,
        }
        handlers.get(self.video_studio_section, self.show_youtube_downloader)()

    def _video_studio_frame(self, section: str, subtitle: str) -> ctk.CTkFrame:
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
        self.video_model = ctk.StringVar(value="base")
        self.video_format = ctk.StringVar(value="Original")
        self.video_fit = ctk.StringVar(value="Preencher")
        self.caption_font = ctk.StringVar(value="Arial")
        self.caption_style = ctk.StringVar(value="Viral")
        self.caption_position = ctk.StringVar(value="Centro")
        self.caption_size = IntVar(value=42)
        self.export_with_captions = ctk.BooleanVar(value=True)
        self.effect_preset = ctk.StringVar(value="Viral")
        self.effect_animation = ctk.StringVar(value="Word Highlight")
        self.export_quality = ctk.StringVar(value="Alta")
        self.effect_keywords = ctk.StringVar(value="")
        self.dynamic_edit_enabled = ctk.BooleanVar(value=True)
        self.dynamic_zoom_enabled = ctk.BooleanVar(value=True)
        self.dynamic_zoom_amount = IntVar(value=8)
        self.effect_speed = DoubleVar(value=1.0)
        self.video_motion = ctk.StringVar(value="Auto Mix")
        self.video_motion_enabled = ctk.BooleanVar(value=True)
        self.motion_smoothing_enabled = ctk.BooleanVar(value=True)
        self.caption_fixed = ctk.BooleanVar(value=True)
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
        self.caption_size_label = ctk.CTkLabel(settings, text="42", text_color=UI["warning"])
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
        self.zoom_amount_label=ctk.CTkLabel(effects,text="8%",text_color=UI["warning"]); self.zoom_amount_label.grid(row=6,column=2,padx=4,sticky="w")
        ctk.CTkSlider(effects,from_=1,to=15,number_of_steps=14,variable=self.dynamic_zoom_amount,command=lambda value:self.zoom_amount_label.configure(text=f"{round(value)}%")).grid(row=6,column=3,padx=14,pady=(0,8),sticky="ew")
        ctk.CTkCheckBox(effects,text="Movimento do vídeo",variable=self.video_motion_enabled).grid(row=7,column=0,padx=14,sticky="w")
        ctk.CTkOptionMenu(effects,variable=self.video_motion,values=["Auto Mix","Zoom In","Zoom Out","Pan Esquerda","Pan Direita","Vertical"]).grid(row=7,column=1,columnspan=2,padx=14,pady=(0,8),sticky="ew")
        ctk.CTkCheckBox(effects,text="Suavizar movimentos (48 FPS)",variable=self.motion_smoothing_enabled).grid(row=8,column=0,columnspan=2,padx=14,pady=(0,8),sticky="w")
        ctk.CTkLabel(effects,text="Velocidade").grid(row=8,column=2,padx=(0,4),sticky="e")
        self.effect_speed_label=ctk.CTkLabel(effects,text="1,0x",text_color=UI["warning"]); self.effect_speed_label.grid(row=8,column=3,padx=(0,14),sticky="e")
        ctk.CTkSlider(effects,from_=0.5,to=2.0,number_of_steps=15,variable=self.effect_speed,command=lambda value:self.effect_speed_label.configure(text=f"{value:.1f}x".replace(".",","))).grid(row=9,column=0,columnspan=4,padx=14,pady=(0,8),sticky="ew")
        self.effects_timeline=ctk.CTkLabel(effects,text="Timeline de vídeo: será atualizada ao gerar legendas.",text_color=UI["muted"]); self.effects_timeline.grid(row=10,column=0,columnspan=4,padx=14,pady=(0,12),sticky="w")
        bar = ctk.CTkFrame(frame, fg_color="transparent"); bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.video_generate_button = ctk.CTkButton(bar, text="Gerar legendas", command=self._generate_video_subtitles)
        self.video_generate_button.pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Exportar SRT / VTT", fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._export_video_captions).pack(side="left")
        ctk.CTkButton(bar, text="EXPORTAR VÍDEO", command=self._export_subtitled_video).pack(side="right")
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

    def show_offer_flyer(self) -> None:
        frame = self._set_active_view("Encarte de Ofertas", "Encarte de Ofertas", "Preencha modelos PSD com produtos, preços e fotos. Requer Adobe Photoshop instalado.")
        self.encarte_psd = ctk.StringVar(); self.encarte_sheet = ctk.StringVar(); self.encarte_photos = ctk.StringVar(); self.encarte_output = ctk.StringVar(value=str(ROOT_DIR / "exports" / "encartes")); self.encarte_period = ctk.StringVar()
        fields = (("Modelo PSD", self.encarte_psd, self._pick_encarte_psd), ("Planilha de produtos", self.encarte_sheet, self._pick_encarte_sheet), ("Pasta de fotos", self.encarte_photos, self._pick_encarte_photos), ("Pasta de saída", self.encarte_output, self._pick_encarte_output))
        for row, (label, variable, command) in enumerate(fields):
            ctk.CTkLabel(frame, text=label, text_color=UI["text"]).grid(row=row * 2, column=0, sticky="w", pady=(5, 2))
            line = ctk.CTkFrame(frame, fg_color="transparent"); line.grid(row=row * 2 + 1, column=0, sticky="ew", pady=(0, 7)); line.grid_columnconfigure(0, weight=1)
            ctk.CTkEntry(line, textvariable=variable, height=36).grid(row=0, column=0, sticky="ew", padx=(0, 8))
            ctk.CTkButton(line, text="Selecionar", width=105, fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=command).grid(row=0, column=1)
        ctk.CTkLabel(frame, text="Período da oferta", text_color=UI["text"]).grid(row=8, column=0, sticky="w", pady=(5, 2))
        ctk.CTkEntry(frame, textvariable=self.encarte_period, placeholder_text="Ex.: 03 A 06/08/2026", height=36).grid(row=9, column=0, sticky="ew", pady=(0, 9))
        bar = ctk.CTkFrame(frame, fg_color="transparent"); bar.grid(row=10, column=0, sticky="ew", pady=(2, 9))
        self.encarte_validate_button = ctk.CTkButton(bar, text="VALIDAR PRODUTOS", command=self._validate_encarte)
        self.encarte_validate_button.pack(side="left")
        self.encarte_extract_button = ctk.CTkButton(bar, text="EXTRAIR FOTOS DO PSD", fg_color=UI["warning"], command=self._extract_encarte_photos)
        self.encarte_extract_button.pack(side="left", padx=8)
        ctk.CTkButton(bar, text="EXPORTAR JPG / PDF", fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._export_encarte_files).pack(side="left")
        self.encarte_generate_button = ctk.CTkButton(bar, text="GERAR ENCARTE", fg_color=UI["success"], command=self._generate_encarte)
        self.encarte_generate_button.pack(side="right")
        self.encarte_status = ctk.CTkLabel(frame, text="Selecione os arquivos para iniciar.", text_color=UI["muted"]); self.encarte_status.grid(row=11, column=0, sticky="w")
        self.encarte_progress = ctk.CTkProgressBar(frame); self.encarte_progress.grid(row=12, column=0, sticky="ew", pady=(4, 10)); self.encarte_progress.set(0)
        self.encarte_list = ctk.CTkTextbox(frame, height=235, fg_color=UI["surface"]); self.encarte_list.grid(row=13, column=0, sticky="ew")
        self.encarte_products = []

    def _pick_encarte_psd(self) -> None:
        value = filedialog.askopenfilename(filetypes=(("Photoshop", "*.psd"),));
        if value: self.encarte_psd.set(value)

    def _pick_encarte_sheet(self) -> None:
        value = filedialog.askopenfilename(filetypes=(("Planilha Excel", "*.xlsx"),));
        if value: self.encarte_sheet.set(value)

    def _pick_encarte_photos(self) -> None:
        value = filedialog.askdirectory();
        if value: self.encarte_photos.set(value)

    def _pick_encarte_output(self) -> None:
        value = filedialog.askdirectory(initialdir=self.encarte_output.get() or str(ROOT_DIR / "exports"));
        if value: self.encarte_output.set(value)

    def _encarte_paths(self) -> tuple[Path, Path, Path, Path]:
        return tuple(Path(value.get().strip()) for value in (self.encarte_psd, self.encarte_sheet, self.encarte_photos, self.encarte_output))

    def _encarte_progress_update(self, percent: int, text: str) -> None:
        self.after(0, lambda: (self.encarte_progress.set(max(0, min(100, percent)) / 100), self.encarte_status.configure(text=text)))

    def _validate_encarte(self) -> None:
        try: paths = self._encarte_paths()
        except Exception: self._show_warning("Encarte", "Preencha os caminhos necessários."); return
        self.encarte_status.configure(text="Lendo planilha e procurando fotos…"); self.encarte_validate_button.configure(state="disabled")
        def task() -> None:
            try:
                products, report = prepare_encarte(*paths)
                self.after(0, lambda: self._display_encarte_validation(products, report))
            except Exception as exc: self.after(0, lambda message=str(exc): self._show_error("Validação do encarte", message))
            finally: self.after(0, lambda: self.encarte_validate_button.configure(state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def _display_encarte_validation(self, products, report) -> None:
        self.encarte_products = products; self.encarte_report = report; found = sum(bool(item.image) for item in products)
        lines = [f"Produtos: {len(products)} · Fotos encontradas: {found} · Fotos faltantes: {len(products) - found}", ""]
        lines.extend(f"{item.position:02d}. {item.description} — {item.price or 'sem preço'} — {item.image.name if item.image else 'SEM FOTO'}" for item in products)
        if report.errors: lines.extend(["", "ERROS:", *report.errors])
        if report.warnings: lines.extend(["", "AVISOS:", *report.warnings])
        self.encarte_list.delete("1.0", "end"); self.encarte_list.insert("1.0", "\n".join(lines))
        self.encarte_progress.set(1 if report.valid else 0); self.encarte_status.configure(text="Validação concluída." if report.valid else "Corrija os erros antes de gerar o encarte.")

    def _generate_encarte(self) -> None:
        if not self.encarte_products: self._validate_encarte(); self._show_warning("Encarte", "Valide os produtos e fotos antes de gerar."); return
        if not getattr(self, "encarte_report", None) or not self.encarte_report.valid:
            self._show_warning("Encarte", "Corrija os erros da validação antes de gerar."); return
        psd, sheet, photos, output = self._encarte_paths()
        self.encarte_generate_button.configure(state="disabled")
        def task() -> None:
            try:
                result = generate_encarte(psd, self.encarte_products, self.encarte_period.get(), output, self._encarte_progress_update)
                self.after(0, lambda: self._show_info("Encarte concluído", f"PSD criado em:\n{result}"))
            except Exception as exc: self.after(0, lambda message=str(exc): self._show_error("Erro ao gerar encarte", message))
            finally: self.after(0, lambda: self.encarte_generate_button.configure(state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def _extract_encarte_photos(self) -> None:
        psd = self.encarte_psd.get().strip(); photos = self.encarte_photos.get().strip()
        if not psd or not photos: self._show_warning("Extrair fotos", "Selecione o PSD e a pasta de fotos."); return
        self.encarte_extract_button.configure(state="disabled")
        def task() -> None:
            try:
                exported = extract_photos(Path(psd), Path(photos), self._encarte_progress_update)
                self.after(0, lambda: self._show_info("Fotos extraídas", f"{len(exported)} fotos salvas em:\n{photos}"))
            except Exception as exc: self.after(0, lambda message=str(exc): self._show_error("Extrair fotos", message))
            finally: self.after(0, lambda: self.encarte_extract_button.configure(state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def _export_encarte_files(self) -> None:
        filename = filedialog.askopenfilename(title="Selecione o encarte PSD", initialdir=self.encarte_output.get() or str(ROOT_DIR / "exports"), filetypes=(("Photoshop", "*.psd"),))
        if not filename: return
        self.encarte_status.configure(text="Exportando JPG e PDF pelo Photoshop…")
        def task() -> None:
            try:
                jpg, pdf = export_encarte_files(Path(filename))
                self.after(0, lambda: self._show_info("Exportação concluída", f"JPG:\n{jpg}\n\nPDF:\n{pdf}"))
            except Exception as exc: self.after(0, lambda message=str(exc): self._show_error("Exportar encarte", message))
        threading.Thread(target=task, daemon=True).start()

    def show_clip_finder(self) -> None:
        frame = self._video_studio_frame("Cortes", "Encontre os trechos com melhor potencial no vídeo atual ou em um link do YouTube.")
        self.clip_url = ctk.CTkEntry(frame, placeholder_text="Link do YouTube (opcional se já houver um vídeo carregado)", height=42)
        self.clip_url.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        actions = ctk.CTkFrame(frame, fg_color="transparent"); actions.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkButton(actions, text="Colar", width=90, fg_color=UI["secondary"], hover_color=UI["secondary_hover"], text_color=UI["text"], command=self._paste_clip_url).pack(side="left")
        self.clip_model = ctk.StringVar(value="base")
        self.clip_use_ai = ctk.BooleanVar(value=bool(get_secret("NEIVA_AI_API_URL")) and bool(get_secret("NEIVA_AI_CLIENT_TOKEN")))
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
        api_url = get_secret("NEIVA_AI_API_URL") if use_ai else ""
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
                    folder = ROOT_DIR / "exports" / "downloads"
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
        folder = ROOT_DIR / "exports" / "analises_de_cortes"; folder.mkdir(parents=True, exist_ok=True)
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
        self.youtube_folder = ctk.CTkEntry(folder, height=40); self.youtube_folder.insert(0, str(ROOT_DIR / "exports" / "downloads")); self.youtube_folder.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(folder, text="Escolher pasta", command=self._choose_youtube_folder).grid(row=0, column=1)
        self.youtube_status = ctk.CTkLabel(frame, text="Pronto para baixar.", text_color=UI["muted"]); self.youtube_status.grid(row=5, column=0, sticky="w")
        self.youtube_progress = ctk.CTkProgressBar(frame); self.youtube_progress.grid(row=6, column=0, sticky="ew", pady=(4, 5)); self.youtube_progress.set(0)
        self.youtube_details = ctk.CTkLabel(frame, text="0%", text_color=UI["muted"]); self.youtube_details.grid(row=7, column=0, sticky="w")
        self.youtube_download_button = ctk.CTkButton(frame, text="BAIXAR VÍDEO", height=48, font=ctk.CTkFont(size=16, weight="bold"), command=self._start_youtube_download); self.youtube_download_button.grid(row=8, column=0, sticky="ew", pady=(16, 0))

    def _choose_youtube_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.youtube_folder.get() or str(ROOT_DIR / "exports"))
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
        def task() -> None:
            try:
                self.video_project.subtitles = transcribe(self.video_project.video_path, self.video_model.get(), 5, self._video_progress_update); self.after(0, self._refresh_video_table)
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
        try: return SilenceSettings(float(self.silence_threshold.get()),float(self.silence_duration.get()),float(self.silence_margin.get()),float(self.silence_margin.get()),self.silence_mode.get())
        except ValueError: raise VideoError("Informe números válidos para duração, margem e volume.")

    def _analyze_silences(self) -> None:
        if not self.video_project: self._show_warning("Edição automática","Selecione um vídeo primeiro."); return
        try: settings=self._silence_settings()
        except Exception as exc: self._show_error("Edição automática",str(exc)); return
        def task():
            try:
                silences=detect_silences(self.video_project.video_path,settings.threshold_db,settings.min_duration); self.silence_cuts=plan_cuts(silences,settings); duration,_,_=probe(self.video_project.video_path); final=duration-sum(c.end-c.start for c in self.silence_cuts)
                self.after(0,lambda:(self.silence_summary.configure(text=f"Silêncios encontrados: {len(silences)} · Tempo original: {duration:.1f}s · Final estimado: {final:.1f}s"),self.silence_apply.configure(state="normal" if self.silence_cuts else "disabled"),self.video_status.configure(text="Timeline: cortes de silêncio calculados.")))
            except Exception as exc: self.after(0,lambda message=str(exc):self._show_error("Análise de silêncio",message))
        threading.Thread(target=task,daemon=True).start()

    def _apply_silence_edits(self) -> None:
        if not getattr(self,"silence_cuts",None) or not self.video_project: return
        source=self.video_project.video_path; output=ROOT_DIR/"exports"/f"{source.stem}_sem_silencios.mp4"; original_subs=list(self.video_project.subtitles)
        def task():
            try:
                duration,_,_=probe(source); segments=output_segments(duration,self.silence_cuts); apply_cuts(source,self.silence_cuts,output,self._video_progress_update); self.video_project.video_path=output; self.video_project.motion_segments=segments; self.video_project.subtitles=remap_subtitles(original_subs,self.silence_cuts); self.after(0,lambda:(self._refresh_video_table(),self.video_info.configure(text=f"Prévia editada: {output.name} · Auto Mix: {len(segments)} movimentos")))
            except Exception as exc: self.after(0,lambda message=str(exc):self._show_error("Edição automática",message))
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
            if value: subtitle.text = value; modal.destroy(); self._refresh_video_table()
        modal.actions(save)

    def _export_video_captions(self) -> None:
        if not self.video_project or not self.video_project.subtitles: self._show_warning("Legendas de Vídeo", "Gere as legendas antes de exportar."); return
        filename = filedialog.asksaveasfilename(defaultextension=".srt", filetypes=(("SRT", "*.srt"), ("WebVTT", "*.vtt")))
        if filename: write_captions(self.video_project.subtitles, Path(filename), filename.lower().endswith(".vtt")); self.video_status.configure(text="Arquivo de legendas exportado.")

    def _export_subtitled_video(self) -> None:
        if not self.video_project or not self.video_project.subtitles: self._show_warning("Legendas de Vídeo", "Gere as legendas antes de exportar."); return
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
        self.video_project.keywords = {item.strip().lower() for item in self.effect_keywords.get().split(",") if item.strip()}
        output = ROOT_DIR / "exports" / f"{self.video_project.video_path.stem}_legendado.mp4"
        def task() -> None:
            try:
                render(self.video_project, output, self.video_format.get(), self.video_fit.get(), self._video_progress_update, self.export_with_captions.get()); self.after(0, lambda: self._show_info("Exportação concluída", f"Vídeo salvo em:\n{output}"))
            except Exception as exc: self.after(0, lambda message=str(exc): self._show_error("Falha na exportação", message))
        threading.Thread(target=task, daemon=True).start()

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
        ctk.CTkLabel(ai_box, text="URL da IA").grid(row=1, column=0, sticky="w", padx=16, pady=8)
        ai_url_entry = ctk.CTkEntry(ai_box, placeholder_text="https://sua-api.onrender.com")
        ai_url_entry.insert(0, get_secret("NEIVA_AI_API_URL"))
        ai_url_entry.grid(row=1, column=1, sticky="ew", padx=16, pady=8)
        ctk.CTkLabel(ai_box, text="Chave de acesso").grid(row=2, column=0, sticky="w", padx=16, pady=8)
        ai_token_entry = ctk.CTkEntry(ai_box, show="●")
        ai_token_entry.insert(0, get_secret("NEIVA_AI_CLIENT_TOKEN"))
        ai_token_entry.grid(row=2, column=1, sticky="ew", padx=16, pady=8)

        def save_ai_settings() -> None:
            try:
                set_secret("NEIVA_AI_API_URL", ai_url_entry.get().strip().rstrip("/"))
                set_secret("NEIVA_AI_CLIENT_TOKEN", ai_token_entry.get().strip())
                self._show_info("IA Neiva", "Configuração salva no cofre do Windows.")
            except Exception as exc: self._show_error("IA Neiva", str(exc))
        ctk.CTkButton(ai_box, text="Salvar configuração", command=save_ai_settings).grid(row=3, column=1, sticky="e", padx=16, pady=(0, 16))

        ctk.CTkLabel(
            frame,
            text=f"Banco: {self.db.db_path}\nArquivos gerados: {ROOT_DIR / 'exports'}\nA chave de acesso da IA fica no cofre do Windows. A chave da OpenAI permanece somente no servidor Neiva.",
            text_color=UI["muted"],
            justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(14, 0))
        self.after(50, self._load_trello_connection)

    def _load_trello_connection(self) -> None:
        app_key, token = get_trello_app_key(), get_secret("TRELLO_TOKEN", self.db.get_setting("TRELLO_TOKEN"))
        if not app_key:
            self.trello_connection_status.configure(text="Conexão indisponível: a versão não possui uma chave de aplicativo Trello.", text_color=UI["error"])
            self.trello_connect_button.configure(state="disabled")
            return
        if not token:
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
        app_key = get_trello_app_key()
        if not app_key:
            self._show_error("Trello", "A chave pública do aplicativo Trello não foi configurada nesta versão.")
            return
        self.trello_connect_button.configure(state="disabled", text="AGUARDANDO LOGIN...")
        self.trello_connection_status.configure(text="Conclua a autorização na janela do navegador.")
        def task() -> None:
            try:
                token = authorize_trello(app_key); identity = get_trello_identity(app_key, token); boards = list_trello_boards(app_key, token)
                set_secret("TRELLO_TOKEN", token); self.db.delete_setting("TRELLO_TOKEN"); os.environ["TRELLO_TOKEN"] = token
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
        selected_id = get_secret("TRELLO_BOARD_ID", self.db.get_setting("TRELLO_BOARD_ID"))
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
            set_secret("TRELLO_BOARD_ID", board_id); self.db.delete_setting("TRELLO_BOARD_ID"); os.environ["TRELLO_BOARD_ID"] = board_id
        except Exception as exc: self._show_error("Trello", str(exc))

    def _disconnect_trello(self) -> None:
        try:
            for key in ("TRELLO_TOKEN", "TRELLO_BOARD_ID"):
                set_secret(key, ""); self.db.delete_setting(key); os.environ.pop(key, None)
        except Exception as exc:
            self._show_error("Trello", str(exc)); return
        self.show_settings()

    def _month_action_panel(self, frame: ctk.CTkFrame, button_text: str, action):
        panel = ctk.CTkFrame(frame, fg_color=UI["surface"], corner_radius=10, border_width=1, border_color=UI["border"])
        panel.grid(row=0, column=0, sticky="ew")
        panel.grid_columnconfigure(1, weight=1)

        clients = self._clients()
        names = [client.name for client in clients] or ["Nenhum cliente"]
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
        modal = FormModal(self, "Cliente", width=620, height=640)
        fields = {
            "name": modal.entry("Nome", client.name if client else ""),
            "niche": modal.entry("Nicho", client.niche if client else ""),
            "instagram": modal.entry("Instagram", client.instagram if client else ""),
            "posting_frequency": modal.entry("Frequência de postagem", client.posting_frequency if client else ""),
            "objective": modal.text("Objetivo", client.objective if client else "", height=90),
            "notes": modal.text("Observações", client.notes if client else "", height=120),
        }

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
        modal = FormModal(self, "Conteúdo", width=720, height=760)
        title = modal.entry("Título", post.title if post else "")
        content_type = modal.option("Tipo", CONTENT_TYPES, post.content_type if post else CONTENT_TYPES[0])
        platform = modal.option("Plataforma", PLATFORMS, post.platform if post else PLATFORMS[0])
        status = modal.option("Status", STATUSES, post.status if post else STATUSES[0])
        description = modal.text("Descrição", post.description if post else "", height=90)
        caption = modal.text("Legenda", post.caption if post else "", height=120)
        cta = modal.text("CTA", post.cta if post else "", height=70)

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
        try:
            path = self.pdf.export_month(client, self.db.get_posts_for_client_month(client.id, year, month), year, month)
        except Exception as exc:
            self._show_error("Erro ao exportar PDF", str(exc))
            return
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
        if client.id is None:
            return
        posts = self.db.get_posts_for_client_month(client.id, year, month)
        if not posts:
            self._show_warning("Trello", "Não há posts neste mês.")
            return
        pending_posts = self.db.get_posts_pending_trello(client.id, year, month)
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
                    "TRELLO_TOKEN": get_secret("TRELLO_TOKEN", self.db.get_setting("TRELLO_TOKEN")),
                    "TRELLO_BOARD_ID": get_secret("TRELLO_BOARD_ID", self.db.get_setting("TRELLO_BOARD_ID")),
                }
                api = TrelloAPI(TrelloConfig.from_environment(settings))
                list_setting = f"TRELLO_LIST_{client.id}_{year}_{month}"
                list_id = self.db.get_setting(list_setting)
                if not list_id:
                    list_id = api.get_or_create_list(list_name)
                    self.db.set_setting(list_setting, list_id)
                for post in pending_posts:
                    if post.id is not None:
                        card_id = api.find_card_for_post(post) or api.create_card(list_id, post)
                        self.db.update_post_trello_card(post.id, card_id)
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
            "Encarte de Ofertas": self.show_offer_flyer,
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
