"""Logging configuration loader and types."""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
from pathlib import Path
import yaml

@dataclass
class FileLogConfig:
    """File logging configuration."""
    enabled: bool = True
    path: str = "logs/app.log"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "json"
    include_timestamp: bool = True

@dataclass
class ConsoleLogConfig:
    """Console logging configuration."""
    enabled: bool = True
    format: str = "text"
    include_timestamp: bool = True
    color: bool = True

@dataclass
class SamplingConfig:
    """Log sampling configuration."""
    debug_rate: float = 0.1
    info_rate: float = 1.0
    warning_rate: float = 1.0
    error_rate: float = 1.0
    critical_rate: float = 1.0

@dataclass
class PerformanceConfig:
    """Performance logging configuration."""
    enabled: bool = True
    slow_threshold_ms: int = 1000
    include_args: bool = False
    include_stack_trace: bool = True

@dataclass
class CorrelationConfig:
    """Correlation ID configuration."""
    enabled: bool = True
    include_in_console: bool = True
    header_name: str = "X-Correlation-ID"

@dataclass
class SensitiveDataConfig:
    """Sensitive data masking configuration."""
    enabled: bool = True
    global_fields: List[str] = None
    mask_pattern: str = "***MASKED***"
    partial_mask: bool = False

    def __post_init__(self):
        if self.global_fields is None:
            self.global_fields = [
                'password', 'token', 'api_key', 'secret',
                'credit_card', 'ssn', 'auth', 'cookie'
            ]

@dataclass
class ServiceLogConfig:
    """Service-specific logging configuration."""
    level: str = "INFO"
    sampling: Optional[SamplingConfig] = None
    sensitive_fields: List[str] = None
    performance_logging: bool = True
    file: Optional[FileLogConfig] = None

    def __post_init__(self):
        if self.sampling is None:
            self.sampling = SamplingConfig()
        if self.sensitive_fields is None:
            self.sensitive_fields = []
        if isinstance(self.sampling, dict):
            self.sampling = SamplingConfig(**self.sampling)
        if isinstance(self.file, dict):
            self.file = FileLogConfig(**self.file)

@dataclass
class LoggingConfig:
    """Complete logging configuration."""
    default_level: str = "WARNING"
    dev_level: str = "DEBUG"
    verbose_level: str = "INFO"
    file: FileLogConfig = None
    console: ConsoleLogConfig = None
    sampling: SamplingConfig = None
    services: Dict[str, ServiceLogConfig] = None
    libraries: Dict[str, str] = None
    performance: PerformanceConfig = None
    correlation: CorrelationConfig = None
    sensitive_data: SensitiveDataConfig = None

    def __post_init__(self):
        if self.file is None:
            self.file = FileLogConfig()
        if self.console is None:
            self.console = ConsoleLogConfig()
        if self.sampling is None:
            self.sampling = SamplingConfig()
        if self.services is None:
            self.services = {}
        if self.libraries is None:
            self.libraries = {}
        if self.performance is None:
            self.performance = PerformanceConfig()
        if self.correlation is None:
            self.correlation = CorrelationConfig()
        if self.sensitive_data is None:
            self.sensitive_data = SensitiveDataConfig()

        # Convert dictionaries to proper objects
        if isinstance(self.file, dict):
            self.file = FileLogConfig(**self.file)
        if isinstance(self.console, dict):
            self.console = ConsoleLogConfig(**self.console)
        if isinstance(self.sampling, dict):
            self.sampling = SamplingConfig(**self.sampling)
        if isinstance(self.performance, dict):
            self.performance = PerformanceConfig(**self.performance)
        if isinstance(self.correlation, dict):
            self.correlation = CorrelationConfig(**self.correlation)
        if isinstance(self.sensitive_data, dict):
            self.sensitive_data = SensitiveDataConfig(**self.sensitive_data)

        # Convert service configurations
        converted_services = {}
        for service_name, service_config in self.services.items():
            if isinstance(service_config, dict):
                converted_services[service_name] = ServiceLogConfig(**service_config)
            else:
                converted_services[service_name] = service_config
        self.services = converted_services

def load_logging_config(config_path: Optional[Union[str, Path]] = None) -> LoggingConfig:
    """Load logging configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Logging configuration object
    """
    if config_path is None:
        config_dir = os.getenv("GOLFCAL_CONFIG_DIR", os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(config_dir, "logging_config.yaml")

    # Load configuration from file if it exists
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        return LoggingConfig(**config_dict)

    # Return default configuration if file doesn't exist
    return LoggingConfig() 