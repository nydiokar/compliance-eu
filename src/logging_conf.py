import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import structlog
    from structlog.typing import FilteringBoundLogger
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    # Fallback type for when structlog is not available
    FilteringBoundLogger = logging.Logger

from src.settings import settings


def setup_logging() -> FilteringBoundLogger:
    """Configure structured logging for the application."""
    
    # Ensure log directory exists
    if settings.log_file:
        Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)
    
    if STRUCTLOG_AVAILABLE:
        # Configure structlog processors
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.CallsiteParameterAdder(
                parameters=[structlog.processors.CallsiteParameter.FUNC_NAME]
            ),
        ]
        
        if settings.log_format == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.extend([
                structlog.dev.ConsoleRenderer(colors=True),
            ])
        
        # Configure structlog
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, settings.log_level.upper())
            ),
            logger_factory=structlog.stdlib.LoggerFactory(),
            context_class=dict,
            cache_logger_on_first_use=True,
        )
    
    # Configure standard library logging
    handlers = ["console"]
    if settings.log_file:
        handlers.append("file")
    
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
            },
            "console": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(colors=True),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json" if settings.log_format == "json" else "console",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "": {
                "handlers": handlers,
                "level": settings.log_level.upper(),
                "propagate": False,
            },
            "uvicorn": {
                "handlers": handlers,
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": handlers,
                "level": "INFO",
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "handlers": handlers,
                "level": "WARNING" if not settings.debug else "INFO",
                "propagate": False,
            },
            "apscheduler": {
                "handlers": handlers,
                "level": "INFO",
                "propagate": False,
            },
        },
    }
    
    # Add file handler if configured
    if settings.log_file:
        logging_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(settings.log_file),
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "formatter": "json",
        }
    
    logging.config.dictConfig(logging_config)
    
    # Return a logger for the application
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger("compliance_kit")
    else:
        return logging.getLogger("compliance_kit")


def get_logger(name: str = "compliance_kit") -> FilteringBoundLogger:
    """Get a logger instance with the given name."""
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    else:
        return logging.getLogger(name)


def log_context(**kwargs: Any) -> None:
    """Add context variables to all subsequent log messages in this context."""
    if STRUCTLOG_AVAILABLE:
        for key, value in kwargs.items():
            structlog.contextvars.bind_contextvars(**{key: value})


def clear_log_context() -> None:
    """Clear all context variables."""
    if STRUCTLOG_AVAILABLE:
        structlog.contextvars.clear_contextvars()


class RequestLoggingMiddleware:
    """Middleware to add request context to logs."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Add request context
            request_id = scope.get("request_id", "unknown")
            method = scope["method"]
            path = scope["path"]
            
            log_context(
                request_id=request_id,
                method=method,
                path=path,
            )
            
            try:
                await self.app(scope, receive, send)
            finally:
                clear_log_context()
        else:
            await self.app(scope, receive, send)


# Audit logging utilities
def log_audit_event(
    event_type: str,
    resource_type: str,
    resource_id: str,
    user_id: str = "system",
    details: Dict[str, Any] = None,
    logger: FilteringBoundLogger = None,
) -> None:
    """Log an audit event with standardized format."""
    if logger is None:
        logger = get_logger("audit")
    
    logger.info(
        "audit_event",
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        details=details or {},
    )


def log_data_processing_event(
    dataset_id: str,
    run_id: str,
    stage: str,
    status: str,
    input_hash: str = None,
    output_hash: str = None,
    error_message: str = None,
    metrics: Dict[str, Any] = None,
    logger: FilteringBoundLogger = None,
) -> None:
    """Log a data processing event."""
    if logger is None:
        logger = get_logger("processing")
    
    log_data = {
        "dataset_id": dataset_id,
        "run_id": run_id,
        "stage": stage,
        "status": status,
    }
    
    if input_hash:
        log_data["input_hash"] = input_hash
    if output_hash:
        log_data["output_hash"] = output_hash
    if error_message:
        log_data["error"] = error_message
    if metrics:
        log_data["metrics"] = metrics
    
    log_level = "error" if status == "failed" else "info"
    getattr(logger, log_level)("data_processing_event", **log_data)


def log_publish_event(
    dataset_id: str,
    run_id: str,
    target: str,
    status: str,
    external_id: str = None,
    error_message: str = None,
    logger: FilteringBoundLogger = None,
) -> None:
    """Log a publishing event."""
    if logger is None:
        logger = get_logger("publish")
    
    log_data = {
        "dataset_id": dataset_id,
        "run_id": run_id,
        "target": target,
        "status": status,
    }
    
    if external_id:
        log_data["external_id"] = external_id
    if error_message:
        log_data["error"] = error_message
    
    log_level = "error" if status == "failed" else "info"
    getattr(logger, log_level)("publish_event", **log_data)