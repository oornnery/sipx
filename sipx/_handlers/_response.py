"""
Response handlers for SIP provisional and final responses.

This module provides handlers that categorize and process different types
of SIP responses according to RFC 3261.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional, Callable

from ._base import EventHandler, EventContext
from .._utils import logger

if TYPE_CHECKING:
    from .._models._message import Response


class ResponseCategory(Enum):
    """
    SIP response categories based on status code ranges.

    According to RFC 3261 Section 7.2:
    - 1xx: Provisional — request received, continuing to process
    - 2xx: Success — action was successfully received, understood, and accepted
    - 3xx: Redirection — further action needs to be taken
    - 4xx: Client Error — request contains bad syntax or cannot be fulfilled
    - 5xx: Server Error — server failed to fulfill an apparently valid request
    - 6xx: Global Failure — request cannot be fulfilled at any server
    """

    PROVISIONAL = "1xx"
    SUCCESS = "2xx"
    REDIRECTION = "3xx"
    CLIENT_ERROR = "4xx"
    SERVER_ERROR = "5xx"
    GLOBAL_FAILURE = "6xx"

    @classmethod
    def from_status_code(cls, status_code: int) -> ResponseCategory:
        """
        Determine response category from status code.

        Args:
            status_code: SIP response status code

        Returns:
            Corresponding ResponseCategory
        """
        if 100 <= status_code < 200:
            return cls.PROVISIONAL
        elif 200 <= status_code < 300:
            return cls.SUCCESS
        elif 300 <= status_code < 400:
            return cls.REDIRECTION
        elif 400 <= status_code < 500:
            return cls.CLIENT_ERROR
        elif 500 <= status_code < 600:
            return cls.SERVER_ERROR
        elif 600 <= status_code < 700:
            return cls.GLOBAL_FAILURE
        else:
            # Default to server error for unknown codes
            return cls.SERVER_ERROR


class ProvisionalResponseHandler(EventHandler):
    """
    Handler for provisional responses (1xx).

    Provisional responses indicate that the request was received and is being
    processed, but the final result is not yet known.

    Common provisional responses:
    - 100 Trying: Server started processing request
    - 180 Ringing: Destination device is alerting user
    - 181 Call is Being Forwarded: Call forwarding in progress
    - 182 Queued: Call placed in queue
    - 183 Session Progress: Early media information available
    """

    def __init__(
        self,
        on_provisional: Optional[Callable[[Response, EventContext], None]] = None,
        on_trying: Optional[Callable[[Response, EventContext], None]] = None,
        on_ringing: Optional[Callable[[Response, EventContext], None]] = None,
        on_progress: Optional[Callable[[Response, EventContext], None]] = None,
    ):
        """
        Initialize provisional response handler.

        Args:
            on_provisional: Callback for any provisional response
            on_trying: Callback specifically for 100 Trying
            on_ringing: Callback specifically for 180 Ringing
            on_progress: Callback specifically for 183 Session Progress
        """
        self.on_provisional = on_provisional
        self.on_trying = on_trying
        self.on_ringing = on_ringing
        self.on_progress = on_progress

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Process provisional responses."""
        category = ResponseCategory.from_status_code(response.status_code)

        if category == ResponseCategory.PROVISIONAL:
            # Store in context for tracking
            if "provisional_responses" not in context.metadata:
                context.metadata["provisional_responses"] = []
            context.metadata["provisional_responses"].append(response)

            # Log provisional response
            logger.info(
                f"📨 Provisional: {response.status_code} {response.reason_phrase}"
            )

            # Handle specific provisional responses
            if response.status_code == 100:
                # 100 Trying - suppress retransmissions
                context.metadata["trying_received"] = True
                logger.debug("100 Trying received, retransmissions suppressed")
                if self.on_trying:
                    self.on_trying(response, context)

            elif response.status_code == 180:
                # 180 Ringing - remote party alerted
                context.metadata["ringing"] = True
                logger.info("📞 Remote party ringing")
                if self.on_ringing:
                    self.on_ringing(response, context)

            elif response.status_code == 183:
                # 183 Session Progress - early media available
                context.metadata["session_progress"] = True
                if response.content:
                    context.metadata["early_media_sdp"] = response.content
                logger.info("📡 Session progress (early media available)")
                if self.on_progress:
                    self.on_progress(response, context)

            # Call general provisional callback
            if self.on_provisional:
                self.on_provisional(response, context)

        return response


