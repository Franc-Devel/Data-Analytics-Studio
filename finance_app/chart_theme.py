"""Shared readable FAUVOR palette for Plotly dashboards."""
import plotly.graph_objects as go
import plotly.io as pio

PALETTE = ["#895522", "#47664F", "#536B70", "#9B732A", "#80634F", "#985A4E"]

def apply_chart_theme():
    theme = go.layout.Template(pio.templates["plotly_white"])
    theme.layout.update(
        colorway=PALETTE, paper_bgcolor="#FFFAF2", plot_bgcolor="#FFFAF2",
        font=dict(color="#2B211A"),
        xaxis=dict(gridcolor="#E5D8C6", linecolor="#D6C0A3", tickfont=dict(color="#65503D")),
        yaxis=dict(gridcolor="#E5D8C6", linecolor="#D6C0A3", tickfont=dict(color="#65503D")),
        legend=dict(font=dict(color="#2B211A")),
        hoverlabel=dict(bgcolor="#4A2A18", font=dict(color="#FFFAF2")),
    )
    pio.templates["fauvor"] = theme
    pio.templates.default = "fauvor"
