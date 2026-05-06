import logging
import json
import traceback
from datetime import datetime, timezone
import sys
from typing import Any, Dict, Optional

# Fields containing sensitive information that must be redacted
SENSITIVE_KEYS = {
    "password", "secret", "token", "key", "authorization", 
    "credit_card", "cc_number", "card_number", "cvv", "api_key"
}
REDACTION_TEXT = "[REDACTED]"

def redact_sensitive_data(data: Any) -> Any:
    """Recursively redacts sensitive keys in dictionaries."""
    if isinstance(data, dict):
        redacted_dict = {}
        for k, v in data.items():
            if any(sensitive_key in str(k).lower() for sensitive_key in SENSITIVE_KEYS):
                redacted_dict[k] = REDACTION_TEXT
            elif isinstance(v, (dict, list)):
                redacted_dict[k] = redact_sensitive_data(v)
            else:
                redacted_dict[k] = v
        return redacted_dict
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data

class JSONFormatter(logging.Formatter):
    """Custom logging formatter to enforce strict JSON output."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage()
        }
        
        # Add optional standard fields if present
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
            
        # Add additional context if present
        if hasattr(record, "context") and isinstance(record.context, dict):
            context_data = record.context
        else:
            context_data = {}
            
        # Capture stack trace if exception is attached
        if record.exc_info:
            context_data["exception"] = "".join(traceback.format_exception(*record.exc_info))
            
        if context_data:
            log_data["context"] = redact_sensitive_data(context_data)
        else:
            log_data["context"] = {}
            
        try:
            return json.dumps(log_data)
        except (TypeError, ValueError):
            # Fallback to standard logging if JSON serialization fails
            fallback_time = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
            return f"[{fallback_time}] {record.levelname} {record.module}: {record.getMessage()} (JSON serialization failed)"

def get_logger(name: str) -> logging.Logger:
    """Returns a configured JSON logger instance."""
    logger = logging.getLogger(name)
    
    # Only configure if not already configured (prevents duplicate handlers)
    if not logger.handlers:
        logger.setLevel(logging.INFO) # Default to INFO, can be overridden by config later
        
        # Write to stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
        # Do not propagate up to root logger to avoid standard formatting
        logger.propagate = False
        
        # Suppress noisy standard libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        
    return logger
