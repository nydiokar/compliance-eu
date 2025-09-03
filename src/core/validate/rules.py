from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.core.mapping.profiles import MappingProfile, FieldType
from src.logging_conf import get_logger

logger = get_logger("validate")


@dataclass
class ValidationError:
    row: int
    column: str
    reason: str


def validate_dataframe(df: pd.DataFrame, profile: MappingProfile) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Validate a normalized DataFrame against MappingProfile.

    Returns a tuple of (valid_df, errors_df) where errors_df has columns [row, column, reason].
    """
    errors: List[ValidationError] = []

    # Required fields
    for field, spec in profile.columns.items():
        if spec.required and field in df.columns:
            missing = df[field].isna()
            for idx in df.index[missing]:
                errors.append(ValidationError(row=int(idx), column=field, reason="required"))

    # Type/range/enum/unique validations
    for field, spec in profile.columns.items():
        if field not in df.columns:
            continue

        series = df[field]
        if spec.type in (FieldType.INTEGER, FieldType.DECIMAL):
            # Numeric min/max
            min_val = None
            max_val = None
            if spec.validation:
                min_val = spec.validation.get("min_value")
                max_val = spec.validation.get("max_value")

            for idx, val in series.items():
                if pd.isna(val):
                    continue
                try:
                    num = float(val)
                except (ValueError, TypeError):
                    errors.append(ValidationError(int(idx), field, "not_numeric"))
                    continue
                if min_val is not None and num < float(min_val):
                    errors.append(ValidationError(int(idx), field, f"lt_min:{min_val}"))
                if max_val is not None and num > float(max_val):
                    errors.append(ValidationError(int(idx), field, f"gt_max:{max_val}"))

        if spec.type in (FieldType.DATE, FieldType.DATETIME):
            # Date range
            if spec.validation and spec.validation.get("date_range"):
                dr = spec.validation["date_range"]
                min_date = dr.get("min_date")
                max_date = dr.get("max_date")
                for idx, val in series.items():
                    if pd.isna(val):
                        continue
                    try:
                        d = val.date() if hasattr(val, "date") else val
                        if isinstance(d, str):
                            d = datetime.fromisoformat(d).date()
                    except Exception:
                        errors.append(ValidationError(int(idx), field, "bad_date"))
                        continue
                    if min_date and d < datetime.fromisoformat(min_date).date():
                        errors.append(ValidationError(int(idx), field, f"before_min:{min_date}"))
                    if max_date and d > datetime.fromisoformat(max_date).date():
                        errors.append(ValidationError(int(idx), field, f"after_max:{max_date}"))

        # Enum values
        if spec.validation and spec.validation.get("enum_values"):
            allowed = set(spec.validation["enum_values"])  # type: ignore[arg-type]
            for idx, val in series.items():
                if pd.isna(val):
                    continue
                if str(val) not in allowed:
                    errors.append(ValidationError(int(idx), field, "not_in_enum"))

        # Unique constraint (basic per-column uniqueness)
        if spec.validation and spec.validation.get("unique"):
            dup_mask = series.duplicated(keep=False)
            for idx in df.index[dup_mask]:
                if pd.notna(series.loc[idx]):
                    errors.append(ValidationError(int(idx), field, "duplicate"))

    # Build error DataFrame
    if errors:
        err_df = pd.DataFrame([e.__dict__ for e in errors])
    else:
        err_df = pd.DataFrame(columns=["row", "column", "reason"])  # empty

    # Exclude rows with any errors to form valid_df
    invalid_rows = set(err_df["row"].tolist()) if not err_df.empty else set()
    if invalid_rows:
        valid_df = df.drop(index=list(invalid_rows)).reset_index(drop=True)
    else:
        valid_df = df.reset_index(drop=True)

    logger.info(
        "validation_completed",
        total_rows=len(df),
        valid_rows=len(valid_df),
        errors=len(err_df) if not err_df.empty else 0,
    )

    return valid_df, err_df

