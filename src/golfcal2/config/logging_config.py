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
            # Convert file config if present
            file_config = None
            if 'file' in service_config:
                file_config = ServiceFileConfig(
                    enabled=service_config['file'].get('enabled', False),
                    path=service_config['file'].get('path', f'logs/{service_name}.log'),
                    max_size_mb=service_config['file'].get('max_size_mb', 10),
                    backup_count=service_config['file'].get('backup_count', 5),
                    include_timestamp=service_config['file'].get('include_timestamp', True)
                )

            # Convert sampling config if present
            sampling_config = None
            if 'sampling' in service_config:
                sampling_config = SamplingConfig(
                    debug_rate=service_config['sampling'].get('debug_rate', 1.0),
                    info_rate=service_config['sampling'].get('info_rate', 1.0),
                    warning_rate=service_config['sampling'].get('warning_rate', 1.0),
                    error_rate=service_config['sampling'].get('error_rate', 1.0),
                    critical_rate=service_config['sampling'].get('critical_rate', 1.0)
                )

            # Create ServiceConfig object
            services[service_name] = ServiceConfig(
                level=service_config.get('level', 'INFO'),
                sampling=sampling_config,
                sensitive_fields=service_config.get('sensitive_fields', []),
                performance_logging=service_config.get('performance_logging', False),
                file=file_config
            )

    # Get libraries config with defaults
    libraries = config_dict.get('libraries', {
        'urllib3': 'WARNING',
        'requests': 'WARNING',
        'icalendar': 'WARNING',
        'yaml': 'WARNING',
        'json': 'WARNING'
    })

    # Create and return the LoggingConfig object
    return LoggingConfig(
        default_level=config_dict.get('default_level', 'WARNING'),
        dev_level=config_dict.get('dev_level', 'INFO'),
        verbose_level=config_dict.get('verbose_level', 'DEBUG'),
        file=FileConfig(**config_dict.get('file', {
            'enabled': False,
            'path': 'logs/golfcal.log',
            'max_size_mb': 50,
            'backup_count': 7,
            'format': 'json',
            'include_timestamp': True
        })),
        console=ConsoleConfig(**config_dict.get('console', {
            'enabled': True,
            'format': 'text',
            'include_timestamp': True,
            'color': True
        })),
        sampling=SamplingConfig(**config_dict.get('sampling', {
            'debug_rate': 1.0,
            'info_rate': 1.0,
            'warning_rate': 1.0,
            'error_rate': 1.0,
            'critical_rate': 1.0
        })),
        services=services,
        libraries=libraries,
        performance=PerformanceConfig(**config_dict.get('performance', {
            'enabled': True,
            'slow_threshold_ms': 2000,
            'include_args': False,
            'include_stack_trace': True
        })),
        correlation=CorrelationConfig(**config_dict.get('correlation', {
            'enabled': True,
            'include_in_console': True,
            'header_name': 'X-GolfCal-Correlation-ID'
        })),
        sensitive_data=SensitiveDataConfig(**config_dict.get('sensitive_data', {
            'enabled': True,
            'global_fields': [],
            'mask_pattern': '***MASKED***',
            'partial_mask': False
        })),
        error_aggregation=ErrorAggregationConfig(**config_dict.get('error_aggregation', {
            'enabled': True,
            'report_interval': 3600,
            'error_threshold': 5,
            'time_threshold': 300,
            'categorize_by': ['service', 'message']
        })),
        journald=journald
    ) 