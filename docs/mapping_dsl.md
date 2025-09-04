Mapping DSL Overview

Purpose: Define column mapping, normalization, validation, and output rules per profile.

- Location: `data/profiles/*.yaml`
- Model: `src/core/mapping/profiles.py` (`MappingProfile`, `FieldSpec`, etc.)

Key fields:
- `columns`: target field → `FieldSpec` with `sources[]`, `type`, `required`, `validation{}`, `transformation`
- `normalization`: thousand/decimal separators, date formats, boolean values
- `validation`: global rules (e.g., date_range)
- `output`: filename template, encoding, decimal places

Helper APIs:
- `HeaderMatcher.detect_headers(df)` and `find_best_matches`
- `apply_column_mapping(df, mapping)` then `normalize_dataframe(df, profile)`

