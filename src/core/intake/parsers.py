import csv
import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import chardet
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from src.logging_conf import get_logger
from src.settings import settings

logger = get_logger("parsers")


class ParseError(Exception):
    """Exception raised when file parsing fails."""
    pass


class FileParser:
    """Base class for file parsers."""
    
    def __init__(self):
        self.supported_extensions = []
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file."""
        return file_path.suffix.lower() in self.supported_extensions
    
    def parse(self, file_path: Path, **options) -> pd.DataFrame:
        """Parse the file and return a DataFrame."""
        raise NotImplementedError


class CSVParser(FileParser):
    """Parser for CSV files with encoding detection and normalization."""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.csv', '.tsv', '.txt']
    
    def detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding using chardet."""
        logger.debug("Detecting encoding", file=str(file_path))
        
        # Read sample of file for detection
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)  # Read first 10KB
        
        if not raw_data:
            return 'utf-8'
        
        detection = chardet.detect(raw_data)
        encoding = detection.get('encoding', 'utf-8')
        confidence = detection.get('confidence', 0.0)
        
        logger.debug("Encoding detected", 
                    encoding=encoding, 
                    confidence=confidence,
                    file=str(file_path))
        
        # Fallback to common encodings if confidence is low
        if confidence < 0.7:
            for fallback in ['utf-8', 'cp1251', 'iso-8859-1', 'windows-1252']:
                try:
                    with open(file_path, 'r', encoding=fallback) as f:
                        f.read(1000)
                    logger.debug("Using fallback encoding", encoding=fallback)
                    return fallback
                except (UnicodeDecodeError, UnicodeError):
                    continue
        
        return encoding or 'utf-8'
    
    def detect_delimiter(self, file_path: Path, encoding: str, sample_size: int = 1024) -> str:
        """Detect CSV delimiter."""
        logger.debug("Detecting delimiter", file=str(file_path))
        
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as f:
                sample = f.read(sample_size)
            
            # Use csv.Sniffer to detect delimiter
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample, delimiters=',;\t|')
                delimiter = dialect.delimiter
            except csv.Error:
                # Fallback: count occurrences of common delimiters
                delimiters = {',': sample.count(','), 
                            ';': sample.count(';'),
                            '\t': sample.count('\t'),
                            '|': sample.count('|')}
                delimiter = max(delimiters, key=delimiters.get)
                if delimiters[delimiter] == 0:
                    delimiter = ','  # Default fallback
            
            logger.debug("Delimiter detected", delimiter=repr(delimiter))
            return delimiter
            
        except Exception as e:
            logger.warning("Failed to detect delimiter, using comma", error=str(e))
            return ','
    
    def detect_decimal_separator(self, df: pd.DataFrame) -> Tuple[str, str]:
        """Detect thousand and decimal separators from numeric-looking columns."""
        logger.debug("Detecting decimal separators")
        
        # Look for columns that might contain numbers
        numeric_patterns = []
        for col in df.select_dtypes(include=['object']).columns:
            sample_values = df[col].dropna().astype(str).head(100)
            for val in sample_values:
                val = val.strip()
                if val and any(c.isdigit() for c in val):
                    numeric_patterns.append(val)
        
        # Analyze patterns to determine separators
        has_comma_decimal = any(',' in p and p.rindex(',') > p.rfind(' ') for p in numeric_patterns)
        has_dot_decimal = any('.' in p and p.rindex('.') > p.rfind(' ') for p in numeric_patterns) 
        has_space_thousand = any(' ' in p and any(c.isdigit() for c in p) for p in numeric_patterns)
        has_comma_thousand = any(p.count(',') > 1 for p in numeric_patterns)
        
        # European format (1 234,56)
        if has_comma_decimal and has_space_thousand:
            thousand_sep, decimal_sep = ' ', ','
        # European format without space (1234,56)  
        elif has_comma_decimal and not has_dot_decimal:
            thousand_sep, decimal_sep = '', ','
        # US format (1,234.56)
        elif has_dot_decimal and has_comma_thousand:
            thousand_sep, decimal_sep = ',', '.'
        # Simple decimal (1234.56)
        elif has_dot_decimal:
            thousand_sep, decimal_sep = '', '.'
        else:
            # Default to locale-neutral
            thousand_sep, decimal_sep = '', '.'
        
        logger.debug("Decimal separators detected", 
                    thousand_sep=repr(thousand_sep), 
                    decimal_sep=repr(decimal_sep))
        return thousand_sep, decimal_sep
    
    def parse(self, file_path: Path, **options) -> pd.DataFrame:
        """Parse CSV file with automatic encoding and delimiter detection."""
        logger.info("Parsing CSV file", file=str(file_path))
        
        # Get options with defaults
        encoding = options.get('encoding')
        delimiter = options.get('delimiter')
        skip_rows = options.get('skip_rows', 0)
        max_rows = options.get('max_rows')
        
        try:
            # Detect encoding if not provided
            if not encoding:
                encoding = self.detect_encoding(file_path)
            
            # Detect delimiter if not provided
            if not delimiter:
                delimiter = self.detect_delimiter(file_path, encoding)
            
            # Read CSV
            read_kwargs = {
                'encoding': encoding,
                'sep': delimiter,
                'skiprows': skip_rows,
                'na_values': ['', 'NA', 'N/A', 'NULL', 'null', '#N/A', '#NULL!'],
                'keep_default_na': True,
                'dtype': str,  # Read everything as string initially
            }
            
            if max_rows:
                read_kwargs['nrows'] = max_rows
            
            df = pd.read_csv(file_path, **read_kwargs)
            
            # Basic cleanup
            df = self._cleanup_dataframe(df)
            
            logger.info("CSV parsing completed", 
                       rows=len(df), 
                       columns=len(df.columns),
                       encoding=encoding,
                       delimiter=repr(delimiter))
            
            return df
            
        except Exception as e:
            error_msg = f"Failed to parse CSV file {file_path}: {str(e)}"
            logger.error(error_msg)
            raise ParseError(error_msg) from e
    
    def _cleanup_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Basic DataFrame cleanup."""
        # Remove completely empty rows and columns
        df = df.dropna(how='all', axis=0)  # Remove empty rows
        df = df.dropna(how='all', axis=1)  # Remove empty columns
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Remove rows where all values are just whitespace
        string_cols = df.select_dtypes(include=['object']).columns
        for col in string_cols:
            df[col] = df[col].astype(str).str.strip()
        
        # Reset index
        df = df.reset_index(drop=True)
        
        return df


class ExcelParser(FileParser):
    """Parser for Excel files (XLSX, XLS)."""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.xlsx', '.xls']
    
    def get_sheet_names(self, file_path: Path) -> List[str]:
        """Get list of sheet names in the Excel file."""
        try:
            if file_path.suffix.lower() == '.xlsx':
                wb = load_workbook(file_path, read_only=True, data_only=True)
                return wb.sheetnames
            else:
                # For .xls files, use pandas
                xls = pd.ExcelFile(file_path)
                return xls.sheet_names
        except Exception as e:
            logger.error("Failed to read Excel sheet names", file=str(file_path), error=str(e))
            return []
    
    def parse(self, file_path: Path, **options) -> pd.DataFrame:
        """Parse Excel file."""
        logger.info("Parsing Excel file", file=str(file_path))
        
        # Get options with defaults
        sheet_name = options.get('sheet_name', 0)  # First sheet by default
        skip_rows = options.get('skip_rows', 0)
        max_rows = options.get('max_rows')
        header_row = options.get('header_row', 0)
        
        try:
            read_kwargs = {
                'sheet_name': sheet_name,
                'skiprows': skip_rows,
                'header': header_row,
                'na_values': ['', 'NA', 'N/A', 'NULL', 'null', '#N/A', '#NULL!', '#DIV/0!'],
                'keep_default_na': True,
                'dtype': str,  # Read everything as string initially
            }
            
            if max_rows:
                read_kwargs['nrows'] = max_rows
            
            # Use openpyxl engine for .xlsx files for better Unicode support
            if file_path.suffix.lower() == '.xlsx':
                read_kwargs['engine'] = 'openpyxl'
            
            df = pd.read_excel(file_path, **read_kwargs)
            
            # Basic cleanup
            df = self._cleanup_dataframe(df)
            
            logger.info("Excel parsing completed", 
                       rows=len(df), 
                       columns=len(df.columns),
                       sheet=sheet_name)
            
            return df
            
        except InvalidFileException as e:
            error_msg = f"Invalid Excel file {file_path}: {str(e)}"
            logger.error(error_msg)
            raise ParseError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to parse Excel file {file_path}: {str(e)}"
            logger.error(error_msg)
            raise ParseError(error_msg) from e
    
    def _cleanup_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Basic DataFrame cleanup."""
        # Remove completely empty rows and columns
        df = df.dropna(how='all', axis=0)
        df = df.dropna(how='all', axis=1)
        
        # Clean column names - handle unnamed columns from Excel
        cleaned_columns = []
        unnamed_count = 1
        for col in df.columns:
            if pd.isna(col) or str(col).startswith('Unnamed:'):
                cleaned_columns.append(f'Column_{unnamed_count}')
                unnamed_count += 1
            else:
                cleaned_columns.append(str(col).strip())
        
        df.columns = cleaned_columns
        
        # Clean string values
        string_cols = df.select_dtypes(include=['object']).columns
        for col in string_cols:
            df[col] = df[col].astype(str).str.strip()
            # Replace 'nan' strings with actual NaN
            df[col] = df[col].replace('nan', pd.NA)
        
        # Reset index
        df = df.reset_index(drop=True)
        
        return df


