from pathlib import Path

from src.core.intake import load_frame


def test_csv_parser_loads_fixture():
    p = Path("tests/data_fixtures/budget_messy_data.csv")
    assert p.exists(), "Fixture missing"
    df = load_frame(p)
    assert not df.empty
    assert len(df.columns) >= 5

