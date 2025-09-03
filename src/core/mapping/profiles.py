import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from pydantic import BaseModel, Field, validator
from enum import Enum

from src.logging_conf import get_logger
from src.settings import settings

logger = get_logger("profiles")


class FieldType(str, Enum):
    """Supported field types for mapping."""
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"


class FieldSpec(BaseModel):
    """Specification for a single field in a mapping profile."""
    sources: List[str] = Field(..., description="List of possible source column names")
    type: FieldType = Field(FieldType.STRING, description="Data type of the field")
    format: Optional[Union[str, List[str]]] = Field(None, description="Format specification for dates/numbers")
    required: bool = Field(False, description="Whether this field is required")
    default: Optional[Any] = Field(None, description="Default value if field is missing")
    validation: Optional[Dict[str, Any]] = Field(None, description="Validation rules")
    transformation: Optional[str] = Field(None, description="Transformation to apply")
    description: Optional[str] = Field(None, description="Human-readable description")

    @validator('sources')
    def sources_not_empty(cls, v):
        if not v:
            raise ValueError("Sources list cannot be empty")
        return v

    @validator('format')
    def format_for_type(cls, v, values):
        field_type = values.get('type')
        if field_type == FieldType.DATE and v:
            # Ensure date formats are valid
            if isinstance(v, str):
                v = [v]
            valid_formats = [
                "YYYY-MM-DD", "DD.MM.YYYY", "DD/MM/YYYY", 
                "MM/DD/YYYY", "YYYY-MM", "DD.MM.YY"
            ]
            for fmt in v:
                if not any(pattern in fmt for pattern in ['Y', 'M', 'D']):
                    logger.warning(f"Date format {fmt} may not be valid")
        return v


class NormalizationSpec(BaseModel):
    """Specification for data normalization rules."""
    thousand_sep: List[str] = Field(default_factory=lambda: [" ", ","])
    decimal_sep: List[str] = Field(default_factory=lambda: [",", "."])
    trim_whitespace: bool = Field(True)
    encoding: str = Field("utf-8")
    remove_bom: bool = Field(True)
    normalize_unicode: bool = Field(True)
    date_formats: List[str] = Field(default_factory=lambda: [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m", "%d.%m.%y"
    ])
    boolean_values: Dict[str, bool] = Field(default_factory=lambda: {
        "да": True, "не": False, "yes": True, "no": False,
        "true": True, "false": False, "1": True, "0": False,
        "активен": True, "неактивен": False, "active": True, "inactive": False
    })


class ValidationSpec(BaseModel):
    """Specification for validation rules."""
    allow_empty: bool = Field(True, description="Allow empty values")
    min_length: Optional[int] = Field(None, description="Minimum string length")
    max_length: Optional[int] = Field(None, description="Maximum string length")
    min_value: Optional[float] = Field(None, description="Minimum numeric value")
    max_value: Optional[float] = Field(None, description="Maximum numeric value")
    pattern: Optional[str] = Field(None, description="Regex pattern to match")
    enum_values: Optional[List[str]] = Field(None, description="List of allowed values")
    unique: bool = Field(False, description="Values must be unique across rows")
    date_range: Optional[Dict[str, str]] = Field(None, description="Date range validation")


class OutputSpec(BaseModel):
    """Specification for output format."""
    format: str = Field("csv", description="Output format (csv, json, xml)")
    filename_template: str = Field("{profile}_{org_id}_{timestamp}", description="Filename template")
    include_metadata: bool = Field(True, description="Include metadata file")
    encoding: str = Field("utf-8", description="Output encoding")
    date_format: str = Field("%Y-%m-%d", description="Date format in output")
    decimal_places: int = Field(2, description="Decimal places for numbers")
    null_representation: str = Field("", description="How to represent null values")


class MappingProfile(BaseModel):
    """Complete mapping profile specification."""
    profile: str = Field(..., description="Profile identifier")
    version: str = Field("1.0", description="Profile version")
    description: Optional[str] = Field(None, description="Profile description")
    
    # Core mapping
    columns: Dict[str, FieldSpec] = Field(..., description="Column specifications")
    
    # Processing rules
    normalization: NormalizationSpec = Field(default_factory=NormalizationSpec)
    validation: ValidationSpec = Field(default_factory=ValidationSpec)
    output: OutputSpec = Field(default_factory=OutputSpec)
    
    # Metadata
    created_by: Optional[str] = Field(None)
    created_at: Optional[str] = Field(None)
    tags: List[str] = Field(default_factory=list)

    @validator('profile')
    def profile_valid(cls, v):
        if not v or not v.strip():
            raise ValueError("Profile identifier cannot be empty")
        # Only allow alphanumeric, underscore, and hyphen
        if not all(c.isalnum() or c in '_-' for c in v):
            raise ValueError("Profile identifier can only contain alphanumeric characters, underscores, and hyphens")
        return v.strip().lower()

    def get_source_columns(self) -> List[str]:
        """Get all possible source column names."""
        sources = []
        for field_spec in self.columns.values():
            sources.extend(field_spec.sources)
        return list(set(sources))

    def get_required_fields(self) -> List[str]:
        """Get list of required field names."""
        return [name for name, spec in self.columns.items() if spec.required]

    def get_field_by_source(self, source_column: str) -> Optional[Tuple[str, FieldSpec]]:
        """Find field specification by source column name."""
        for field_name, field_spec in self.columns.items():
            if source_column in field_spec.sources:
                return field_name, field_spec
        return None


