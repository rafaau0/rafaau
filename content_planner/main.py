from __future__ import annotations


def main() -> None:
    try:
        try:
            from .ui import ContentPlannerApp
        except ImportError:
            from content_planner.ui import ContentPlannerApp
        app = ContentPlannerApp()
        app.mainloop()
    except Exception as exc:
        import traceback
        from tkinter import messagebox

        traceback.print_exc()
        messagebox.showerror("Neiva Planner", f"Não foi possível iniciar o aplicativo.\n\n{exc}")


if __name__ == "__main__":
    main()
