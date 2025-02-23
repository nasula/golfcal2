"""Logging configuration types and loading utilities."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

import yaml
import os

@dataclass
class FileConfig:
    """File logging configuration."""
    enabled: bool
    path: str
    max_size_mb: int
    backup_count: int
    format: str
    include_timestamp: bool

@dataclass
class ConsoleConfig:
    """Console logging configuration."""
    enabled: bool
    format: str
    include_timestamp: bool
    color: bool

@dataclass
class SamplingConfig:
    """Sampling configuration."""
    debug_rate: float
    info_rate: float
    warning_rate: float
    error_rate: float
    critical_rate: float

@dataclass
class ServiceFileConfig:
    """Service-specific file logging configuration."""
    enabled: bool
    path: str
    max_size_mb: int
    backup_count: int
    include_timestamp: bool = True

@dataclass
class ServiceConfig:
    """Service-specific logging configuration."""
    level: str
    sampling: Optional[SamplingConfig] = None
    sensitive_fields: Optional[List[str]] = None
    performance_logging: bool = False
    file: Optional[ServiceFileConfig] = None

@dataclass
class PerformanceConfig:
    """Performance logging configuration."""
    enabled: bool
    slow_threshold_ms: int
    include_args: bool
    include_stack_trace: bool

@dataclass
class CorrelationConfig:
    """Correlation ID configuration."""
    enabled: bool
    include_in_console: bool
    header_name: str

@dataclass
class SensitiveDataConfig:
    """Sensitive data masking configuration."""
    enabled: bool
    global_fields: List[str]
    mask_pattern: str
    partial_mask: bool

@dataclass
class ErrorAggregationConfig:
    """Error aggregation configuration."""
    enabled: bool
    report_interval: int
    error_threshold: int
    time_threshold: int
    categorize_by: List[str]

@dataclass
class JournaldConfig:
    """Journald logging configuration."""
    enabled: bool
    identifier: str
    format: str
    level: str

@dataclass
class LoggingConfig:
    """Complete logging configuration."""
    default_level: str
    dev_level: str
    verbose_level: str
    file: FileConfig
    console: ConsoleConfig
    sampling: SamplingConfig
    services: Dict[str, ServiceConfig]
    libraries: Dict[str, str]
    performance: PerformanceConfig
    correlation: CorrelationConfig
    sensitive_data: SensitiveDataConfig
    error_aggregation: ErrorAggregationConfig
    journald: JournaldConfig

def load_logging_config(config_path=None):
    """Load logging configuration from YAML file."""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), 'logging_config.yaml')

    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)

    # Convert journald config to JournaldConfig object
    journald_config = config_dict.get('journald', {})
    journald = JournaldConfig(
        enabled=journald_config.get('enabled', True),
        identifier=journald_config.get('identifier', 'golfcal2'),
        format=journald_config.get('format', '%(name)s: %(levelname)s %(message)s'),
        level=journald_config.get('level', 'DEBUG')
    )

    # Convert services config to ServiceConfig objects
    services = {}
    if 'services' in config_dict:
        for service_name, service_config in config_dict['services'].items():
            services[service_name] = ServiceConfig(**service_config)

    # Create and return the LoggingConfig object
    return LoggingConfig(
        default_level=config_dict.get('default_level', 'WARNING'),
        dev_level=config_dict.get('dev_level', 'INFO'),
        verbose_level=config_dict.get('verbose_level', 'DEBUG'),
        file=FileConfig(**config_dict.get('file', {})) if 'file' in config_dict else None,
        console=ConsoleConfig(**config_dict.get('console', {})) if 'console' in config_dict else None,
        sampling=SamplingConfig(**config_dict.get('sampling', {})) if 'sampling' in config_dict else None,
        services=services,
        performance=PerformanceConfig(**config_dict.get('performance', {})) if 'performance' in config_dict else None,
        correlation=CorrelationConfig(**config_dict.get('correlation', {})) if 'correlation' in config_dict else None,
        sensitive_data=SensitiveDataConfig(**config_dict.get('sensitive_data', {})) if 'sensitive_data' in config_dict else None,
        error_aggregation=ErrorAggregationConfig(**config_dict.get('error_aggregation', {})) if 'error_aggregation' in config_dict else None,
        journald=journald
    ) 