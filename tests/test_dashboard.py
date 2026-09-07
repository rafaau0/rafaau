import tempfile
import unittest
from datetime import date
from pathlib import Path

from content_planner.database import Client, Contract, Database, Post


class DashboardTests(unittest.TestCase):
    def test_month_client_and_agenda_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / 'test.db')
            first = db.create_client(Client(None, 'Mesmo nome', '', '', '', '', ''))
            second = db.create_client(Client(None, 'Mesmo nome', '', '', '', '', ''))
            for client, day, status in [
                (first, '2026-08-31', 'Pendente'),
                (first, '2026-09-07', 'Em andamento'),
                (first, '2026-09-08', 'Pendente'),
                (first, '2026-09-14', 'Pendente'),
                (first, '2026-09-15', 'Pendente'),
                (first, '2026-09-08', 'Concluído'),
                (second, '2026-09-07', 'Pendente'),
            ]:
                db.create_post(Post(None, client, day, 'Feed', 'Instagram', 'Teste', '', '', '', status))
            data = db.dashboard_data(2026, 9, first, date(2026, 9, 7))
            self.assertEqual(data['counts'], {'Pendente': 3, 'Em andamento': 1, 'Concluído': 1})
            self.assertEqual([p.post_date for p in data['priorities']], ['2026-08-31', '2026-09-07'])
            self.assertEqual([p.post_date for p in data['upcoming']], ['2026-09-08', '2026-09-14'])
            self.assertEqual(set(data['clients']), {first})

    def test_contract_vigency_revenue_and_alerts(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / 'test.db')
            active = db.create_client(Client(None, 'Ativo', '', '', '', '', ''))
            inactive = db.create_client(Client(None, 'Inativo', '', '', '', '', '', status='Inativo'))
            for client, start, end, value, status in [
                (active, '2026-09-07', '2026-09-07', 100, 'Ativo'),
                (active, '', '', 200, 'Ativo'),
                (active, '2026-09-08', '', 400, 'Ativo'),
                (active, '', '2026-09-06', 800, 'Ativo'),
                (active, '', '', 1600, 'Cancelado'),
                (inactive, '', '', 3200, 'Ativo'),
            ]:
                db.create_contract(Contract(None, client, 'Contrato', value_cents=value,
                                            start_date=start, end_date=end, status=status))
            data = db.dashboard_data(2025, 1, today=date(2026, 9, 7))
            self.assertEqual(data['revenue'], 300)
            self.assertEqual(len(data['contracts']), 3)
            self.assertEqual([c.end_date for c in data['alerts']], ['2026-09-06', '2026-09-07'])

    def test_empty_dashboard(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Database(Path(folder) / 'test.db').dashboard_data(2026, 9)
            self.assertEqual(data['counts'], {})
            self.assertEqual(data['priorities'], [])
            self.assertEqual(data['revenue'], 0)
