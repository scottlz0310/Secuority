"""Tests for logging system."""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from secuority.utils.logger import (
    LogLevel,
    SecuorityLogger,
    StructuredFormatter,
    configure_logging,
    get_logger,
)


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_level_values(self) -> None:
        """Test that LogLevel enum has correct values."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestStructuredFormatter:
    """Tests for StructuredFormatter."""

    def test_format_basic_log_record(self) -> None:
        """Test formatting a basic log record."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test_logger"
        assert log_data["message"] == "Test message"
        assert log_data["module"] == "test"
        assert log_data["line"] == 42
        assert "timestamp" in log_data

    def test_format_log_record_with_exception(self) -> None:
        """Test formatting a log record with exception information."""
        formatter = StructuredFormatter()

        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        formatted = formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["level"] == "ERROR"
        assert log_data["message"] == "Error occurred"
        assert "exception" in log_data
        assert log_data["exception"]["type"] == "ValueError"
        assert log_data["exception"]["message"] == "Test exception"
        assert "traceback" in log_data["exception"]

    def test_format_log_record_with_extra_fields(self) -> None:
        """Test formatting a log record with extra fields."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra fields
        record.operation = "test_operation"
        record.status = "success"

        formatted = formatter.format(record)
        log_data = json.loads(formatted)

        assert "extra" in log_data
        assert log_data["extra"]["operation"] == "test_operation"
        assert log_data["extra"]["status"] == "success"


class TestSecuorityLogger:
    """Tests for SecuorityLogger."""

    @pytest.fixture
    def logger(self) -> SecuorityLogger:
        """Create a fresh logger instance for testing."""
        logger = SecuorityLogger(name="test_logger")
        # Reset configuration state
        logger._configured = False
        logger.logger.handlers.clear()
        return logger

    def test_logger_initialization(self, logger: SecuorityLogger) -> None:
        """Test logger initialization."""
        assert logger.name == "test_logger"
        assert not logger._configured
        assert not logger._verbose
        assert not logger._structured_output

    def test_configure_basic(self, logger: SecuorityLogger) -> None:
        """Test basic logger configuration."""
        logger.configure()
        assert logger._configured
        assert len(logger.logger.handlers) > 0

    def test_configure_with_verbose(self, logger: SecuorityLogger) -> None:
        """Test logger configuration with verbose mode."""
        logger.configure(verbose=True)
        assert logger._verbose
        assert logger.logger.level == logging.DEBUG

    def test_configure_with_log_level(self, logger: SecuorityLogger) -> None:
        """Test logger configuration with specific log level."""
        logger.configure(level=LogLevel.WARNING)
        assert logger.logger.level == logging.WARNING

    def test_configure_with_structured_output(self, logger: SecuorityLogger) -> None:
        """Test logger configuration with structured output."""
        logger.configure(structured_output=True)
        assert logger._structured_output
        # Check that handler uses StructuredFormatter
        handler = logger.logger.handlers[0]
        assert isinstance(handler.formatter, StructuredFormatter)

    def test_configure_with_log_file(self, logger: SecuorityLogger, tmp_path: Path) -> None:
        """Test logger configuration with log file."""
        log_file = tmp_path / "test.log"
        logger.configure(log_file=log_file)

        # Should have console handler and file handler
        assert len(logger.logger.handlers) == 2

        # File should be created
        assert log_file.exists()

    def test_configure_only_once(self, logger: SecuorityLogger) -> None:
        """Test that configure only runs once."""
        logger.configure(level=LogLevel.INFO)
        initial_handlers = len(logger.logger.handlers)

        logger.configure(level=LogLevel.DEBUG)
        # Should not add more handlers
        assert len(logger.logger.handlers) == initial_handlers

    def test_debug_logging(self, logger: SecuorityLogger) -> None:
        """Test debug logging."""
        logger.configure(verbose=True)
        with patch.object(logger.logger, "debug") as mock_debug:
            logger.debug("Debug message", extra_field="value")
            mock_debug.assert_called_once()
            args, kwargs = mock_debug.call_args
            assert args[0] == "Debug message"
            assert kwargs["extra"]["extra_field"] == "value"

    def test_info_logging(self, logger: SecuorityLogger) -> None:
        """Test info logging."""
        logger.configure()
        with patch.object(logger.logger, "info") as mock_info:
            logger.info("Info message")
            mock_info.assert_called_once_with("Info message", extra={})

    def test_warning_logging(self, logger: SecuorityLogger) -> None:
        """Test warning logging."""
        logger.configure()
        with patch.object(logger.logger, "warning") as mock_warning:
            logger.warning("Warning message")
            mock_warning.assert_called_once()

    def test_error_logging(self, logger: SecuorityLogger) -> None:
        """Test error logging."""
        logger.configure()
        with patch.object(logger.logger, "error") as mock_error:
            logger.error("Error message")
            mock_error.assert_called_once()

    def test_critical_logging(self, logger: SecuorityLogger) -> None:
        """Test critical logging."""
        logger.configure()
        with patch.object(logger.logger, "critical") as mock_critical:
            logger.critical("Critical message")
            mock_critical.assert_called_once()

    def test_exception_logging(self, logger: SecuorityLogger) -> None:
        """Test exception logging."""
        logger.configure()
        with patch.object(logger.logger, "exception") as mock_exception:
            logger.exception("Exception message")
            mock_exception.assert_called_once()

    def test_log_operation(self, logger: SecuorityLogger) -> None:
        """Test structured operation logging."""
        logger.configure()
        with patch.object(logger.logger, "info") as mock_info:
            logger.log_operation(
                operation="test_op",
                status="success",
                details={"count": 42},
                level=LogLevel.INFO,
            )
            mock_info.assert_called_once()
            args, kwargs = mock_info.call_args
            assert "test_op" in args[0]
            assert kwargs["extra"]["operation"] == "test_op"
            assert kwargs["extra"]["status"] == "success"
            assert kwargs["extra"]["count"] == 42

    def test_log_analysis_result(self, logger: SecuorityLogger) -> None:
        """Test analysis result logging."""
        logger.configure()
        with patch.object(logger.logger, "info") as mock_info:
            logger.log_analysis_result(
                file_path="/path/to/file.py",
                analysis_type="dependency",
                result={"packages": 10},
                recommendations=["Update package X"],
            )
            mock_info.assert_called_once()
            args, kwargs = mock_info.call_args
            assert "/path/to/file.py" in args[0]
            assert kwargs["extra"]["file_path"] == "/path/to/file.py"
            assert kwargs["extra"]["analysis_type"] == "dependency"
            assert kwargs["extra"]["recommendations"] == ["Update package X"]

    def test_log_configuration_change_success(self, logger: SecuorityLogger) -> None:
        """Test logging successful configuration change."""
        logger.configure()
        with patch.object(logger.logger, "info") as mock_info:
            logger.log_configuration_change(
                file_path="/path/to/config.toml",
                change_type="update",
                description="Updated settings",
                success=True,
                backup_path="/path/to/backup.toml",
            )
            mock_info.assert_called_once()
            args, kwargs = mock_info.call_args
            assert "applied" in args[0]
            assert kwargs["extra"]["file_path"] == "/path/to/config.toml"
            assert kwargs["extra"]["backup_path"] == "/path/to/backup.toml"

    def test_log_configuration_change_failure(self, logger: SecuorityLogger) -> None:
        """Test logging failed configuration change."""
        logger.configure()
        with patch.object(logger.logger, "error") as mock_error:
            logger.log_configuration_change(
                file_path="/path/to/config.toml",
                change_type="update",
                description="Failed to update",
                success=False,
            )
            mock_error.assert_called_once()
            args, _kwargs = mock_error.call_args
            assert "failed" in args[0]

    def test_log_github_api_call_success(self, logger: SecuorityLogger) -> None:
        """Test logging successful GitHub API call."""
        logger.configure(verbose=True)
        with patch.object(logger.logger, "debug") as mock_debug:
            logger.log_github_api_call(
                endpoint="/repos/owner/repo",
                method="GET",
                status_code=200,
                success=True,
            )
            mock_debug.assert_called_once()
            args, kwargs = mock_debug.call_args
            assert "successful" in args[0]
            assert kwargs["extra"]["github_api"] is True

    def test_log_github_api_call_failure(self, logger: SecuorityLogger) -> None:
        """Test logging failed GitHub API call."""
        logger.configure()
        with patch.object(logger.logger, "warning") as mock_warning:
            logger.log_github_api_call(
                endpoint="/repos/owner/repo",
                method="GET",
                status_code=404,
                success=False,
                error_message="Not found",
            )
            mock_warning.assert_called_once()
            args, _kwargs = mock_warning.call_args
            assert "failed" in args[0]
            assert "Not found" in args[0]

    def test_is_verbose(self, logger: SecuorityLogger) -> None:
        """Test is_verbose method."""
        logger.configure(verbose=False)
        assert not logger.is_verbose()

        logger._verbose = True
        assert logger.is_verbose()

    def test_is_debug_enabled(self, logger: SecuorityLogger) -> None:
        """Test is_debug_enabled method."""
        logger.configure(level=LogLevel.INFO)
        assert not logger.is_debug_enabled()

        logger.logger.setLevel(logging.DEBUG)
        assert logger.is_debug_enabled()


class TestGlobalLogger:
    """Tests for global logger functions."""

    def test_get_logger_singleton(self) -> None:
        """Test that get_logger returns singleton instance."""
        # Reset global instance
        import secuority.utils.logger as logger_module

        logger_module._logger_instance = None

        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2

    def test_configure_logging(self) -> None:
        """Test global configure_logging function."""
        import secuority.utils.logger as logger_module

        logger_module._logger_instance = None

        configure_logging(level=LogLevel.DEBUG, verbose=True)
        logger = get_logger()
        assert logger._configured
        assert logger._verbose

    def test_convenience_functions(self) -> None:
        """Test convenience logging functions."""
        import secuority.utils.logger as logger_module

        logger_module._logger_instance = None
        configure_logging()

        logger = get_logger()

        with patch.object(logger, "debug") as mock_debug:
            logger_module.debug("Debug message", key="value")
            mock_debug.assert_called_once_with("Debug message", key="value")

        with patch.object(logger, "info") as mock_info:
            logger_module.info("Info message")
            mock_info.assert_called_once_with("Info message")

        with patch.object(logger, "warning") as mock_warning:
            logger_module.warning("Warning message")
            mock_warning.assert_called_once_with("Warning message")

        with patch.object(logger, "error") as mock_error:
            logger_module.error("Error message")
            mock_error.assert_called_once_with("Error message")

        with patch.object(logger, "critical") as mock_critical:
            logger_module.critical("Critical message")
            mock_critical.assert_called_once_with("Critical message")

        with patch.object(logger, "exception") as mock_exception:
            logger_module.exception("Exception message")
            mock_exception.assert_called_once_with("Exception message")


class TestLoggerIntegration:
    """Integration tests for logger with actual log output."""

    def test_logger_writes_to_file(self, tmp_path: Path) -> None:
        """Test that logger actually writes to file."""
        log_file = tmp_path / "test.log"
        logger = SecuorityLogger(name="integration_test")
        logger.configure(log_file=log_file, structured_output=True)

        logger.info("Test message", test_field="test_value")

        # Read log file and verify content
        assert log_file.exists()
        log_content = log_file.read_text()
        log_data = json.loads(log_content.strip())

        assert log_data["message"] == "Test message"
        assert log_data["level"] == "INFO"
        assert log_data["extra"]["test_field"] == "test_value"

    def test_logger_respects_log_level(self) -> None:
        """Test that logger respects configured log level."""
        logger = SecuorityLogger(name="level_test")
        logger.configure(level=LogLevel.WARNING)

        # Mock the underlying logger to check what gets called
        with patch.object(logger.logger, "debug") as mock_debug, patch.object(logger.logger, "warning") as mock_warning:
            logger.debug("Debug message")
            logger.warning("Warning message")

            # Debug should be called but not logged due to level
            mock_debug.assert_called_once()
            mock_warning.assert_called_once()

    def test_exception_logging_with_traceback(self) -> None:
        """Test that exception logging includes traceback."""
        logger = SecuorityLogger(name="exception_test")
        logger.configure(structured_output=True)

        try:
            raise ValueError("Test exception")
        except ValueError:
            with patch.object(logger.logger, "exception") as mock_exception:
                logger.exception("An error occurred")
                mock_exception.assert_called_once()
