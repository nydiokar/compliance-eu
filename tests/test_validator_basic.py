import pandas as pd

from src.core.mapping.profiles import load_profile
from src.core.validate.rules import validate_dataframe


def test_basic_validation_rules_flag_out_of_range():
    profile = load_profile("budget_execution_v1")
    assert profile is not None

    # Build minimal df with a bad execution_percentage and a negative planned_amount
    df = pd.DataFrame(
        {
            "period": ["2025-01-15", "2025-01-16"],
            "department": ["Education", "Health"],
            "budget_line": ["EDU.01", "HLT.01"],
            "execution_percentage": [150, 50],  # 150 is invalid (>100)
            "planned_amount": [-10, 100],  # -10 invalid (<0)
        }
    )

    valid, errors = validate_dataframe(df, profile)
    # Should have at least 2 errors
    assert errors is not None
    assert not errors.empty
    reasons = set(errors["reason"].tolist())
    assert any(r.startswith("above_maximum") for r in reasons)
    assert any(r.startswith("below_minimum") for r in reasons)
    # At least one row was dropped
    assert len(valid) < len(df)

