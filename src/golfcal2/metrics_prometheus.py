"""Prometheus metrics formatting for golfcal2."""

from typing import Dict, Any, List, Iterator
from datetime import datetime

class PrometheusFormatter:
    """Format metrics in Prometheus text format."""
    
    @staticmethod
    def format_help(name: str, help_text: str) -> str:
        """Format HELP line.
        
        Args:
            name: Metric name
            help_text: Help text
            
        Returns:
            Formatted help line
        """
        return f"# HELP {name} {help_text}"
    
    @staticmethod
    def format_type(name: str, type_name: str) -> str:
        """Format TYPE line.
        
        Args:
            name: Metric name
            type_name: Metric type
            
        Returns:
            Formatted type line
        """
        return f"# TYPE {name} {type_name}"
    
    @staticmethod
    def format_metric(name: str, value: float, labels: Dict[str, str] = None) -> str:
        """Format metric line.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels
            
        Returns:
            Formatted metric line
        """
        if labels:
            label_str = ','.join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}} {value}"
        return f"{name} {value}"
    
    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitize metric name to follow Prometheus naming conventions.
        
        Args:
            name: Original metric name
            
        Returns:
            Sanitized name
        """
        # Replace invalid characters with underscores
        return ''.join(c if c.isalnum() else '_' for c in name)
    
    @classmethod
    def format_counter(cls, name: str, value: int, help_text: str = "") -> List[str]:
        """Format a counter metric.
        
        Args:
            name: Metric name
            value: Counter value
            help_text: Optional help text
            
        Returns:
            List of formatted lines
        """
        name = cls.sanitize_name(name)
        lines = []
        if help_text:
            lines.append(cls.format_help(name, help_text))
        lines.append(cls.format_type(name, "counter"))
        lines.append(cls.format_metric(name, float(value)))
        return lines
    
    @classmethod
    def format_gauge(cls, name: str, value: float, help_text: str = "") -> List[str]:
        """Format a gauge metric.
        
        Args:
            name: Metric name
            value: Gauge value
            help_text: Optional help text
            
        Returns:
            List of formatted lines
        """
        name = cls.sanitize_name(name)
        lines = []
        if help_text:
            lines.append(cls.format_help(name, help_text))
        lines.append(cls.format_type(name, "gauge"))
        lines.append(cls.format_metric(name, float(value)))
        return lines
    
    @classmethod
    def format_histogram(cls, name: str, stats: Dict[str, float], help_text: str = "") -> List[str]:
        """Format histogram metrics from timer stats.
        
        Args:
            name: Base metric name
            stats: Timer statistics
            help_text: Optional help text
            
        Returns:
            List of formatted lines
        """
        name = cls.sanitize_name(name)
        lines = []
        
        # Add help and type
        if help_text:
            lines.append(cls.format_help(f"{name}_seconds", help_text))
        lines.append(cls.format_type(f"{name}_seconds", "histogram"))
        
        # Add count
        lines.append(cls.format_metric(
            f"{name}_seconds_count",
            float(stats["count"])
        ))
        
        # Add sum
        lines.append(cls.format_metric(
            f"{name}_seconds_sum",
            float(stats["total"])
        ))
        
        # Add bucket for max (infinity bucket)
        lines.append(cls.format_metric(
            f"{name}_seconds_bucket",
            float(stats["count"]),
            {"le": "+Inf"}
        ))
        
        return lines

def format_prometheus_metrics(metrics: Dict[str, Any]) -> str:
    """Convert metrics dictionary to Prometheus format.
    
    Args:
        metrics: Metrics dictionary from Metrics.get_metrics()
        
    Returns:
        Metrics in Prometheus text format
    """
    formatter = PrometheusFormatter()
    lines = []
    
    # Add uptime
    lines.extend(formatter.format_gauge(
        "golfcal_uptime_seconds",
        metrics["uptime_seconds"],
        "Service uptime in seconds"
    ))
    
    # Add counters
    for name, value in metrics["counters"].items():
        lines.extend(formatter.format_counter(
            f"golfcal_{name}_total",
            value,
            f"Total number of {name.replace('_', ' ')}"
        ))
    
    # Add gauges
    for name, value in metrics["gauges"].items():
        lines.extend(formatter.format_gauge(
            f"golfcal_{name}",
            value,
            f"Current value of {name.replace('_', ' ')}"
        ))
    
    # Add timers as histograms
    for name, stats in metrics["timers"].items():
        lines.extend(formatter.format_histogram(
            f"golfcal_{name}",
            stats,
            f"Histogram of {name.replace('_', ' ')} durations"
        ))
    
    return '\n'.join(lines) + '\n' 