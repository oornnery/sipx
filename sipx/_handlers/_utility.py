"""
Utility handlers for common SIP client tasks.

This module provides ready-to-use handlers for logging, retries,
and header manipulation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ._base import EventHandler, EventContext
from .._utils import logger

if TYPE_CHECKING:
    from .._models._message import Request, Response


class LoggingHandler(EventHandler):
    """
    Handler that logs SIP messages.

    Logs outgoing requests, incoming responses, and errors.
    """

    def __init__(self, custom_logger=None, verbose: bool = True):
        """
        Initialize logging handler.

        Args:
            custom_logger: Optional custom logger instance
            verbose: If True, includes more details in logs
        """
        self.logger = custom_logger or logger
        self.verbose = verbose

    def on_request(self, request: Request, context: EventContext) -> Request:
        """Log outgoing request."""
        dest = context.destination
        if self.verbose and dest:
            msg = f">>> Sending {request.method} to {dest.host}:{dest.port}"
        else:
            msg = f">>> Sending {request.method}"

        self.logger.info(msg)
        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Log incoming response."""
        if self.verbose:
            msg = f"<<< Received {response.status_code} {response.reason_phrase}"
        else:
            msg = f"<<< Received {response.status_code}"

        self.logger.info(msg)
        return response

    def on_error(self, error: Exception, context: EventContext) -> None:
        """Log error."""
        self.logger.error(f"!!! Error: {error}")


class RetryHandler(EventHandler):
    """
    Handler that implements retry logic for failed requests.

    Tracks retry attempts and signals when requests should be retried
    based on response status codes.
    """

    def __init__(self, max_retries: int = 3, retry_codes: Optional[list[int]] = None):
        """
        Initialize retry handler.

        Args:
            max_retries: Maximum number of retry attempts
            retry_codes: Status codes that trigger retry (default: [408, 500, 503])
        """
        self.max_retries = max_retries
        self.retry_codes = retry_codes or [408, 500, 503]
        self._retry_count: dict = {}

    def on_request(self, request: Request, context: EventContext) -> Request:
        """Track request for retry counting."""
        request_id = id(request)
        if request_id not in self._retry_count:
            self._retry_count[request_id] = 0
        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Check if response should trigger retry."""
        if response.status_code in self.retry_codes:
            request_id = id(response.request) if response.request else None
            if request_id and self._retry_count.get(request_id, 0) < self.max_retries:
                self._retry_count[request_id] += 1
                # Signal that retry should happen (client must check this)
                context.metadata["should_retry"] = True
                context.metadata["retry_count"] = self._retry_count[request_id]
                logger.info(
                    f"Retry {self._retry_count[request_id]}/{self.max_retries} "
                    f"for status {response.status_code}"
                )
        return response


class HeaderInjectionHandler(EventHandler):
    """
    Handler that injects custom headers into requests.

    Useful for adding common headers like User-Agent, custom extensions, etc.
    """

    def __init__(self, headers: dict, overwrite: bool = False):
        """
        Initialize header injection handler.

        Args:
            headers: Headers to inject (key-value pairs)
            overwrite: If True, overwrite existing headers; if False, only add missing ones
        """
        self.headers = headers
        self.overwrite = overwrite

    def on_request(self, request: Request, context: EventContext) -> Request:
        """Inject headers into request."""
        for key, value in self.headers.items():
            if self.overwrite or key not in request.headers:
                request.headers[key] = value
        return request


class TimeoutHandler(EventHandler):
    """
    Handler that tracks request timeouts.

    Stores timeout information in context for monitoring and debugging.
    """

    def __init__(self, default_timeout: float = 30.0):
        """
        Initialize timeout handler.

        Args:
            default_timeout: Default timeout in seconds
        """
        self.default_timeout = default_timeout
        self._request_times: dict = {}

    def on_request(self, request: Request, context: EventContext) -> Request:
        """Record request start time."""
        import time

        request_id = id(request)
        self._request_times[request_id] = time.time()
        context.metadata["request_start_time"] = self._request_times[request_id]
        context.metadata["timeout"] = self.default_timeout
        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Calculate request duration."""
        import time

        if response.request:
            request_id = id(response.request)
            start_time = self._request_times.get(request_id)
            if start_time:
                duration = time.time() - start_time
                context.metadata["request_duration"] = duration

                if duration > self.default_timeout:
                    logger.warning(
                        f"Request exceeded timeout: {duration:.2f}s > {self.default_timeout}s"
                    )

                # Cleanup
                del self._request_times[request_id]

        return response

    def on_error(self, error: Exception, context: EventContext) -> None:
        """Handle timeout errors."""
        if isinstance(error, TimeoutError):
            logger.error(f"Request timed out after {self.default_timeout}s")

