"""Logging configuration types and loading utilities."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

import yaml

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

def load_logging_config() -> LoggingConfig:
    """Load logging configuration from YAML file.
    
    Returns:
        Loaded logging configuration
    """
    config_path = Path(__file__).parent / 'logging_config.yaml'
    with open(config_path) as f:
        config_dict = yaml.safe_load(f)
    
    # Convert nested dictionaries to appropriate config objects
    if 'file' in config_dict:
        config_dict['file'] = FileConfig(**config_dict['file'])
    if 'console' in config_dict:
        config_dict['console'] = ConsoleConfig(**config_dict['console'])
    if 'sampling' in config_dict:
        config_dict['sampling'] = SamplingConfig(**config_dict['sampling'])
    if 'performance' in config_dict:
        config_dict['performance'] = PerformanceConfig(**config_dict['performance'])
    if 'correlation' in config_dict:
        config_dict['correlation'] = CorrelationConfig(**config_dict['correlation'])
    if 'sensitive_data' in config_dict:
        config_dict['sensitive_data'] = SensitiveDataConfig(**config_dict['sensitive_data'])
    if 'error_aggregation' in config_dict:
        config_dict['error_aggregation'] = ErrorAggregationConfig(**config_dict['error_aggregation'])
    
    # Convert service configurations
    if 'services' in config_dict:
        services = {}
        for name, service_dict in config_dict['services'].items():
            if 'file' in service_dict:
                service_dict['file'] = ServiceFileConfig(**service_dict['file'])
            if 'sampling' in service_dict:
                service_dict['sampling'] = SamplingConfig(**service_dict['sampling'])
            services[name] = ServiceConfig(**service_dict)
        config_dict['services'] = services
    
    return LoggingConfig(**config_dict) 