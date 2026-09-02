"""Mantém o tkinter disponível quando a verificação automática do PyInstaller falha."""


def pre_find_module_path(hook_api):
    """Os arquivos Tcl/Tk são incluídos manualmente pelo NeivaPlanner.spec."""
