import re
import unicodedata
from typing import Dict, List, Optional, Tuple, Set
import pandas as pd

try:
    from Levenshtein import distance as levenshtein_distance
    LEVENSHTEIN_AVAILABLE = True
except ImportError:
    LEVENSHTEIN_AVAILABLE = False
    
    # Fallback implementation
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Simple Levenshtein distance implementation."""
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]

from src.logging_conf import get_logger

logger = get_logger("matcher")


class HeaderMatcher:
    """Intelligent header matching with fuzzy matching and multilingual support."""
    
    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        
        # Common word mappings for normalization
        self.word_mappings = {
            # Bulgarian -> English
            'сума': 'amount',
            'стойност': 'value',
            'период': 'period',
            'дата': 'date',
            'месец': 'month',
            'година': 'year',
            'отдел': 'department',
            'име': 'name',
            'код': 'code',
            'номер': 'number',
            'описание': 'description',
            'тип': 'type',
            'статус': 'status',
            'адрес': 'address',
            'телефон': 'phone',
            'email': 'email',
            'фирма': 'company',
            'организация': 'organization',
            
            # Common variations
            'amt': 'amount',
            'qty': 'quantity',
            'количество': 'quantity',
            'брой': 'count',
            'цена': 'price',
            'единична_цена': 'unit_price',
            'обща_сума': 'total_amount',
            
            # Symbols and units
            '%': ' percent ',
            
            # Date variations
            'дд.мм.гггг': 'date',
            'yyyy-mm-dd': 'date',
            'mm/dd/yyyy': 'date',
            
            # Status variations
            'активен': 'active',
            'неактивен': 'inactive',
            'завършен': 'completed',
            'в_процес': 'in_progress',
        }
        
        # Cyrillic to Latin transliteration map (Bulgarian)
        self.cyrillic_to_latin = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l',
            'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's',
            'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch',
            'ш': 'sh', 'щ': 'sht', 'ь': 'y', 'ю': 'yu', 'я': 'ya',
            'ъ': 'a', 'ѝ': 'i'
        }
    
    def normalize_header(self, header: str) -> str:
        """Normalize header for comparison."""
        if not header or pd.isna(header):
            return ""
        
        # Convert to string and strip
        header = str(header).strip()
        
        # Convert to lowercase
        header = header.lower()
        
        # Remove Unicode categories that are typically decorative
        header = ''.join(c for c in header 
                        if unicodedata.category(c) not in ['Mn', 'Mc', 'Me'])
        
        # Replace common word mappings
        for bg_word, en_word in self.word_mappings.items():
            if bg_word in header:
                header = header.replace(bg_word, en_word)
        
        # Transliterate Cyrillic to Latin
        transliterated = ""
        for char in header:
            if char in self.cyrillic_to_latin:
                transliterated += self.cyrillic_to_latin[char]
            else:
                transliterated += char
        header = transliterated
        
        # Normalize punctuation and whitespace
        header = re.sub(r'[^\w\s]', ' ', header)  # Replace punctuation with spaces
        header = re.sub(r'\s+', '_', header.strip())  # Replace spaces with underscores
        
        # Remove leading/trailing underscores
        header = header.strip('_')
        
        return header
    
    def calculate_similarity(self, header1: str, header2: str) -> float:
        """Calculate similarity between two headers."""
        if not header1 or not header2:
            return 0.0
        
        # Normalize both headers
        norm1 = self.normalize_header(header1)
        norm2 = self.normalize_header(header2)
        
        if not norm1 or not norm2:
            return 0.0
        
        if norm1 == norm2:
            return 1.0
        
        # Calculate Levenshtein distance
        max_len = max(len(norm1), len(norm2))
        if max_len == 0:
            return 1.0
        
        distance = levenshtein_distance(norm1, norm2)
        similarity = 1.0 - (distance / max_len)
        
        # Bonus for exact substring matches
        if norm1 in norm2 or norm2 in norm1:
            similarity = min(1.0, similarity + 0.1)
        
        # Bonus for common prefixes/suffixes
        if norm1.startswith(norm2[:3]) or norm2.startswith(norm1[:3]):
            similarity = min(1.0, similarity + 0.05)
        
        return similarity
    
    def detect_headers(self, df: pd.DataFrame, start_row: int = 0, max_rows_to_check: int = 10) -> Tuple[int, List[str]]:
        """Detect which row contains the headers and extract them."""
        logger.debug("Detecting headers in dataframe", shape=df.shape)
        
        if df.empty:
            return 0, []
        
        best_row = start_row
        best_score = 0
        best_headers = []
        
        # Check multiple rows to find the one that looks most like headers
        max_check = min(start_row + max_rows_to_check, len(df))
        
        for row_idx in range(start_row, max_check):
            try:
                potential_headers = df.iloc[row_idx].astype(str).tolist()
                score = self._score_potential_headers(potential_headers)
                
                if score > best_score:
                    best_score = score
                    best_row = row_idx
                    best_headers = potential_headers
                    
            except IndexError:
                break
        
        logger.debug("Header detection completed", 
                    header_row=best_row, 
                    score=best_score,
                    num_headers=len(best_headers))
        
        return best_row, best_headers
    
    def _score_potential_headers(self, headers: List[str]) -> float:
        """Score a row to determine if it looks like headers."""
        if not headers:
            return 0.0
        
        score = 0.0
        total_headers = len(headers)
        
        for header in headers:
            header_str = str(header).strip()
            
            # Skip empty or very short headers
            if not header_str or len(header_str) < 2:
                continue
            
            # Positive indicators
            if header_str and header_str != 'nan':
                score += 1.0  # Non-empty
            
            if not header_str.isdigit():
                score += 0.5  # Not a number
            
            if len(header_str) > 2:
                score += 0.3  # Reasonable length
            
            if any(c.isalpha() for c in header_str):
                score += 0.5  # Contains letters
            
            # Check for common header patterns
            normalized = self.normalize_header(header_str)
            if any(word in normalized for word in ['id', 'name', 'date', 'amount', 'code', 'type']):
                score += 0.5
            
            # Negative indicators
            if header_str.startswith(('Row', 'row', 'Ред', 'ред')):
                score -= 0.5  # Looks like row indicator
        
        # Normalize score by number of headers
        return score / max(total_headers, 1)
    
    def find_best_matches(
        self, 
        source_headers: List[str], 
        target_headers: List[str],
        min_similarity: Optional[float] = None
    ) -> Dict[str, Tuple[str, float]]:
        """Find best matches between source and target headers.
        
        Args:
            source_headers: Headers from the input file
            target_headers: Expected headers from the mapping profile
            min_similarity: Minimum similarity threshold (uses instance default if None)
        
        Returns:
            Dict mapping target headers to (best_source_header, similarity_score)
        """
        if min_similarity is None:
            min_similarity = self.similarity_threshold
        
        logger.debug("Finding header matches", 
                    source_count=len(source_headers),
                    target_count=len(target_headers),
                    min_similarity=min_similarity)
        
        matches = {}
        used_source_headers = set()
        
        # Calculate all similarities
        similarities = {}
        for target_header in target_headers:
            similarities[target_header] = []
            for source_header in source_headers:
                similarity = self.calculate_similarity(source_header, target_header)
                similarities[target_header].append((source_header, similarity))
            
            # Sort by similarity (descending)
            similarities[target_header].sort(key=lambda x: x[1], reverse=True)
        
        # Sort target headers by best available match (to process highest confidence first)
        sorted_targets = sorted(
            target_headers,
            key=lambda t: similarities[t][0][1] if similarities[t] else 0,
            reverse=True
        )
        
        for target_header in sorted_targets:
            best_match = None
            best_similarity = 0
            
            # Find best unused match above threshold
            for source_header, similarity in similarities[target_header]:
                if (similarity >= min_similarity and 
                    source_header not in used_source_headers and
                    similarity > best_similarity):
                    best_match = source_header
                    best_similarity = similarity
            
            if best_match:
                matches[target_header] = (best_match, best_similarity)
                used_source_headers.add(best_match)
        
        logger.debug("Header matching completed", 
                    matches_found=len(matches),
                    total_targets=len(target_headers))
        
        return matches
    
    def suggest_mappings(
        self, 
        df: pd.DataFrame, 
        target_schema: Dict[str, any],
        header_row: Optional[int] = None
    ) -> Dict[str, any]:
        """Suggest column mappings based on header analysis.
        
        Args:
            df: Input DataFrame
            target_schema: Expected schema with field definitions
            header_row: Row index containing headers (auto-detect if None)
        
        Returns:
            Dictionary with suggested mappings and metadata
        """
        logger.info("Suggesting column mappings", shape=df.shape)
        
        # Detect headers if not provided
        if header_row is None:
            header_row, source_headers = self.detect_headers(df)
        else:
            source_headers = df.iloc[header_row].astype(str).tolist()
        
        # Get target headers from schema
        target_headers = list(target_schema.get('columns', {}).keys())
        
        # Find best matches
        matches = self.find_best_matches(source_headers, target_headers)
        
        # Analyze unmatched headers
        matched_sources = {match[0] for match in matches.values()}
        unmatched_sources = [h for h in source_headers if h not in matched_sources]
        unmatched_targets = [h for h in target_headers if h not in matches]
        
        # Build result
        result = {
            'header_row': header_row,
            'source_headers': source_headers,
            'target_headers': target_headers,
            'matches': matches,
            'unmatched_sources': unmatched_sources,
            'unmatched_targets': unmatched_targets,
            'confidence': len(matches) / max(len(target_headers), 1),
        }
        
        logger.info("Mapping suggestions completed",
                   matches=len(matches),
                   unmatched_sources=len(unmatched_sources),
                   unmatched_targets=len(unmatched_targets),
                   confidence=result['confidence'])
        
        return result
    
    def create_column_mapping(
        self,
        matches: Dict[str, Tuple[str, float]],
        target_schema: Dict[str, any]
    ) -> Dict[str, str]:
        """Create a simple column mapping from match results.
        
        Args:
            matches: Results from find_best_matches
            target_schema: Target schema definition
            
        Returns:
            Dictionary mapping source columns to target columns
        """
        mapping = {}
        for target_col, (source_col, _) in matches.items():
            mapping[source_col] = target_col
        
        return mapping


# Utility functions

def detect_headers(df: pd.DataFrame, **kwargs) -> Tuple[int, List[str]]:
    """Convenience function to detect headers in a DataFrame."""
    matcher = HeaderMatcher()
    return matcher.detect_headers(df, **kwargs)


def find_column_matches(
    source_headers: List[str], 
    target_headers: List[str],
    similarity_threshold: float = 0.7
) -> Dict[str, Tuple[str, float]]:
    """Convenience function to find column matches."""
    matcher = HeaderMatcher(similarity_threshold)
    return matcher.find_best_matches(source_headers, target_headers)