class FinalResponseHandler(EventHandler):
    """
    Handler for final responses (2xx-6xx).

    Final responses indicate the definitive result of request processing.

    Response categories:
    - 2xx Success: Request successfully processed
    - 3xx Redirection: Further action needed (contact moved, etc.)
    - 4xx Client Error: Request contains errors
    - 5xx Server Error: Server failed to process valid request
    - 6xx Global Failure: Request cannot be fulfilled anywhere
    """

    def __init__(
        self,
        on_success: Optional[Callable[[Response, EventContext], None]] = None,
        on_redirect: Optional[Callable[[Response, EventContext], None]] = None,
        on_client_error: Optional[Callable[[Response, EventContext], None]] = None,
        on_server_error: Optional[Callable[[Response, EventContext], None]] = None,
        on_global_failure: Optional[Callable[[Response, EventContext], None]] = None,
    ):
        """
        Initialize final response handler.

        Args:
            on_success: Callback for 2xx responses
            on_redirect: Callback for 3xx responses
            on_client_error: Callback for 4xx responses
            on_server_error: Callback for 5xx responses
            on_global_failure: Callback for 6xx responses
        """
        self.on_success = on_success
        self.on_redirect = on_redirect
        self.on_client_error = on_client_error
        self.on_server_error = on_server_error
        self.on_global_failure = on_global_failure

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Process final responses."""
        category = ResponseCategory.from_status_code(response.status_code)

        # Only process final responses (not provisional)
        if category == ResponseCategory.PROVISIONAL:
            return response

        # Store final response in context
        context.metadata["final_response"] = response
        context.metadata["response_category"] = category

        # Log final response with appropriate emoji
        emoji_map = {
            ResponseCategory.SUCCESS: "✅",
            ResponseCategory.REDIRECTION: "↪️",
            ResponseCategory.CLIENT_ERROR: "❌",
            ResponseCategory.SERVER_ERROR: "⚠️",
            ResponseCategory.GLOBAL_FAILURE: "🚫",
        }
        emoji = emoji_map.get(category, "📩")

        logger.info(
            f"{emoji} Final: {response.status_code} {response.reason_phrase} ({category.value})"
        )

        # Call appropriate callback based on category
        if category == ResponseCategory.SUCCESS and self.on_success:
            self.on_success(response, context)
        elif category == ResponseCategory.REDIRECTION and self.on_redirect:
            self.on_redirect(response, context)
        elif category == ResponseCategory.CLIENT_ERROR and self.on_client_error:
            self.on_client_error(response, context)
        elif category == ResponseCategory.SERVER_ERROR and self.on_server_error:
            self.on_server_error(response, context)
        elif category == ResponseCategory.GLOBAL_FAILURE and self.on_global_failure:
            self.on_global_failure(response, context)

        return response


class ResponseFilterHandler(EventHandler):
    """
    Handler that filters responses by status code or range.

    Useful for creating custom handlers that only process specific responses.
    """

    def __init__(
        self,
        status_code: Optional[int] = None,
        status_range: Optional[tuple[int, int]] = None,
        callback: Optional[Callable[[Response, EventContext], None]] = None,
    ):
        """
        Initialize response filter handler.

        Args:
            status_code: Specific status code to filter (e.g., 200)
            status_range: Status code range to filter (e.g., (200, 299) for 2xx)
            callback: Callback to invoke for matching responses
        """
        self.status_code = status_code
        self.status_range = status_range
        self.callback = callback

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Filter and process matching responses."""
        matches = False

        # Check if response matches filter
        if self.status_code and response.status_code == self.status_code:
            matches = True
        elif self.status_range:
            min_code, max_code = self.status_range
            if min_code <= response.status_code <= max_code:
                matches = True

        # Invoke callback if response matches
        if matches and self.callback:
            self.callback(response, context)

        return response

