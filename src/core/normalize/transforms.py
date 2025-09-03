import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Union
import pandas as pd

try:
    from dateutil import parser as date_parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False
    date_parser = None

from src.logging_conf import get_logger
from src.core.mapping.profiles import MappingProfile, FieldType

logger = get_logger("transforms")


class NormalizationError(Exception):
    """Exception raised when normalization fails."""
    pass


class DataNormalizer:
    """Data normalization and transformation engine."""
    
    def __init__(self, profile: MappingProfile):
        self.profile = profile
        self.normalization_spec = profile.normalization
        
        # Compile regex patterns for performance
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for better performance."""
        self.patterns = {
            'whitespace': re.compile(r'\s+'),
            'decimal_number': re.compile(r'^-?\d+([,.\s]\d+)*([,.]\d+)?$'),
            'integer_number': re.compile(r'^-?\d+$'),
            'phone': re.compile(r'[\+\(\)\-\s\.]'),
            'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            'url': re.compile(r'^https?://[^\s<>"]+$'),
        }
    
    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize entire DataFrame according to profile."""
        logger.info("Starting dataframe normalization", 
                   rows=len(df), 
                   columns=len(df.columns),
                   profile=self.profile.profile)
        
        try:
            # Create a copy to avoid modifying original
            normalized_df = df.copy()
            
            # Basic cleanup
            if self.normalization_spec.trim_whitespace:
                normalized_df = self._trim_whitespace(normalized_df)
            
            if self.normalization_spec.normalize_unicode:
                normalized_df = self._normalize_unicode(normalized_df)
            
            # Column-specific normalization
            for target_column, field_spec in self.profile.columns.items():
                if target_column in normalized_df.columns:
                    normalized_df[target_column] = self._normalize_column(
                        normalized_df[target_column], field_spec
                    )
            
            logger.info("Dataframe normalization completed successfully")
            return normalized_df
            
        except Exception as e:
            error_msg = f"Dataframe normalization failed: {str(e)}"
            logger.error(error_msg)
            raise NormalizationError(error_msg) from e
    
    def _trim_whitespace(self, df: pd.DataFrame) -> pd.DataFrame:
        """Trim whitespace from string columns."""
        logger.debug("Trimming whitespace")
        
        string_columns = df.select_dtypes(include=['object']).columns
        for col in string_columns:
            df[col] = df[col].astype(str).str.strip()
            # Replace empty strings with NaN
            df[col] = df[col].replace('', pd.NA)
        
        return df
    
    def _normalize_unicode(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize Unicode characters."""
        logger.debug("Normalizing Unicode")
        
        import unicodedata
        
        string_columns = df.select_dtypes(include=['object']).columns
        for col in string_columns:
            df[col] = df[col].astype(str).apply(
                lambda x: unicodedata.normalize('NFKC', x) if pd.notna(x) and x != 'nan' else x
            )
        
        return df
    
    def _normalize_column(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize a single column according to its field specification."""
        logger.debug(f"Normalizing column with type {field_spec.type}")
        
        if field_spec.type == FieldType.STRING:
            return self._normalize_string(series, field_spec)
        elif field_spec.type == FieldType.INTEGER:
            return self._normalize_integer(series, field_spec)
        elif field_spec.type == FieldType.DECIMAL:
            return self._normalize_decimal(series, field_spec)
        elif field_spec.type == FieldType.DATE:
            return self._normalize_date(series, field_spec)
        elif field_spec.type == FieldType.DATETIME:
            return self._normalize_datetime(series, field_spec)
        elif field_spec.type == FieldType.BOOLEAN:
            return self._normalize_boolean(series, field_spec)
        elif field_spec.type == FieldType.EMAIL:
            return self._normalize_email(series, field_spec)
        elif field_spec.type == FieldType.PHONE:
            return self._normalize_phone(series, field_spec)
        elif field_spec.type == FieldType.URL:
            return self._normalize_url(series, field_spec)
        else:
            logger.warning(f"Unknown field type: {field_spec.type}")
            return series
    
    def _normalize_string(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize string values."""
        # Basic string cleaning
        normalized = series.astype(str)
        
        # Remove 'nan' strings
        normalized = normalized.replace('nan', pd.NA)
        
        # Apply transformations if specified
        if field_spec.transformation:
            if field_spec.transformation == 'upper':
                normalized = normalized.str.upper()
            elif field_spec.transformation == 'lower':
                normalized = normalized.str.lower()
            elif field_spec.transformation == 'title':
                normalized = normalized.str.title()
        
        return normalized
    
    def _normalize_integer(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize integer values."""
        normalized = series.copy()
        
        def clean_number(value):
            if pd.isna(value):
                return pd.NA
            
            # Convert to string for processing
            str_val = str(value).strip()
            if not str_val or str_val.lower() in ['nan', 'null', '']:
                return pd.NA
            
            # Remove thousand separators
            for sep in self.normalization_spec.thousand_sep:
                str_val = str_val.replace(sep, '')
            
            # Try to convert to integer
            try:
                return int(float(str_val))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert '{value}' to integer")
                return pd.NA
        
        return normalized.apply(clean_number)
    
    def _normalize_decimal(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize decimal values."""
        normalized = series.copy()
        
        def clean_decimal(value):
            if pd.isna(value):
                return pd.NA
            
            str_val = str(value).strip()
            if not str_val or str_val.lower() in ['nan', 'null', '']:
                return pd.NA
            
            # Handle European number format (e.g., "1 234,56")
            # First, remove thousand separators
            for thousand_sep in self.normalization_spec.thousand_sep:
                if thousand_sep in str_val:
                    parts = str_val.split(thousand_sep)
                    if len(parts) > 1:
                        # Check if this is actually a decimal separator
                        last_part = parts[-1]
                        if len(last_part) <= 3 and last_part.isdigit():
                            # This looks like a decimal part
                            str_val = ''.join(parts[:-1]) + '.' + last_part
                        else:
                            # This is a thousand separator
                            str_val = ''.join(parts)
            
            # Normalize decimal separator to dot
            for decimal_sep in self.normalization_spec.decimal_sep:
                if decimal_sep in str_val:
                    # Find the last occurrence (should be decimal separator)
                    last_sep_index = str_val.rfind(decimal_sep)
                    if last_sep_index != -1:
                        # Replace the last occurrence with dot
                        str_val = str_val[:last_sep_index] + '.' + str_val[last_sep_index + 1:]
                    break
            
            try:
                return float(str_val)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert '{value}' to decimal")
                return pd.NA
        
        return normalized.apply(clean_decimal)
    
    def _normalize_date(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize date values."""
        normalized = series.copy()
        
        def parse_date(value):
            if pd.isna(value):
                return pd.NA
            
            str_val = str(value).strip()
            if not str_val or str_val.lower() in ['nan', 'null', '']:
                return pd.NA
            
            # Try specified formats first
            if field_spec.format:
                formats = field_spec.format if isinstance(field_spec.format, list) else [field_spec.format]
                for fmt in formats:
                    try:
                        # Convert format from human readable to strptime
                        strp_format = self._convert_date_format(fmt)
                        parsed_date = datetime.strptime(str_val, strp_format).date()
                        return parsed_date
                    except ValueError:
                        continue
            
            # Try normalization spec formats
            for fmt in self.normalization_spec.date_formats:
                try:
                    parsed_date = datetime.strptime(str_val, fmt).date()
                    return parsed_date
                except ValueError:
                    continue
            
            # Try dateutil parser as last resort
            if DATEUTIL_AVAILABLE:
                try:
                    parsed_date = date_parser.parse(str_val, dayfirst=True).date()
                    return parsed_date
                except (ValueError, TypeError):
                    pass
            
            logger.warning(f"Could not parse date '{value}'")
            return pd.NA
        
        return normalized.apply(parse_date)
    
    def _normalize_datetime(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize datetime values."""
        normalized = series.copy()
        
        def parse_datetime(value):
            if pd.isna(value):
                return pd.NA
            
            str_val = str(value).strip()
            if not str_val or str_val.lower() in ['nan', 'null', '']:
                return pd.NA
            
            if DATEUTIL_AVAILABLE:
                try:
                    return date_parser.parse(str_val, dayfirst=True)
                except (ValueError, TypeError):
                    pass
            
            logger.warning(f"Could not parse datetime '{value}'")
            return pd.NA
        
        return normalized.apply(parse_datetime)
    
    def _normalize_boolean(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize boolean values."""
        normalized = series.copy()
        
        def parse_boolean(value):
            if pd.isna(value):
                return pd.NA
            
            str_val = str(value).strip().lower()
            if not str_val or str_val in ['nan', 'null', '']:
                return pd.NA
            
            # Check normalization spec boolean values
            for bool_str, bool_val in self.normalization_spec.boolean_values.items():
                if str_val == bool_str.lower():
                    return bool_val
            
            logger.warning(f"Could not parse boolean '{value}'")
            return pd.NA
        
        return normalized.apply(parse_boolean)
    
    def _normalize_email(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize email addresses."""
        normalized = self._normalize_string(series, field_spec)
        
        def validate_email(value):
            if pd.isna(value):
                return pd.NA
            
            str_val = str(value).strip().lower()
            if not str_val or str_val == 'nan':
                return pd.NA
            
            if self.patterns['email'].match(str_val):
                return str_val
            else:
                logger.warning(f"Invalid email format: '{value}'")
                return pd.NA
        
        return normalized.apply(validate_email)
    
    def _normalize_phone(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize phone numbers."""
        normalized = series.copy()
        
        def clean_phone(value):
            if pd.isna(value):
                return pd.NA
            
            str_val = str(value).strip()
            if not str_val or str_val.lower() in ['nan', 'null', '']:
                return pd.NA
            
            # Remove common phone number formatting
            cleaned = self.patterns['phone'].sub('', str_val)
            
            # Keep only digits and leading +
            if cleaned.startswith('+'):
                cleaned = '+' + re.sub(r'[^\d]', '', cleaned[1:])
            else:
                cleaned = re.sub(r'[^\d]', '', cleaned)
            
            return cleaned if cleaned else pd.NA
        
        return normalized.apply(clean_phone)
    
    def _normalize_url(self, series: pd.Series, field_spec) -> pd.Series:
        """Normalize URLs."""
        normalized = self._normalize_string(series, field_spec)
        
        def validate_url(value):
            if pd.isna(value):
                return pd.NA
            
            str_val = str(value).strip()
            if not str_val or str_val == 'nan':
                return pd.NA
            
            # Add protocol if missing
            if not str_val.startswith(('http://', 'https://')):
                str_val = 'https://' + str_val
            
            if self.patterns['url'].match(str_val):
                return str_val
            else:
                logger.warning(f"Invalid URL format: '{value}'")
                return pd.NA
        
        return normalized.apply(validate_url)
    
    def _convert_date_format(self, human_format: str) -> str:
        """Convert human-readable date format to strptime format."""
        format_mapping = {
            'YYYY': '%Y',
            'YY': '%y',
            'MM': '%m',
            'DD': '%d',
            'HH': '%H',
            'mm': '%M',
            'SS': '%S'
        }
        
        strp_format = human_format
        for human, strp in format_mapping.items():
            strp_format = strp_format.replace(human, strp)
        
        return strp_format


def normalize_dataframe(df: pd.DataFrame, profile: MappingProfile) -> pd.DataFrame:
    """Convenience function to normalize a DataFrame with a profile."""
    normalizer = DataNormalizer(profile)
    return normalizer.normalize_dataframe(df)


def apply_column_mapping(df: pd.DataFrame, column_mapping: Dict[str, str]) -> pd.DataFrame:
    """Apply column mapping to rename columns."""
    logger.info("Applying column mapping", mappings=len(column_mapping))
    
    # Create a copy and rename columns
    mapped_df = df.copy()
    mapped_df = mapped_df.rename(columns=column_mapping)
    
    # Log any unmapped columns
    unmapped_columns = [col for col in df.columns if col not in column_mapping]
    if unmapped_columns:
        logger.warning("Unmapped columns found", columns=unmapped_columns)
    
    return mapped_df