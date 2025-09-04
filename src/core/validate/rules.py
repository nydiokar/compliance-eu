from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Set, Any
from decimal import Decimal, InvalidOperation

import pandas as pd

from src.core.mapping.profiles import MappingProfile, FieldType
from src.logging_conf import get_logger

logger = get_logger("validate")


@dataclass
class ValidationError:
    row: int
    column: str
    reason: str
    value: Optional[Any] = None
    severity: str = "error"  # error, warning, info
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "row": self.row,
            "column": self.column,
            "reason": self.reason,
            "value": str(self.value) if self.value is not None else "",
            "severity": self.severity
        }


def validate_dataframe(df: pd.DataFrame, profile: MappingProfile) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Validate a normalized DataFrame against MappingProfile.

    Returns a tuple of (valid_df, errors_df) where errors_df has columns [row, column, reason, value, severity].
    """
    errors: List[ValidationError] = []
    logger.info("Starting validation", total_rows=len(df), columns=len(df.columns))

    # Required fields validation
    for field, spec in profile.columns.items():
        if spec.required and field in df.columns:
            missing = df[field].isna()
            for idx in df.index[missing]:
                errors.append(ValidationError(
                    row=int(idx), 
                    column=field, 
                    reason="required_field_missing",
                    value=None,
                    severity="error"
                ))

    # Type/range/enum/unique/pattern validations
    for field, spec in profile.columns.items():
        if field not in df.columns:
            # Check if required field is missing entirely
            if spec.required:
                errors.append(ValidationError(
                    row=-1,  # Column-level error
                    column=field,
                    reason="required_column_missing",
                    value="column not found in data",
                    severity="error"
                ))
            continue

        series = df[field]
        
        # Numeric validation (INTEGER, DECIMAL)
        if spec.type in (FieldType.INTEGER, FieldType.DECIMAL):
            errors.extend(_validate_numeric_field(series, field, spec))
            
        # String validation (length, pattern)
        elif spec.type == FieldType.STRING:
            errors.extend(_validate_string_field(series, field, spec))
            
        # Email validation
        elif spec.type == FieldType.EMAIL:
            errors.extend(_validate_email_field(series, field, spec))
            
        # URL validation
        elif spec.type == FieldType.URL:
            errors.extend(_validate_url_field(series, field, spec))
            
        # Phone validation
        elif spec.type == FieldType.PHONE:
            errors.extend(_validate_phone_field(series, field, spec))

        # Date/DateTime validation
        if spec.type in (FieldType.DATE, FieldType.DATETIME):
            errors.extend(_validate_date_field(series, field, spec, profile.validation))

        # Enum values validation
        if spec.validation and spec.validation.get("enum_values"):
            errors.extend(_validate_enum_field(series, field, spec))

        # Unique constraint validation
        if spec.validation and spec.validation.get("unique"):
            errors.extend(_validate_unique_field(series, field, spec))
    
    # Cross-field business rule validations
    errors.extend(_validate_business_rules(df, profile))

    # Build error DataFrame
    if errors:
        err_df = pd.DataFrame([e.to_dict() for e in errors])
    else:
        err_df = pd.DataFrame(columns=["row", "column", "reason", "value", "severity"])  # empty

    # Exclude rows with errors (not warnings) to form valid_df
    error_rows = set()
    if not err_df.empty:
        # Only exclude rows with actual errors, not warnings
        error_rows = set(
            err_df[(err_df["severity"] == "error") & (err_df["row"] >= 0)]["row"].tolist()
        )
    
    if error_rows:
        valid_df = df.drop(index=list(error_rows)).reset_index(drop=True)
    else:
        valid_df = df.reset_index(drop=True)

    # Count errors by severity
    error_counts = {"error": 0, "warning": 0, "info": 0}
    if not err_df.empty:
        severity_counts = err_df["severity"].value_counts().to_dict()
        error_counts.update(severity_counts)

    logger.info(
        "validation_completed",
        total_rows=len(df),
        valid_rows=len(valid_df),
        errors=error_counts["error"],
        warnings=error_counts["warning"],
        info=error_counts["info"],
        exclusion_rate=len(error_rows) / len(df) if len(df) > 0 else 0
    )

    return valid_df, err_df


def _validate_numeric_field(series: pd.Series, field: str, spec) -> List[ValidationError]:
    """Validate numeric fields (INTEGER, DECIMAL)."""
    errors = []
    validation_rules = spec.validation or {}
    
    min_val = validation_rules.get("min_value")
    max_val = validation_rules.get("max_value")
    
    for idx, val in series.items():
        if pd.isna(val):
            continue
            
        # Type validation
        try:
            if spec.type == FieldType.INTEGER:
                # Check if it's a valid integer
                num = int(float(val))  # Allow "123.0" -> 123
                if float(val) != num:  # But not "123.5" -> 123
                    errors.append(ValidationError(
                        int(idx), field, "not_integer", val, "error"
                    ))
                    continue
            else:  # DECIMAL
                num = float(val)
        except (ValueError, TypeError, OverflowError):
            errors.append(ValidationError(
                int(idx), field, "not_numeric", val, "error"
            ))
            continue
            
        # Range validation
        if min_val is not None and num < float(min_val):
            errors.append(ValidationError(
                int(idx), field, f"below_minimum:{min_val}", val, "error"
            ))
        if max_val is not None and num > float(max_val):
            errors.append(ValidationError(
                int(idx), field, f"above_maximum:{max_val}", val, "error"
            ))
    
    return errors


def _validate_string_field(series: pd.Series, field: str, spec) -> List[ValidationError]:
    """Validate string fields (length, pattern)."""
    errors = []
    validation_rules = spec.validation or {}
    
    min_length = validation_rules.get("min_length")
    max_length = validation_rules.get("max_length")
    pattern = validation_rules.get("pattern")
    
    compiled_pattern = None
    if pattern:
        try:
            compiled_pattern = re.compile(pattern)
        except re.error as e:
            logger.warning(f"Invalid regex pattern for field {field}: {pattern}, error: {e}")
    
    for idx, val in series.items():
        if pd.isna(val):
            continue
            
        str_val = str(val)
        
        # Length validation
        if min_length is not None and len(str_val) < min_length:
            errors.append(ValidationError(
                int(idx), field, f"too_short:{min_length}", val, "error"
            ))
        if max_length is not None and len(str_val) > max_length:
            errors.append(ValidationError(
                int(idx), field, f"too_long:{max_length}", val, "error"
            ))
            
        # Pattern validation
        if compiled_pattern and not compiled_pattern.match(str_val):
            errors.append(ValidationError(
                int(idx), field, f"pattern_mismatch:{pattern}", val, "error"
            ))
    
    return errors


def _validate_email_field(series: pd.Series, field: str, spec) -> List[ValidationError]:
    """Validate email fields."""
    errors = []
    # Simple email regex - more sophisticated validation can be added
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    for idx, val in series.items():
        if pd.isna(val):
            continue
            
        str_val = str(val).strip()
        if not email_pattern.match(str_val):
            errors.append(ValidationError(
                int(idx), field, "invalid_email_format", val, "error"
            ))
    
    return errors


def _validate_url_field(series: pd.Series, field: str, spec) -> List[ValidationError]:
    """Validate URL fields."""
    errors = []
    # Basic URL validation
    url_pattern = re.compile(r'^https?://[\w\-\.]+(:[0-9]+)?(/.*)?$', re.IGNORECASE)
    
    for idx, val in series.items():
        if pd.isna(val):
            continue
            
        str_val = str(val).strip()
        if not url_pattern.match(str_val):
            errors.append(ValidationError(
                int(idx), field, "invalid_url_format", val, "error"
            ))
    
    return errors


def _validate_phone_field(series: pd.Series, field: str, spec) -> List[ValidationError]:
    """Validate phone fields."""
    errors = []
    # Basic phone validation - can be enhanced for specific regions
    # This accepts: +XXX-XXX-XXXX, XXX-XXX-XXXX, (XXX) XXX-XXXX, etc.
    phone_pattern = re.compile(r'^[\+]?[\d\s\(\)\-\.]{7,15}$')
    
    for idx, val in series.items():
        if pd.isna(val):
            continue
            
        str_val = str(val).strip()
        if not phone_pattern.match(str_val):
            errors.append(ValidationError(
                int(idx), field, "invalid_phone_format", val, "error"
            ))
    
    return errors


def _validate_date_field(series: pd.Series, field: str, spec, global_validation) -> List[ValidationError]:
    """Validate date/datetime fields."""
    errors = []
    validation_rules = spec.validation or {}
    
    # Check for date range from field spec or global validation
    date_range = validation_rules.get("date_range") or global_validation.date_range
    min_date_str = None
    max_date_str = None
    
    if date_range:
        min_date_str = date_range.get("min_date")
        max_date_str = date_range.get("max_date")
    
    for idx, val in series.items():
        if pd.isna(val):
            continue
            
        # Parse date
        parsed_date = None
        try:
            if isinstance(val, (datetime, date)):
                parsed_date = val.date() if hasattr(val, "date") else val
            elif isinstance(val, str):
                # Try multiple date formats
                for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m"]:
                    try:
                        parsed_date = datetime.strptime(val, fmt).date()
                        break
                    except ValueError:
                        continue
                
                if not parsed_date:
                    # Try ISO format as fallback
                    parsed_date = datetime.fromisoformat(str(val)).date()
            else:
                parsed_date = datetime.fromisoformat(str(val)).date()
                
        except (ValueError, TypeError, AttributeError) as e:
            errors.append(ValidationError(
                int(idx), field, "invalid_date_format", val, "error"
            ))
            continue
            
        # Range validation
        if min_date_str and parsed_date < datetime.fromisoformat(min_date_str).date():
            errors.append(ValidationError(
                int(idx), field, f"date_before_minimum:{min_date_str}", val, "error"
            ))
        if max_date_str and parsed_date > datetime.fromisoformat(max_date_str).date():
            errors.append(ValidationError(
                int(idx), field, f"date_after_maximum:{max_date_str}", val, "error"
            ))
    
    return errors


def _validate_enum_field(series: pd.Series, field: str, spec) -> List[ValidationError]:
    """Validate enum/categorical fields."""
    errors = []
    allowed_values = set(str(v) for v in spec.validation["enum_values"])
    
    for idx, val in series.items():
        if pd.isna(val):
            continue
            
        str_val = str(val).strip()
        if str_val not in allowed_values:
            errors.append(ValidationError(
                int(idx), field, f"not_in_allowed_values:{','.join(sorted(allowed_values))}", val, "error"
            ))
    
    return errors


def _validate_unique_field(series: pd.Series, field: str, spec) -> List[ValidationError]:
    """Validate unique constraint on fields."""
    errors = []
    
    # Find duplicates
    non_null_series = series.dropna()
    if len(non_null_series) != len(non_null_series.drop_duplicates()):
        # There are duplicates
        dup_mask = series.duplicated(keep=False)
        for idx in series.index[dup_mask]:
            if pd.notna(series.loc[idx]):
                errors.append(ValidationError(
                    int(idx), field, "duplicate_value", series.loc[idx], "error"
                ))
    
    return errors


def _validate_business_rules(df: pd.DataFrame, profile: MappingProfile) -> List[ValidationError]:
    """Validate business-specific rules for the profile."""
    errors = []
    
    # Budget execution specific validations
    if profile.profile == "budget_execution_v1":
        errors.extend(_validate_budget_execution_rules(df))
    
    return errors


def _validate_budget_execution_rules(df: pd.DataFrame) -> List[ValidationError]:
    """Budget execution specific business rules."""
    errors = []
    
    # Rule 1: executed_amount should not exceed planned_amount (with tolerance)
    if "planned_amount" in df.columns and "executed_amount" in df.columns:
        for idx, row in df.iterrows():
            planned = row.get("planned_amount")
            executed = row.get("executed_amount")
            
            if pd.notna(planned) and pd.notna(executed):
                try:
                    planned_val = float(planned)
                    executed_val = float(executed)
                    
                    # Allow 5% tolerance for overexecution (common in government budgets)
                    if executed_val > planned_val * 1.05:
                        errors.append(ValidationError(
                            int(idx), "executed_amount", 
                            f"execution_exceeds_planned:{planned_val:.2f}",
                            executed, "warning"  # Warning, not error
                        ))
                except (ValueError, TypeError):
                    pass  # Skip if values are not numeric
    
    # Rule 2: remaining_amount should equal planned_amount - executed_amount (approximately)
    if all(col in df.columns for col in ["planned_amount", "executed_amount", "remaining_amount"]):
        for idx, row in df.iterrows():
            planned = row.get("planned_amount")
            executed = row.get("executed_amount")
            remaining = row.get("remaining_amount")
            
            if all(pd.notna(val) for val in [planned, executed, remaining]):
                try:
                    planned_val = float(planned)
                    executed_val = float(executed)
                    remaining_val = float(remaining)
                    
                    expected_remaining = planned_val - executed_val
                    # Allow small rounding differences (1% tolerance)
                    tolerance = abs(planned_val) * 0.01
                    
                    if abs(remaining_val - expected_remaining) > tolerance:
                        errors.append(ValidationError(
                            int(idx), "remaining_amount",
                            f"inconsistent_calculation:{expected_remaining:.2f}",
                            remaining, "warning"
                        ))
                except (ValueError, TypeError):
                    pass
    
    # Rule 3: execution_percentage should match (executed/planned)*100
    if all(col in df.columns for col in ["planned_amount", "executed_amount", "execution_percentage"]):
        for idx, row in df.iterrows():
            planned = row.get("planned_amount")
            executed = row.get("executed_amount")
            percentage = row.get("execution_percentage")
            
            if all(pd.notna(val) for val in [planned, executed, percentage]):
                try:
                    planned_val = float(planned)
                    executed_val = float(executed)
                    percentage_val = float(percentage)
                    
                    if planned_val != 0:
                        expected_percentage = (executed_val / planned_val) * 100
                        # Allow 1% tolerance
                        if abs(percentage_val - expected_percentage) > 1.0:
                            errors.append(ValidationError(
                                int(idx), "execution_percentage",
                                f"inconsistent_percentage:{expected_percentage:.1f}",
                                percentage, "warning"
                            ))
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
    
    return errors


def validate_and_get_summary(df: pd.DataFrame, profile: MappingProfile) -> Dict[str, Any]:
    """Validate DataFrame and return detailed summary statistics."""
    valid_df, errors_df = validate_dataframe(df, profile)
    
    summary = {
        "total_rows": len(df),
        "valid_rows": len(valid_df),
        "invalid_rows": len(df) - len(valid_df),
        "total_errors": len(errors_df),
        "error_rate": len(errors_df) / len(df) if len(df) > 0 else 0,
        "validation_passed": len(errors_df) == 0,
        "data_quality_score": len(valid_df) / len(df) if len(df) > 0 else 0
    }
    
    if not errors_df.empty:
        # Error breakdown by severity
        severity_counts = errors_df["severity"].value_counts().to_dict()
        summary["errors_by_severity"] = severity_counts
        
        # Error breakdown by column
        column_counts = errors_df["column"].value_counts().to_dict()
        summary["errors_by_column"] = column_counts
        
        # Error breakdown by reason
        reason_counts = errors_df["reason"].value_counts().to_dict()
        summary["errors_by_reason"] = reason_counts
    
    return summary