class FileParserFactory:
    """Factory class for creating appropriate file parsers."""
    
    def __init__(self):
        self.parsers = [
            CSVParser(),
            ExcelParser(),
        ]
    
    def get_parser(self, file_path: Path) -> Optional[FileParser]:
        """Get appropriate parser for the file."""
        for parser in self.parsers:
            if parser.can_parse(file_path):
                return parser
        return None
    
    def parse_file(self, file_path: Path, **options) -> pd.DataFrame:
        """Parse file using appropriate parser."""
        if isinstance(file_path, str):
            file_path = Path(file_path)
        
        if not file_path.exists():
            raise ParseError(f"File not found: {file_path}")
        
        # Check file size
        file_size = file_path.stat().st_size
        if hasattr(settings, 'max_file_size') and file_size > settings.max_file_size:
            raise ParseError(f"File too large: {file_size} bytes (max: {settings.max_file_size})")
        
        # Check file extension (normalize dotless, lowercase)
        ext = file_path.suffix.lower().lstrip('.')
        allowed = {e.lower().lstrip('.') for e in settings.allowed_file_extensions}
        if ext not in allowed:
            raise ParseError(f"File type not allowed: .{ext}")
        
        parser = self.get_parser(file_path)
        if not parser:
            raise ParseError(f"No parser available for file type: {file_path.suffix}")
        
        logger.info("Starting file parsing", 
                   file=str(file_path), 
                   size_bytes=file_size,
                   parser=parser.__class__.__name__)
        
        try:
            df = parser.parse(file_path, **options)
            
            logger.info("File parsing completed successfully", 
                       file=str(file_path),
                       rows=len(df),
                       columns=len(df.columns))
            
            return df
            
        except ParseError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error parsing file {file_path}: {str(e)}"
            logger.error(error_msg)
            raise ParseError(error_msg) from e


# Global factory instance
parser_factory = FileParserFactory()


def load_frame(file_path: Union[str, Path], **options) -> pd.DataFrame:
    """Load a file into a DataFrame using the appropriate parser.
    
    Args:
        file_path: Path to the file to parse
        **options: Parser-specific options
        
    Returns:
        pandas.DataFrame: Parsed data
        
    Raises:
        ParseError: If parsing fails
    """
    return parser_factory.parse_file(Path(file_path), **options)
