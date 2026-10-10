import tkinter as tk

from finance_app.gui import FinanceApp


if __name__ == "__main__":
    try:
        FinanceApp().run()
    except tk.TclError as exc:
        raise SystemExit(
            "No se pudo abrir la ventana. Instale Python para Windows con la opción "
            "'tcl/tk and IDLE' habilitada y vuelva a ejecutar iniciar.bat.\n"
            f"Detalle técnico: {exc}"
        ) from exc

