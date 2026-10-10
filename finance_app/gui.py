from __future__ import annotations
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import customtkinter as ctk

from finance_app.analysis import STATISTIC_HELP, numeric_summary, profile_dataset, quality_issues, recommend_chart
from finance_app.data_service import DataLoadError, excel_sheets, load_dataset
from finance_app.consulting import generate_income_statement
from finance_app.charts import draw_chart
from finance_app.reports import export_income_statement_to_excel

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class FinanceApp:
    def __init__(self) -> None:
        self.root = ctk.CTk()
        self.root.title("Data Analytics Studio — demo con datos sintéticos")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        self.frame: pd.DataFrame | None = None
        self.status = tk.StringVar(value="Listo para importar datos")
        self._configure_style()
        self._build()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#1e1e2e",
                        foreground="#cdd6f4",
                        rowheight=30,
                        fieldbackground="#1e1e2e",
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#313244')])
        style.configure("Treeview.Heading",
                        background="#313244",
                        foreground="#cdd6f4",
                        relief="flat",
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview.Heading", background=[('active', '#45475a')])

    def run(self) -> None:
        self.root.mainloop()

    def _build(self) -> None:
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(header, text="Data Analytics Studio", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Importar CSV / Excel", command=self._choose_file).pack(side="right")

        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.tabs.add("Datos")
        self.tabs.add("Gráficas")
        self.tabs.add("Contabilidad")
        self.tabs.add("Terminal")

        # Tab: Datos
        self.metrics = ctk.CTkFrame(self.tabs.tab("Datos"), fg_color="transparent")
        self.metrics.pack(fill="x", pady=(0, 10))
        self.preview_tree = self._tree(self.tabs.tab("Datos"))

        # Tab: Gráficas
        self._build_charts(self.tabs.tab("Gráficas"))

        # Tab: Contabilidad
        self._build_accounting(self.tabs.tab("Contabilidad"))

        # Tab: Terminal
        self._build_terminal(self.tabs.tab("Terminal"))

        ctk.CTkLabel(self.root, textvariable=self.status, anchor="w").pack(fill="x", padx=20, pady=5)

    def _tree(self, parent, columns: tuple[str, ...] = ()) -> ttk.Treeview:
        holder = ctk.CTkFrame(parent)
        holder.pack(fill="both", expand=True)
        # Using ttk.Treeview for tables since CustomTkinter doesn't have a native table yet
        tree = ttk.Treeview(holder, columns=columns, show="headings")
        ybar = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        xbar = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        if columns:
            self._set_tree_columns(tree, list(columns))
        return tree

    def _build_charts(self, parent) -> None:
        controls = ctk.CTkFrame(parent, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(controls, text="Variable X:").pack(side="left")
        self.chart_x_var = ctk.StringVar()
        self.chart_x_combo = ctk.CTkComboBox(controls, variable=self.chart_x_var, state="readonly")
        self.chart_x_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(controls, text="Variable Y (Opcional):").pack(side="left")
        self.chart_y_var = ctk.StringVar()
        self.chart_y_combo = ctk.CTkComboBox(controls, variable=self.chart_y_var, state="readonly")
        self.chart_y_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(controls, text="Tipo:").pack(side="left", padx=5)
        self.chart_type_var = ctk.StringVar(value="bar")
        self.chart_type_combo = ctk.CTkComboBox(controls, variable=self.chart_type_var, values=["bar", "pie", "line", "scatter"], state="readonly")
        self.chart_type_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(controls, text="Graficar", command=self._render_chart).pack(side="left", padx=10)
        
        self.chart_canvas_frame = tk.Frame(parent, bg="#2b2b2b")
        self.chart_canvas_frame.pack(fill="both", expand=True)

    def _render_chart(self):
        if self.frame is None:
            return
        x_col = self.chart_x_var.get()
        y_col = self.chart_y_var.get() if self.chart_y_var.get() else None
        c_type = self.chart_type_var.get()
        if not x_col:
            messagebox.showwarning("Faltan datos", "Seleccione al menos la Variable X")
            return
        draw_chart(self.chart_canvas_frame, self.frame, c_type, x_col, y_col)

    def _build_accounting(self, parent) -> None:
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(top, text="Categoría (Ingreso/Gasto):").pack(side="left")
        self.cat_col_var = ctk.StringVar()
        self.cat_col_combo = ctk.CTkComboBox(top, variable=self.cat_col_var, state="readonly")
        self.cat_col_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(top, text="Monto ($):").pack(side="left")
        self.amt_col_var = ctk.StringVar()
        self.amt_col_combo = ctk.CTkComboBox(top, variable=self.amt_col_var, state="readonly")
        self.amt_col_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(top, text="Generar EERR", command=self._generate_income_statement).pack(side="left", padx=10)
        ctk.CTkButton(top, text="Exportar a Excel", command=self._export_income_statement, fg_color="#217346", hover_color="#1e5c3a").pack(side="left", padx=5)
        
        self.accounting_text = ctk.CTkTextbox(parent, font=("Consolas", 14))
        self.accounting_text.pack(fill="both", expand=True)
        self.last_income_statement = None
        self.accounting_text.pack(fill="both", expand=True)

    def _build_terminal(self, parent) -> None:
        self.terminal_text = ctk.CTkTextbox(parent, font=("Consolas", 14), fg_color="#1e1e1e", text_color="#00ff00")
        self.terminal_text.pack(fill="both", expand=True)
        self.terminal_text.insert("end", "Terminal Profesional de Consultoría\nEscriba 'help' para ver los comandos.\n>>> ")
        self.terminal_text.bind("<Return>", self._handle_terminal_input)

    def _generate_income_statement(self) -> None:
        if self.frame is None: return
        cat_col = self.cat_col_var.get()
        amt_col = self.amt_col_var.get()
        if not cat_col or not amt_col: return
        
        result = generate_income_statement(self.frame, cat_col, amt_col)
        self.accounting_text.configure(state="normal")
        self.accounting_text.delete("1.0", "end")
        if "error" in result:
            self.accounting_text.insert("end", result["error"])
        else:
            out = (
                " ESTADO DE RESULTADOS\n"
                " ====================\n\n"
                f" Ingresos Totales:  $ {result.get('Ingresos Totales', 0):,.2f}\n"
                f" Costos:            $ {result.get('Costos', 0):,.2f}\n"
                " --------------------\n"
                f" Utilidad Bruta:    $ {result.get('Utilidad Bruta', 0):,.2f}\n\n"
                f" Gastos Operativos: $ {result.get('Gastos', 0):,.2f}\n"
                " --------------------\n"
                f" UTILIDAD NETA:     $ {result.get('Utilidad Neta', 0):,.2f}\n"
            )
            self.accounting_text.insert("end", out)
            self.last_income_statement = result
        self.accounting_text.configure(state="disabled")

    def _export_income_statement(self) -> None:
        if not hasattr(self, 'last_income_statement') or not self.last_income_statement:
            messagebox.showinfo("Exportar", "Primero debe generar un Estado de Resultados.")
            return
            
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", 
            filetypes=[("Excel files", "*.xlsx")],
            title="Guardar Estado de Resultados"
        )
        if not path:
            return
            
        success = export_income_statement_to_excel(self.last_income_statement, path)
        if success:
            messagebox.showinfo("Exportar", f"Reporte exportado exitosamente a:\n{path}")
        else:
            messagebox.showerror("Exportar", "Ocurrió un error al exportar el reporte.")

    def _handle_terminal_input(self, event) -> str:
        lines = self.terminal_text.get("1.0", "end-1c").split("\n")
        last_line = lines[-1]
        if last_line.startswith(">>> "):
            cmd = last_line[4:].strip()
            out = ""
            if cmd == "help":
                out = "Comandos: stats, preview, clear"
            elif cmd == "stats":
                out = f"Filas: {len(self.frame)}, Col: {len(self.frame.columns)}" if self.frame is not None else "No data"
            elif cmd == "clear":
                self.terminal_text.delete("1.0", "end")
                self.terminal_text.insert("end", ">>> ")
                return "break"
            elif cmd == "preview":
                out = self.frame.head(5).to_string() if self.frame is not None else "No data"
            elif cmd != "":
                out = f"Comando desconocido: '{cmd}'"
            
            if out: self.terminal_text.insert("end", f"\n{out}\n>>> ")
            else: self.terminal_text.insert("end", "\n>>> ")
        return "break"

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Datos", "*.csv *.xlsx"), ("CSV", "*.csv"), ("Excel", "*.xlsx")])
        if not path: return
        try:
            sheet = self._select_sheet(path) if Path(path).suffix.lower() == ".xlsx" else None
            if sheet is False: return
            dataset = load_dataset(path, sheet if isinstance(sheet, str) else None)
        except DataLoadError as exc:
            messagebox.showerror("Error", str(exc))
            return
        self.frame = dataset.frame
        self._refresh()
        self.status.set(f"{Path(path).name}: {len(self.frame):,} filas, {len(self.frame.columns)} columnas")

    def _select_sheet(self, path: str) -> str | bool:
        sheets = excel_sheets(path)
        if len(sheets) == 1: return sheets[0]
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Elegir hoja")
        dialog.grab_set()
        choice = ctk.StringVar(value=sheets[0])
        ctk.CTkLabel(dialog, text="Seleccione hoja:").pack(pady=10)
        ctk.CTkComboBox(dialog, variable=choice, values=sheets).pack(pady=10)
        res = []
        ctk.CTkButton(dialog, text="Importar", command=lambda: (res.append(choice.get()), dialog.destroy())).pack(pady=10)
        self.root.wait_window(dialog)
        return res[0] if res else False

    def _refresh(self) -> None:
        if self.frame is None: return
        
        # update metrics
        profile = profile_dataset(self.frame)
        for child in self.metrics.winfo_children():
            child.destroy()
            
        labels = [
            ("Filas", f"{profile['filas']:,}"), 
            ("Columnas", str(profile["columnas"])),
            ("Completitud", f"{profile['porcentaje_completo']:.1f}%"),
            ("Duplicados", f"{profile['duplicados']:,}"), 
            ("Numéricas", str(profile["numericas"]))
        ]
        
        for index, (name, value) in enumerate(labels):
            card = ctk.CTkFrame(self.metrics, fg_color="#313244", corner_radius=10)
            card.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            ctk.CTkLabel(card, text=name, text_color="#a6accd", font=("Segoe UI", 12)).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=value, text_color="#cdd6f4", font=("Segoe UI", 20, "bold")).pack(pady=(0, 10))
        
        # update table
        self._fill_tree(self.preview_tree, self.frame.head(100))
        
        # update combos
        cols = [""] + list(self.frame.columns)
        self.chart_x_combo.configure(values=cols)
        self.chart_y_combo.configure(values=cols)
        self.cat_col_combo.configure(values=list(self.frame.columns))
        self.amt_col_combo.configure(values=list(self.frame.columns))

    def _fill_tree(self, tree: ttk.Treeview, frame: pd.DataFrame) -> None:
        self._set_tree_columns(tree, [str(column) for column in frame.columns])
        tree.delete(*tree.get_children())
        for row in frame.itertuples(index=False, name=None):
            tree.insert("", "end", values=[self._display(value) for value in row])

    @staticmethod
    def _set_tree_columns(tree: ttk.Treeview, columns: list[str]) -> None:
        tree.configure(columns=columns)
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=max(110, min(260, len(column) * 11)), stretch=True)

    @staticmethod
    def _display(value: object) -> str:
        if pd.isna(value): return "—"
        if isinstance(value, float): return f"{value:,.4f}".rstrip("0").rstrip(".")
        return str(value)

