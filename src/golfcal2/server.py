"""HTTP server for health checks and monitoring."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from golfcal2.health import get_health_status
from golfcal2.metrics import Metrics
from golfcal2.metrics_prometheus import format_prometheus_metrics
from golfcal2.utils.logging_utils import get_logger

logger = get_logger(__name__)

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Handler for health check requests."""
    
    def _send_response(self, status_code: int, data: dict[str, Any], content_type: str = 'application/json') -> None:
        """Send response with appropriate content type.
        
        Args:
            status_code: HTTP status code
            data: Response data
            content_type: Content type header value
        """
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        
        if content_type == 'application/json':
            response = json.dumps(data, indent=2)
        else:
            response = str(data)
            
        self.wfile.write(response.encode('utf-8'))
    
    def do_GET(self) -> None:
        """Handle GET requests."""
        try:
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            if parsed_url.path == '/health':
                # Get health status
                status = get_health_status()
                status_code = 200 if status['status'] == 'healthy' else 503
                self._send_response(status_code, status)
                return
                
            if parsed_url.path == '/metrics':
                # Get metrics
                metrics = Metrics().get_metrics()
                
                # Check format parameter
                format_param = query_params.get('format', ['json'])[0].lower()
                
                if format_param == 'prometheus':
                    # Return Prometheus format
                    prometheus_metrics = format_prometheus_metrics(metrics)
                    self._send_response(200, prometheus_metrics, 'text/plain; version=0.0.4')
                else:
                    # Return JSON format
                    self._send_response(200, metrics)
                return
                
            # Handle unknown paths
            self._send_response(404, {
                'error': 'Not Found',
                'message': f'Path not found: {parsed_url.path}'
            })
            
        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            self._send_response(500, {
                'error': 'Internal Server Error',
                'message': str(e)
            })
    
    def log_message(self, format: str, *args: Any) -> None:
        """Override to use our logger instead of printing to stderr."""
        logger.info(f"{self.address_string()} - {format%args}")

class HealthCheckServer:
    """Server for health checks and metrics."""
    
    def __init__(self, host: str = 'localhost', port: int = 8080):
        """Initialize server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.metrics = Metrics()  # Initialize metrics
        
    def start(self) -> None:
        """Start the server in a background thread."""
        if self.server:
            logger.warning("Server already running")
            return
            
        try:
            self.server = HTTPServer((self.host, self.port), HealthCheckHandler)
            self.thread = threading.Thread(target=self.server.serve_forever)
            self.thread.daemon = True
            self.thread.start()
            
            logger.info(f"Health check server started on http://{self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}", exc_info=True)
            raise
    
    def stop(self) -> None:
        """Stop the server."""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
                if self.thread:
                    self.thread.join()
                logger.info("Health check server stopped")
            except Exception as e:
                logger.error(f"Error stopping server: {e}", exc_info=True)
            finally:
                self.server = None
                self.thread = None 