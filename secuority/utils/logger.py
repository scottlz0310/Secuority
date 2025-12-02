"""Structured logging system for Secuority.

This module provides a centralized logging system with structured output,
configurable log levels, and integration with the CLI verbose flag.
"""

import json
import logging
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception information if present
        if record.exc_info:
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else None
            exc_message = str(record.exc_info[1]) if record.exc_info[1] else None
            exc_traceback = self.formatException(record.exc_info) if record.exc_info else None
            log_entry["exception"] = {
                "type": exc_type,
                "message": exc_message,
                "traceback": exc_traceback,
            }

        # Add extra fields from the log record
        extra_fields = {}
        reserved_fields = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "getMessage",
            "message",
            "taskName",
        }

        for key, value in record.__dict__.items():
            if key not in reserved_fields:
                extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class SecuorityLogger:
    """Centralized logger for Secuority with structured output support."""

    def __init__(self, name: str = "secuority"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.console = Console(stderr=True)
        self._configured = False
        self._verbose = False
        self._structured_output = False

    def configure(
        self,
        level: str | LogLevel = LogLevel.INFO,
        verbose: bool = False,
        structured_output: bool = False,
        log_file: Path | None = None,
    ) -> None:
        """Configure the logging system.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            verbose: Enable verbose logging (sets level to DEBUG)
            structured_output: Enable structured JSON output
            log_file: Optional file path for log output
        """
        if self._configured:
            return

        self._verbose = verbose
        self._structured_output = structured_output

        # Set log level
        if verbose:
            log_level = logging.DEBUG
        elif isinstance(level, LogLevel):
            log_level = getattr(logging, level.value)
        else:
            log_level = getattr(logging, level.upper())

        self.logger.setLevel(log_level)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Configure console handler
        if structured_output:
            # Use structured JSON output
            console_handler: logging.Handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(StructuredFormatter())
        else:
            # Use Rich handler for pretty console output
            console_handler = RichHandler(
                console=self.console,
                show_time=verbose,
                show_path=verbose,
                markup=True,
                rich_tracebacks=True,
            )
            console_handler.setFormatter(
                logging.Formatter(
                    fmt="%(message)s",
                    datefmt="[%X]",
                ),
            )

        console_handler.setLevel(log_level)
        self.logger.addHandler(console_handler)

        # Configure file handler if specified
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(StructuredFormatter())
            file_handler.setLevel(logging.DEBUG)  # Always log everything to file
            self.logger.addHandler(file_handler)

        self._configured = True

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self.logger.error(message, extra=kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self.logger.critical(message, extra=kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self.logger.exception(message, extra=kwargs)

    def log_operation(
        self,
        operation: str,
        status: str,
        details: dict[str, Any] | None = None,
        level: LogLevel = LogLevel.INFO,
    ) -> None:
        """Log a structured operation result.

        Args:
            operation: Name of the operation (e.g., "file_analysis", "template_apply")
            status: Operation status (e.g., "success", "failed", "skipped")
            details: Additional operation details
            level: Log level for this operation
        """
        log_data = {
            "operation": operation,
            "status": status,
        }

        if details:
            log_data.update(details)

        message = f"Operation '{operation}' {status}"
        if details and "message" in details:
            message = details["message"]

        getattr(self, level.value.lower())(message, **log_data)

    def log_analysis_result(
        self,
        file_path: str,
        analysis_type: str,
        result: dict[str, Any],
        recommendations: list[str] | None = None,
    ) -> None:
        """Log analysis results in a structured format.

        Args:
            file_path: Path to the analyzed file
            analysis_type: Type of analysis performed
            result: Analysis results
            recommendations: List of recommendations
        """
        log_data = {
            "file_path": file_path,
            "analysis_type": analysis_type,
            "result": result,
        }

        if recommendations:
            log_data["recommendations"] = recommendations

        message = f"Analysis completed for {file_path}"
        if self._verbose:
            message += f" ({analysis_type})"

        self.info(message, **log_data)

    def log_configuration_change(
        self,
        file_path: str,
        change_type: str,
        description: str,
        success: bool = True,
        backup_path: str | None = None,
    ) -> None:
        """Log configuration changes.

        Args:
            file_path: Path to the configuration file
            change_type: Type of change (create, update, merge)
            description: Description of the change
            success: Whether the change was successful
            backup_path: Path to backup file if created
        """
        log_data = {
            "file_path": file_path,
            "change_type": change_type,
            "description": description,
            "success": success,
        }

        if backup_path:
            log_data["backup_path"] = backup_path

        status = "applied" if success else "failed"
        message = f"Configuration change {status}: {description}"

        if success:
            self.info(message, **log_data)
        else:
            self.error(message, **log_data)

    def log_github_api_call(
        self,
        endpoint: str,
        method: str,
        status_code: int | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Log GitHub API calls.

        Args:
            endpoint: API endpoint called
            method: HTTP method used
            status_code: HTTP status code received
            success: Whether the call was successful
            error_message: Error message if call failed
        """
        log_data = {
            "endpoint": endpoint,
            "method": method,
            "github_api": True,
        }

        if status_code:
            log_data["status_code"] = status_code

        if success:
            message = f"GitHub API call successful: {method} {endpoint}"
            self.debug(message, **log_data)
        else:
            message = f"GitHub API call failed: {method} {endpoint}"
            if error_message:
                message += f" - {error_message}"
                log_data["error_message"] = error_message
            self.warning(message, **log_data)

    def is_verbose(self) -> bool:
        """Check if verbose logging is enabled."""
        return self._verbose

    def is_debug_enabled(self) -> bool:
        """Check if debug logging is enabled."""
        return self.logger.isEnabledFor(logging.DEBUG)


# Global logger instance
_logger_instance: SecuorityLogger | None = None


def get_logger(name: str = "secuority") -> SecuorityLogger:
    """Get the global logger instance.

    Args:
        name: Logger name (default: "secuority")

    Returns:
        SecuorityLogger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SecuorityLogger(name)
    return _logger_instance


def configure_logging(
    level: str | LogLevel = LogLevel.INFO,
    verbose: bool = False,
    structured_output: bool = False,
    log_file: Path | None = None,
) -> None:
    """Configure the global logging system.

    Args:
        level: Logging level
        verbose: Enable verbose logging
        structured_output: Enable structured JSON output
        log_file: Optional file path for log output
    """
    logger = get_logger()
    logger.configure(
        level=level,
        verbose=verbose,
        structured_output=structured_output,
        log_file=log_file,
    )


# Convenience functions for common logging operations
def debug(message: str, **kwargs: Any) -> None:
    """Log debug message using global logger."""
    get_logger().debug(message, **kwargs)


def info(message: str, **kwargs: Any) -> None:
    """Log info message using global logger."""
    get_logger().info(message, **kwargs)


def warning(message: str, **kwargs: Any) -> None:
    """Log warning message using global logger."""
    get_logger().warning(message, **kwargs)


def error(message: str, **kwargs: Any) -> None:
    """Log error message using global logger."""
    get_logger().error(message, **kwargs)


def critical(message: str, **kwargs: Any) -> None:
    """Log critical message using global logger."""
    get_logger().critical(message, **kwargs)


def exception(message: str, **kwargs: Any) -> None:
    """Log exception with traceback using global logger."""
    get_logger().exception(message, **kwargs)
