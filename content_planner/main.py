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
            from .ui import ContentPlannerApp
        except ImportError:
            from content_planner.ui import ContentPlannerApp
        app = ContentPlannerApp()
        app.mainloop()
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
