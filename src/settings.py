from typing import List, Optional
from pathlib import Path
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    database_url: str = Field(default="sqlite:///./compliance_kit.db", env="DATABASE_URL")
    
    # Application Settings
    app_name: str = Field(default="Compliance Automation Kit", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    secret_key: str = Field(default="dev-secret-key", env="SECRET_KEY")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    reload: bool = Field(default=False, env="RELOAD")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_file: Optional[str] = Field(default="logs/compliance_kit.log", env="LOG_FILE")
    
    # File Storage
    data_dir: Path = Field(default=Path("data"), env="DATA_DIR")
    upload_dir: Path = Field(default=Path("uploads"), env="UPLOAD_DIR")
    output_dir: Path = Field(default=Path("outputs"), env="OUTPUT_DIR")
    max_file_size: str = Field(default="100MB", env="MAX_FILE_SIZE")
    
    # CKAN Integration
    ckan_url: Optional[str] = Field(default=None, env="CKAN_URL")
    ckan_api_key: Optional[str] = Field(default=None, env="CKAN_API_KEY")
    ckan_organization: Optional[str] = Field(default=None, env="CKAN_ORGANIZATION")
    ckan_timeout: int = Field(default=30, env="CKAN_TIMEOUT")
    ckan_max_retries: int = Field(default=3, env="CKAN_MAX_RETRIES")
    ckan_backoff_factor: float = Field(default=1.0, env="CKAN_BACKOFF_FACTOR")
    
    # FTP Integration
    ftp_host: Optional[str] = Field(default=None, env="FTP_HOST")
    ftp_port: int = Field(default=21, env="FTP_PORT")
    ftp_user: Optional[str] = Field(default=None, env="FTP_USER")
    ftp_password: Optional[str] = Field(default=None, env="FTP_PASSWORD")
    ftp_path: str = Field(default="/compliance-data", env="FTP_PATH")
    
    # Security Settings
    allowed_file_extensions: List[str] = Field(
        # Narrow to currently supported intake types; broaden as parsers are added
        default=["csv", "tsv", "txt", "xlsx", "xls"],
        env="ALLOWED_FILE_EXTENSIONS"
    )
    pii_redaction_enabled: bool = Field(default=True, env="PII_REDACTION_ENABLED")
    pii_redaction_fields: List[str] = Field(
        default=["email", "phone", "ssn", "tax_id", "bank_account"],
        env="PII_REDACTION_FIELDS"
    )
    
    # Scheduler Settings
    scheduler_timezone: str = Field(default="Europe/Sofia", env="SCHEDULER_TIMEZONE")
    scheduler_max_workers: int = Field(default=4, env="SCHEDULER_MAX_WORKERS")
    scheduler_coalesce: bool = Field(default=True, env="SCHEDULER_COALESCE")
    scheduler_misfire_grace_time: int = Field(default=30, env="SCHEDULER_MISFIRE_GRACE_TIME")
    
    # OCR Settings
    tesseract_cmd: str = Field(default="tesseract", env="TESSERACT_CMD")
    ocr_languages: List[str] = Field(default=["eng", "bul"], env="OCR_LANGUAGES")
    ocr_config: str = Field(default="--psm 6", env="OCR_CONFIG")
    
    # Email Notifications
    smtp_host: Optional[str] = Field(default=None, env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, env="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, env="SMTP_USE_TLS")
    email_from: str = Field(default="noreply@compliance-kit.eu", env="EMAIL_FROM")
    admin_email: Optional[str] = Field(default=None, env="ADMIN_EMAIL")
    
    # Audit and Retention
    audit_retention_days: int = Field(default=2555, env="AUDIT_RETENTION_DAYS")  # 7 years
    cleanup_temp_files: bool = Field(default=True, env="CLEANUP_TEMP_FILES")
    backup_enabled: bool = Field(default=False, env="BACKUP_ENABLED")
    backup_s3_bucket: Optional[str] = Field(default=None, env="BACKUP_S3_BUCKET")
    
    # Development Settings
    mock_ckan: bool = Field(default=False, env="MOCK_CKAN")
    mock_ftp: bool = Field(default=False, env="MOCK_FTP")
    generate_test_data: bool = Field(default=False, env="GENERATE_TEST_DATA")

    @validator("allowed_file_extensions", pre=True)
    def parse_extensions(cls, v):
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v

    @validator("pii_redaction_fields", pre=True)
    def parse_pii_fields(cls, v):
        if isinstance(v, str):
            return [field.strip() for field in v.split(",")]
        return v

    @validator("ocr_languages", pre=True)
    def parse_ocr_languages(cls, v):
        if isinstance(v, str):
            return [lang.strip() for lang in v.split(",")]
        return v

    @validator("data_dir", "upload_dir", "output_dir", pre=True)
    def parse_path(cls, v):
        if isinstance(v, str):
            return Path(v)
        return v

    @validator("max_file_size")
    def parse_file_size(cls, v):
        """Convert file size string to bytes."""
        if isinstance(v, str):
            v = v.upper()
            if v.endswith("MB"):
                return int(float(v[:-2]) * 1024 * 1024)
            elif v.endswith("GB"):
                return int(float(v[:-2]) * 1024 * 1024 * 1024)
            elif v.endswith("KB"):
                return int(float(v[:-2]) * 1024)
            elif v.isdigit():
                return int(v)
        return v

    def model_post_init(self, __context) -> None:
        """Ensure directories exist."""
        for dir_path in [self.data_dir, self.upload_dir, self.output_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure logs directory exists if log_file is set
        if self.log_file:
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


# Global settings instance
settings = Settings()
