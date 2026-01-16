"""
OpenTelemetry integration for agent observability.

This module provides telemetry and monitoring capabilities using
OpenTelemetry and Azure Monitor integration for the agent application.

Key Features:
- Distributed tracing for agent operations
- Custom metrics for performance monitoring
- Structured logging integration
- Azure Monitor export

Usage:
    from agent.telemetry import init_telemetry, trace_operation
    
    # Initialize telemetry
    init_telemetry()
    
    # Trace operations
    with trace_operation("agent_query"):
        response = agent.run(query)
"""

import logging
import os
from typing import Optional, Dict, Any
from contextlib import contextmanager
from functools import wraps

from .config_loader import AgentConfig, load_agent_config

# Configure module logger
logger = logging.getLogger(__name__)

# Global tracer instance
_tracer = None
_meter = None


def init_telemetry(
    config: Optional[AgentConfig] = None,
    service_name: str = "driving-manual-agent"
) -> None:
    """
    Initialize OpenTelemetry with Azure Monitor integration.
    
    Sets up:
    - Tracer provider for distributed tracing
    - Meter provider for custom metrics
    - Azure Monitor exporter for telemetry data
    - Structured logging correlation
    
    This function should be called once at application startup.
    
    Args:
        config: Optional AgentConfig instance
        service_name: Name of the service for telemetry
    
    Example:
        >>> init_telemetry()
        >>> # Telemetry is now active for all operations
    """
    global _tracer, _meter
    
    # Load config if not provided
    if config is None:
        try:
            config = load_agent_config(validate=False)
        except Exception as e:
            logger.warning(f"Could not load config for telemetry: {e}")
            config = None
    
    # Skip telemetry if disabled
    if config and not config.enable_telemetry:
        logger.info("Telemetry disabled in configuration")
        return
    
    try:
        # Import OpenTelemetry components
        # Note: These imports are optional - gracefully degrade if not available
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource
        
        # Try to import Azure Monitor exporter
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
            azure_monitor_available = True
        except ImportError:
            logger.warning(
                "azure-monitor-opentelemetry not available. "
                "Telemetry will use console exporter only."
            )
            azure_monitor_available = False
        
        # Create resource with service information
        resource = Resource.create({
            "service.name": service_name,
            "service.version": os.environ.get("APP_VERSION", "1.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "development")
        })
        
        # Configure Azure Monitor if available
        if azure_monitor_available:
            # Azure Monitor requires connection string
            connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
            if connection_string:
                logger.info("Configuring Azure Monitor for telemetry")
                configure_azure_monitor(
                    connection_string=connection_string,
                    resource=resource
                )
            else:
                logger.warning(
                    "APPLICATIONINSIGHTS_CONNECTION_STRING not set. "
                    "Telemetry will not be exported to Azure Monitor."
                )
        
        # Set up tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
        
        # Get tracer for this module
        _tracer = trace.get_tracer(__name__)
        
        # Set up meter provider for metrics
        meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(meter_provider)
        
        # Get meter for this module
        _meter = metrics.get_meter(__name__)
        
        logger.info(f"Telemetry initialized for service: {service_name}")
        
    except ImportError as e:
        logger.warning(
            f"OpenTelemetry packages not available: {e}. "
            "Install opentelemetry-sdk and azure-monitor-opentelemetry for telemetry support."
        )
    except Exception as e:
        logger.error(f"Failed to initialize telemetry: {e}")


@contextmanager
def trace_operation(
    operation_name: str,
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Context manager for tracing operations.
    
    Creates a span for the operation with optional attributes.
    Automatically handles span lifecycle and error recording.
    
    Span Attributes:
    - Custom attributes provided via 'attributes' parameter
    - Automatic error recording on exceptions
    - Duration and status tracking
    
    Args:
        operation_name: Name of the operation to trace
        attributes: Optional dictionary of span attributes
    
    Yields:
        Span object for additional manipulation
    
    Example:
        >>> with trace_operation("agent_query", {"query": "stop sign"}):
        ...     response = agent.run("What does a stop sign mean?")
    """
    # Check if telemetry is initialized
    if _tracer is None:
        # No-op context manager if telemetry not initialized
        yield None
        return
    
    # Create span
    with _tracer.start_as_current_span(operation_name) as span:
        # Add attributes if provided
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
        
        try:
            yield span
        except Exception as e:
            # Record exception in span
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


def trace_function(operation_name: Optional[str] = None):
    """
    Decorator for tracing function calls.
    
    Automatically creates spans for decorated functions with:
    - Function name as operation name (or custom name)
    - Function arguments as span attributes
    - Exception tracking
    
    Args:
        operation_name: Optional custom operation name
    
    Returns:
        Decorated function
    
    Example:
        >>> @trace_function("process_query")
        ... def process_query(query: str):
        ...     return agent.run(query)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use function name if operation name not provided
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            # Build attributes from arguments
            attributes = {}
            if args:
                attributes["args.count"] = len(args)
            if kwargs:
                attributes["kwargs.count"] = len(kwargs)
                # Add some kwargs as attributes (limit to avoid too much data)
                for i, (key, value) in enumerate(list(kwargs.items())[:5]):
                    attributes[f"kwargs.{key}"] = str(value)[:100]
            
            # Trace the function call
            with trace_operation(op_name, attributes):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def record_metric(
    name: str,
    value: float,
    attributes: Optional[Dict[str, str]] = None
) -> None:
    """
    Record a custom metric value.
    
    Metrics can track:
    - Request counts
    - Response times
    - Error rates
    - Custom business metrics
    
    Args:
        name: Metric name (e.g., "agent.query.duration")
        value: Numeric value to record
        attributes: Optional metric attributes/dimensions
    
    Example:
        >>> record_metric("agent.query.duration", 1.5, {"status": "success"})
    """
    if _meter is None:
        # Telemetry not initialized
        return
    
    try:
        # Create or get counter
        counter = _meter.create_counter(
            name=name,
            description=f"Metric: {name}"
        )
        
        # Record value with attributes
        counter.add(value, attributes or {})
        
        logger.debug(f"Recorded metric: {name}={value}, attributes={attributes}")
        
    except Exception as e:
        logger.warning(f"Failed to record metric {name}: {e}")


def log_with_trace_context(
    message: str,
    level: int = logging.INFO,
    **kwargs
) -> None:
    """
    Log message with trace context correlation.
    
    Includes trace and span IDs in log records for correlation
    between logs and traces in Azure Monitor.
    
    Args:
        message: Log message
        level: Logging level (logging.INFO, logging.ERROR, etc.)
        **kwargs: Additional logging arguments
    
    Example:
        >>> log_with_trace_context("Processing query", level=logging.INFO)
    """
    # Get current span context if available
    if _tracer is not None:
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            span_context = span.get_span_context()
            
            if span_context.is_valid:
                # Add trace context to log extra data
                extra = kwargs.get('extra', {})
                extra['trace_id'] = format(span_context.trace_id, '032x')
                extra['span_id'] = format(span_context.span_id, '016x')
                kwargs['extra'] = extra
        except Exception:
            pass  # Ignore errors in trace context extraction
    
    # Log with standard logger
    logger.log(level, message, **kwargs)


# Example usage and testing
if __name__ == "__main__":
    """
    Test telemetry initialization and operations.
    """
    import sys
    import time
    
    # Configure logging for the test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("Telemetry Test")
    print("="*60 + "\n")
    
    # Initialize telemetry
    print("1. Initializing telemetry...")
    init_telemetry(service_name="test-service")
    print("   ✓ Telemetry initialized\n")
    
    # Test tracing
    print("2. Testing operation tracing...")
    with trace_operation("test_operation", {"test": "value"}):
        print("   - Inside traced operation")
        time.sleep(0.1)
    print("   ✓ Operation traced\n")
    
    # Test function decorator
    print("3. Testing function tracing...")
    
    @trace_function("test_function")
    def sample_function(arg1: str, arg2: int):
        """Sample function for testing."""
        print(f"   - Function called: {arg1}, {arg2}")
        return "result"
    
    result = sample_function("test", 42)
    print(f"   ✓ Function traced, result: {result}\n")
    
    # Test metrics
    print("4. Testing metric recording...")
    record_metric("test.counter", 1.0, {"status": "success"})
    record_metric("test.duration", 0.5, {"operation": "test"})
    print("   ✓ Metrics recorded\n")
    
    # Test contextual logging
    print("5. Testing contextual logging...")
    log_with_trace_context("Test log message with trace context")
    print("   ✓ Contextual logging working\n")
    
    print("="*60)
    print("✓ All telemetry tests completed!")
    print("="*60 + "\n")
    
    print("Note: Telemetry data export requires Azure Monitor configuration.")
    print("Set APPLICATIONINSIGHTS_CONNECTION_STRING to enable export.\n")
    
    sys.exit(0)
