import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import seaborn as sns
import tkinter as tk

# Configuración visual premium para consultoría
sns.set_theme(style="dark", context="talk")
plt.rcParams['font.family'] = 'sans-serif'

def draw_chart(frame: tk.Frame, df: pd.DataFrame, chart_type: str, x_col: str, y_col: str = None):
    """
    Dibuja un gráfico de matplotlib de alta calidad en un Frame de Tkinter.
    """
    for widget in frame.winfo_children():
        widget.destroy()

    if df.empty or not x_col:
        lbl = tk.Label(frame, text="Datos insuficientes para graficar", bg="#1e1e2e", fg="#a6accd", font=("Segoe UI", 12))
        lbl.pack(expand=True)
        return

    # Usar DPI alto para mayor nitidez
    fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
    
    # Fondo elegante estilo dashboard oscuro
    bg_color = '#1e1e2e'
    text_color = '#cdd6f4'
    grid_color = '#313244'
    
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.tick_params(colors=text_color, labelsize=10)
    ax.xaxis.label.set_color(text_color)
    ax.yaxis.label.set_color(text_color)
    ax.title.set_color(text_color)
    ax.title.set_fontsize(14)
    ax.title.set_weight('bold')
    
    # Grid sutil
    ax.grid(axis='y', color=grid_color, linestyle='--', linewidth=0.7, alpha=0.7)

    # Paleta de colores profesional
    palette = sns.color_palette("mako", as_cmap=False)

    try:
        if chart_type == 'bar':
            if y_col:
                plot = sns.barplot(data=df, x=x_col, y=y_col, ax=ax, palette="mako")
            else:
                counts = df[x_col].value_counts()
                plot = sns.barplot(x=counts.index, y=counts.values, ax=ax, palette="mako")
                
            ax.set_title(f'Análisis de {x_col}', pad=20)
            # Agregar etiquetas de datos en las barras
            for container in ax.containers:
                ax.bar_label(container, color=text_color, fmt='%.1f', padding=3, fontsize=9)
            
        elif chart_type == 'pie':
            counts = df[x_col].value_counts()
            wedges, texts, autotexts = ax.pie(
                counts, labels=counts.index, autopct='%1.1f%%', 
                colors=sns.color_palette("mako", len(counts)),
                textprops={'color': text_color, 'fontsize': 10},
                wedgeprops={'linewidth': 2, 'edgecolor': bg_color}
            )
            ax.set_title(f'Distribución de {x_col}', pad=20)
            
        elif chart_type == 'line':
            if y_col:
                sns.lineplot(data=df, x=x_col, y=y_col, ax=ax, color='#89b4fa', linewidth=2.5, marker='o', markersize=8)
            ax.set_title(f'Tendencia: {y_col} vs {x_col}', pad=20)
            ax.grid(axis='x', color=grid_color, linestyle='--', linewidth=0.7, alpha=0.7)
            
        elif chart_type == 'scatter':
            if y_col:
                sns.scatterplot(data=df, x=x_col, y=y_col, ax=ax, color='#f38ba8', s=80, alpha=0.8, edgecolor='none')
            ax.set_title(f'Relación: {x_col} vs {y_col}', pad=20)
            ax.grid(axis='x', color=grid_color, linestyle='--', linewidth=0.7, alpha=0.7)
            
        # Remover bordes superiores y derechos
        sns.despine(ax=ax, left=True, bottom=False)
        ax.spines['bottom'].set_color(grid_color)
            
    except Exception as e:
        ax.clear()
        ax.text(0.5, 0.5, f"Error al generar gráfico:\n{str(e)}", color='#f38ba8', ha='center', va='center', fontsize=12)

    plt.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