class ProfileManager:
    """Manager for loading, saving, and working with mapping profiles."""
    
    def __init__(self, profiles_dir: Optional[Path] = None):
        self.profiles_dir = profiles_dir or (settings.data_dir / "profiles")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profiles_cache: Dict[str, MappingProfile] = {}
    
    def load_profile(self, profile_name: str) -> Optional[MappingProfile]:
        """Load a mapping profile from file."""
        # Check cache first
        if profile_name in self._profiles_cache:
            return self._profiles_cache[profile_name]
        
        profile_file = self.profiles_dir / f"{profile_name}.yaml"
        if not profile_file.exists():
            logger.warning(f"Profile file not found: {profile_file}")
            return None
        
        try:
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile_data = yaml.safe_load(f)
            
            profile = MappingProfile(**profile_data)
            self._profiles_cache[profile_name] = profile
            
            logger.info(f"Loaded mapping profile: {profile_name}")
            return profile
            
        except Exception as e:
            logger.error(f"Failed to load profile {profile_name}: {str(e)}")
            return None
    
    def save_profile(self, profile: MappingProfile, overwrite: bool = False) -> bool:
        """Save a mapping profile to file."""
        profile_file = self.profiles_dir / f"{profile.profile}.yaml"
        
        if profile_file.exists() and not overwrite:
            logger.error(f"Profile file already exists: {profile_file}")
            return False
        
        try:
            # Convert to dict and clean up for YAML serialization
            profile_dict = profile.dict()
            
            # Add created timestamp if not set
            if not profile_dict.get('created_at'):
                from datetime import datetime
                profile_dict['created_at'] = datetime.now().isoformat()
            
            with open(profile_file, 'w', encoding='utf-8') as f:
                yaml.dump(profile_dict, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            
            # Update cache
            self._profiles_cache[profile.profile] = profile
            
            logger.info(f"Saved mapping profile: {profile.profile}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save profile {profile.profile}: {str(e)}")
            return False
    
    def list_profiles(self) -> List[str]:
        """List available profile names."""
        profile_files = list(self.profiles_dir.glob("*.yaml"))
        return [f.stem for f in profile_files]
    
    def delete_profile(self, profile_name: str) -> bool:
        """Delete a mapping profile."""
        profile_file = self.profiles_dir / f"{profile_name}.yaml"
        
        if not profile_file.exists():
            logger.warning(f"Profile file not found: {profile_file}")
            return False
        
        try:
            profile_file.unlink()
            
            # Remove from cache
            if profile_name in self._profiles_cache:
                del self._profiles_cache[profile_name]
            
            logger.info(f"Deleted mapping profile: {profile_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete profile {profile_name}: {str(e)}")
            return False
    
    def create_profile_from_data(
        self,
        profile_name: str,
        sample_headers: List[str],
        target_schema: Dict[str, Any],
        description: Optional[str] = None
    ) -> MappingProfile:
        """Create a new profile based on sample data and target schema."""
        from datetime import datetime
        
        columns = {}
        for target_field, field_config in target_schema.get('columns', {}).items():
            # Find matching headers using fuzzy matching
            from .matcher import HeaderMatcher
            matcher = HeaderMatcher()
            
            potential_sources = []
            for header in sample_headers:
                similarity = matcher.calculate_similarity(header, target_field)
                if similarity > 0.5:  # Lower threshold for suggestions
                    potential_sources.append(header)
            
            # If no good matches, use the target field name as source
            if not potential_sources:
                potential_sources = [target_field]
            
            columns[target_field] = FieldSpec(
                sources=potential_sources,
                type=FieldType(field_config.get('type', 'string')),
                format=field_config.get('format'),
                required=field_config.get('required', False),
                default=field_config.get('default'),
                description=field_config.get('description')
            )
        
        profile = MappingProfile(
            profile=profile_name,
            description=description or f"Auto-generated profile for {profile_name}",
            columns=columns,
            created_by="system",
            created_at=datetime.now().isoformat()
        )
        
        return profile


# Global profile manager instance
profile_manager = ProfileManager()


def load_profile(profile_name: str) -> Optional[MappingProfile]:
    """Convenience function to load a profile."""
    return profile_manager.load_profile(profile_name)


def save_profile(profile: MappingProfile, overwrite: bool = False) -> bool:
    """Convenience function to save a profile."""
    return profile_manager.save_profile(profile, overwrite)


def list_profiles() -> List[str]:
    """Convenience function to list available profiles."""
    return profile_manager.list_profiles()