"""Run the local analytical pipeline without a graphical display."""
from finance_app.analysis import numeric_summary, profile_dataset, quality_issues
from finance_app.consulting import generate_income_statement
from finance_app.data_service import load_dataset
from examples.generate_data import generate


def main() -> None:
    frame = load_dataset(generate()).frame
    result = generate_income_statement(frame, "categoria", "monto")
    assert len(frame) == 21
    assert result["Ingresos Totales"] == 75000
    assert result["Costos"] == 24000
    assert result["Gastos"] == 13800
    assert result["Utilidad Neta"] == 37200
    print("DEMO: datos completamente sintéticos / entirely synthetic data")
    print(profile_dataset(frame))
    print(numeric_summary(frame).to_string(index=False))
    print(quality_issues(frame))
    print(result)


if __name__ == "__main__":
    main()
