"""Command-line demo showcasing the high-level SIP client.

This script sends a SIP OPTIONS request (and optionally a MESSAGE) to a
remote server, logging the responses and any negotiated call events. It is
intended for manual experimentation rather than automated testing.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Optional

from . import (
	CallHangupEvent,
	Client,
	DigestCredentials,
	OptionResponseEvent,
	SDPNegotiatedEvent,
)


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Run a simple SIP client demo")
	parser.add_argument("host", nargs="?", default="demo.mizu-voip.com", help="Remote SIP host")
	parser.add_argument("port", nargs="?", type=int, default=37075, help="Remote SIP port")
	parser.add_argument(
		"--protocol",
		choices={"UDP", "TCP"},
		default="UDP",
		help="Transport protocol to use",
	)
	parser.add_argument("--identity", default="sipx-demo", help="Local SIP identity username")
	parser.add_argument("--display-name", default="sipx demo", help="Optional display name")
	parser.add_argument("--remote-uri", help="Override remote SIP URI (defaults to sip:host:port)")
	parser.add_argument("--user-agent", default="sipx-demo/0.1", help="User-Agent header value")
	parser.add_argument("--username", help="Digest auth username")
	parser.add_argument("--password", help="Digest auth password")
	parser.add_argument("--realm", help="Digest auth realm override")
	parser.add_argument(
		"--message",
		help="Optional MESSAGE payload to send after OPTIONS",
	)
	parser.add_argument(
		"--message-uri",
		help="Override MESSAGE target URI (defaults to remote URI)",
	)
	parser.add_argument(
		"--wait",
		type=float,
		default=2.0,
		help="Seconds to keep the client alive to process events",
	)
	parser.add_argument(
		"--log-level",
		default="INFO",
		choices={"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"},
		help="Logging verbosity",
	)
	parser.add_argument(
		"--show-raw",
		action="store_true",
		help="Log raw SIP responses at DEBUG level",
	)
	return parser


def _configure_logging(level: str) -> None:
	logging.basicConfig(
		level=getattr(logging, level.upper(), logging.INFO),
		format="%(asctime)s %(levelname)s %(name)s %(message)s",
	)


def _register_event_handlers(show_raw: bool) -> None:
	Client._event_handlers.clear()

	@Client.event_handler("OptionResponse")
	def _on_option(event: OptionResponseEvent) -> None:
		response = event.response
		logging.info(
			"OPTIONS %s %s (latency %.0f ms)",
			response.status_code,
			response.status_text,
			(response.duration or 0) * 1000,
		)
		if show_raw and response.response_raw:
			logging.debug("Raw response:\n%s", response.response_raw.strip())

	@Client.event_handler("SDPNegotiated")
	def _on_sdp(event: SDPNegotiatedEvent) -> None:
		first_line = event.sdp.splitlines()[0] if event.sdp else "<empty>"
		logging.info("SDP negotiated (%s…)", first_line[:60])

	@Client.event_handler("CallHangup")
	def _on_hangup(event: CallHangupEvent) -> None:
		source = "remote" if event.by_remote else "local"
		logging.info("Call hangup from %s", source)


async def _run_demo(args: argparse.Namespace) -> int:
	_configure_logging(args.log_level)
	_register_event_handlers(args.show_raw)

	credentials: Optional[DigestCredentials] = None
	if args.username and args.password:
		credentials = DigestCredentials(
			username=args.username,
			password=args.password,
			realm=args.realm,
		)
	elif args.username or args.password:
		logging.error("Both username and password are required for digest auth")
		return 2

	remote_uri = args.remote_uri or f"sip:{args.host}:{args.port}"
	message_uri = args.message_uri or remote_uri

	logging.info("Connecting to %s via %s", remote_uri, args.protocol)

	try:
		async with Client(
			(args.host, args.port),
			protocol=args.protocol,
			identity=args.identity,
			display_name=args.display_name,
			remote_uri=remote_uri,
			user_agent=args.user_agent,
			credentials=credentials,
		) as client:
			response = await client.options()
			if response.timed_out:
				logging.warning("OPTIONS request timed out")
			elif response.status_code and response.status_code >= 400:
				logging.warning(
					"OPTIONS rejected with %s %s",
					response.status_code,
					response.status_text,
				)

			if args.message:
				logging.info("Sending MESSAGE (%d bytes)", len(args.message))
				await client.message(
					args.message,
					uri=message_uri,
					content_type="text/plain",
					wait_response=False,
				)

			if args.wait > 0:
				logging.info("Waiting %.1f seconds for incoming events", args.wait)
				await asyncio.sleep(args.wait)

	except Exception as exc:  # pragma: no cover - demo convenience
		logging.exception("Demo failed: %s", exc)
		return 1

	logging.info("Demo finished")
	return 0


def main() -> int:
	parser = _build_parser()
	args = parser.parse_args()
	return asyncio.run(_run_demo(args))


if __name__ == "__main__":
	raise SystemExit(main())
