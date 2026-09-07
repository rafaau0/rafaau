"""Dashboard local: resumo mensal e atalhos para o trabalho atual."""
from datetime import date

import customtkinter as ctk

from .client_management import format_date_br, format_money, parse_date_input
from .design_system import COLORS as UI, RADIUS, font, primary_button, secondary_button
from .form_modal import FormModal


class DashboardMixin:
    def show_dashboard(self) -> None:
        today = date.today()
        year, month = getattr(self, '_dashboard_period', (today.year, today.month))
        client_id = getattr(self, '_dashboard_client', None)
        choices = {f'{c.name} · #{c.id}': c.id for c in self._clients()}
        if client_id not in choices.values():
            client_id = None
            self._dashboard_client = None
        data = self.db.dashboard_data(year, month, client_id, today)
        frame = self._set_active_view('Dashboard', 'Visão geral', 'Seu planejamento, suas prioridades e seus clientes.')

        def section(title, note=''):
            box = ctk.CTkFrame(frame, fg_color=UI['surface'], corner_radius=RADIUS['md'],
                               border_width=1, border_color=UI['border'])
            box.pack(fill='x', pady=(0, 16))
            ctk.CTkLabel(box, text=title, font=font(17, 'bold'), text_color=UI['text']).pack(anchor='w', padx=18, pady=(16, 4))
            if note:
                label = ctk.CTkLabel(box, text=note, font=font(12), text_color=UI['muted'], justify='left')
                label.pack(fill='x', padx=18, pady=(0, 10))
                label.bind('<Configure>', lambda e, target=label: target.configure(wraplength=max(150, e.width - 12)))
            return box

        toolbar = section('Resumo do mês')
        filters = ctk.CTkFrame(toolbar, fg_color='transparent')
        filters.pack(fill='x', padx=18, pady=(4, 12))
        ctk.CTkButton(filters, text='‹', width=36, command=lambda: self._dashboard_move_month(-1), **secondary_button()).pack(side='left')
        ctk.CTkLabel(filters, text=f'{month:02d}/{year}', font=font(16, 'bold'), width=100).pack(side='left')
        ctk.CTkButton(filters, text='›', width=36, command=lambda: self._dashboard_move_month(1), **secondary_button()).pack(side='left')
        ctk.CTkButton(filters, text='Mês atual', width=95, command=lambda: self._dashboard_set_period(today.year, today.month), **secondary_button()).pack(side='left', padx=8)
        selection = ctk.CTkOptionMenu(toolbar, values=['Todos os clientes', *choices],
                                     command=lambda label: self._dashboard_select_client(choices.get(label)))
        selection.set(next((label for label, ident in choices.items() if ident == client_id), 'Todos os clientes'))
        selection.pack(fill='x', padx=18, pady=(0, 12))
        ctk.CTkButton(toolbar, text='+ Novo conteúdo', command=self._dashboard_new_post, **primary_button()).pack(anchor='w', padx=18, pady=(0, 16))

        metrics = ctk.CTkFrame(frame, fg_color='transparent')
        metrics.pack(fill='x', pady=(0, 16))
        counts = data['counts']
        tiles = []
        for label, value, color in [
            ('Conteúdos do mês', sum(counts.values()), UI['accent']),
            ('Pendentes', counts.get('Pendente', 0), UI['warning']),
            ('Em andamento', counts.get('Em andamento', 0), UI['text']),
            ('Concluídos', counts.get('Concluído', 0), UI['success']),
        ]:
            tile = ctk.CTkFrame(metrics, fg_color=UI['surface'], border_width=1, border_color=UI['border'], corner_radius=RADIUS['md'])
            ctk.CTkLabel(tile, text=label, font=font(12), text_color=UI['muted']).pack(anchor='w', padx=16, pady=(14, 2))
            ctk.CTkLabel(tile, text=str(value), font=font(30, 'bold'), text_color=color).pack(anchor='w', padx=16, pady=(0, 14))
            tiles.append(tile)

        def reflow(event):
            columns = 4 if event.width >= 850 else 2 if event.width >= 440 else 1
            for col in range(4):
                metrics.grid_columnconfigure(col, weight=1 if col < columns else 0, uniform='metrics' if col < columns else '')
            for index, tile in enumerate(tiles):
                tile.grid(row=index // columns, column=index % columns, sticky='ew', padx=4, pady=4)
        metrics.bind('<Configure>', reflow)

        if not choices:
            welcome = section('Comece pelo seu primeiro cliente', 'Cadastre um cliente e depois crie seu primeiro conteúdo no planejamento.')
            ctk.CTkButton(welcome, text='Cadastrar cliente', command=self._open_client_modal, **primary_button()).pack(anchor='w', padx=18, pady=(0, 16))

        def posts_section(title, note, posts, empty):
            box = section(f'{title} · {len(posts)}', note)
            if not posts:
                ctk.CTkLabel(box, text=empty, text_color=UI['muted']).pack(anchor='w', padx=18, pady=(0, 16))
            for post in posts:
                client = data['clients'].get(post.client_id)
                day_label = 'Hoje' if post.post_date == today.isoformat() else format_date_br(post.post_date)
                if post.post_date < today.isoformat():
                    day_label += ' · Atrasado'
                text = f'{day_label} · {client.name if client else "Cliente"}\n{post.title or post.content_type} · {post.status}'
                button = ctk.CTkButton(box, text=text, anchor='w', command=lambda p=post: self._dashboard_open_post(p), **secondary_button(height=62))
                button.pack(fill='x', padx=18, pady=(0, 8))
                button.bind('<Configure>', lambda e, b=button: b._text_label.configure(wraplength=max(120, e.width - 30)))

        posts_section('Precisam de atenção', 'Atrasados e previstos para hoje, de qualquer mês. Clique para editar.',
                      data['priorities'], 'Nenhuma pendência até hoje. Tudo em dia!')
        posts_section('Próximas entregas', 'Conteúdos ainda não concluídos, de amanhã até os próximos sete dias.',
                      data['upcoming'], 'Nenhuma entrega prevista para os próximos sete dias.')
        business = section('Clientes e contratos · situação atual',
                           'O filtro de cliente se aplica aqui. Valores consideram a vigência de hoje, independentemente do mês selecionado.')
        for text in [f"Clientes ativos: {sum(c.status == 'Ativo' for c in data['clients'].values())}",
                     f"Contratos vigentes: {len(data['contracts'])}",
                     f"Valor mensal contratado: {format_money(data['revenue'])}"]:
            ctk.CTkLabel(business, text=text, font=font(15, 'bold'), text_color=UI['text']).pack(anchor='w', padx=18, pady=4)
        note = ctk.CTkLabel(business, text='Valor de contratos vigentes de clientes ativos. Não representa pagamentos recebidos.', text_color=UI['muted'], justify='left')
        note.pack(fill='x', padx=18, pady=(4, 14))
        note.bind('<Configure>', lambda e: note.configure(wraplength=max(150, e.width - 12)))
        for contract in data['alerts']:
            client = data['clients'][contract.client_id]
            status = 'Vencido' if contract.end_date < today.isoformat() else 'Vence em breve'
            button = ctk.CTkButton(business, text=f'{status} · {format_date_br(contract.end_date)}\n{client.name} · {contract.title}',
                                 anchor='w', command=lambda c=client: self._open_client_profile(c), **secondary_button(height=62))
            button.pack(fill='x', padx=18, pady=(0, 8))
            button.bind('<Configure>', lambda e, b=button: b._text_label.configure(wraplength=max(120, e.width - 30)))
        ctk.CTkButton(business, text='Ver todos os clientes e contratos', command=self.show_clients, **secondary_button()).pack(anchor='w', padx=18, pady=(8, 16))
        shortcuts = section('Ações rápidas')
        for label, command in [('Novo cliente', self._open_client_modal), ('Abrir planejamento', self.show_planning), ('Exportar PDF', self.show_export)]:
            ctk.CTkButton(shortcuts, text=label, command=command, **secondary_button()).pack(fill='x', padx=18, pady=(0, 10))

    def _dashboard_set_period(self, year, month):
        self._dashboard_period = (year, month)
        self.show_dashboard()

    def _dashboard_move_month(self, delta):
        today = date.today()
        year, month = getattr(self, '_dashboard_period', (today.year, today.month))
        year, month = divmod(year * 12 + month - 1 + delta, 12)
        if 1 <= year <= 9999:
            self._dashboard_set_period(year, month + 1)

    def _dashboard_select_client(self, client_id):
        self._dashboard_client = client_id
        self.show_dashboard()

    def _dashboard_open_post(self, post):
        self.selected_client_id = post.client_id
        self._open_post_modal(post.post_date, post)

    def _dashboard_new_post(self):
        choices = dict(self._client_choices())
        if not choices:
            self._open_client_modal()
            return
        modal = FormModal(self, 'Novo conteúdo', width=440, height=360)
        default = next((label for label, c in choices.items() if c.id == getattr(self, '_dashboard_client', None)), next(iter(choices)))
        selection = modal.option('Cliente', list(choices), default)
        year, month = getattr(self, '_dashboard_period', (date.today().year, date.today().month))
        initial = date.today() if (year, month) == (date.today().year, date.today().month) else date(year, month, 1)
        day = modal.entry('Data (DD/MM/AAAA)', format_date_br(initial.isoformat()))

        def proceed():
            try:
                post_date = parse_date_input(day.get(), required=True)
            except ValueError as exc:
                self._show_warning('Data inválida', str(exc))
                return
            self.selected_client_id = choices[selection.get()].id
            modal.destroy()
            self._open_post_modal(post_date, None)
        ctk.CTkButton(modal.body, text='Continuar', command=proceed, **primary_button()).pack(pady=12)
