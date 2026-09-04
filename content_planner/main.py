from __future__ import annotations

import logging

try:
    from .logging_setup import configure_logging
except ImportError:
    from content_planner.logging_setup import configure_logging


def main() -> None:
    configure_logging()
    try:
        try:
            from .account_login import require_login
        except ImportError:
            from content_planner.account_login import require_login
        force_login = False
        while True:
            if not require_login(force=force_login):
                return
            force_login = False
            try:
                from .ui import ContentPlannerApp
            except ImportError:
                from content_planner.ui import ContentPlannerApp
            app = ContentPlannerApp()
            app.mainloop()
            action = getattr(app, "auth_action", None)
            if action not in {"add", "switch", "logout"}:
                return
            force_login = action == "add"
    except Exception as exc:
        import traceback
        logging.exception("Falha não tratada ao iniciar o aplicativo")
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("Neiva Planner", f"Não foi possível iniciar o aplicativo.\n\nConsulte o arquivo de logs para suporte.\n\n{exc}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
