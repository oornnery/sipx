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

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import (
	Call,
	CallHangupEvent,
	Client,
	DigestCredentials,
	OptionResponseEvent,
	SDPNegotiatedEvent,
)
from ._fsm import CallState


CONSOLE = Console()
SHOW_RAW_RESPONSES = False
on = Client.event_handler


def _option_response_handler(event: OptionResponseEvent) -> None:
	response = event.response
	code = response.status_code or 0
	text = response.status_text or ""
	latency_ms = int((response.duration or 0) * 1000)
	logging.info(f"OPTIONS {code} {text} ({latency_ms} ms)")
	if SHOW_RAW_RESPONSES and response.response_raw:
		body = response.response_raw.strip() or "<empty>"
		CONSOLE.print(
			Panel.fit(
				body,
				title="OPTIONS Raw Response",
				border_style="cyan",
			)
		)


def _sdp_negotiated_handler(event: SDPNegotiatedEvent) -> None:
	first_line = event.sdp.splitlines()[0] if event.sdp else "<empty>"
	logging.info(f"SDP negotiated ({first_line[:60]})")


def _hangup_handler(event: CallHangupEvent) -> None:
	source = "remote" if event.by_remote else "local"
	logging.info(f"Call hangup from {source}")


_EVENT_HANDLERS = [
	("OptionResponse", _option_response_handler),
	("SDPNegotiated", _sdp_negotiated_handler),
	("CallHangup", _hangup_handler),
]


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
	parser.add_argument("--identity", help="Local SIP identity username (defaults to username)")
	parser.add_argument("--display-name", help="Optional display name")
	parser.add_argument("--remote-uri", help="Override remote SIP URI (defaults to sip:host:port)")
	parser.add_argument("--user-agent", default="sipx-demo/0.1", help="User-Agent header value")
	parser.add_argument("--username", default="1111", help="Digest auth username")
	parser.add_argument("--password", default="1111xxx", help="Digest auth password")
	parser.add_argument("--realm", help="Digest auth realm override")
	parser.add_argument(
		"--message",
		help="MESSAGE payload to send after OPTIONS (defaults to a friendly greeting)",
	)
	parser.add_argument(
		"--message-uri",
		help="Override MESSAGE target URI (defaults to remote URI)",
	)
	parser.add_argument(
		"--skip-message",
		action="store_true",
		help="Skip sending the MESSAGE request",
	)
	parser.add_argument(
		"--skip-invite",
		action="store_true",
		help="Skip placing the INVITE call",
	)
	parser.add_argument(
		"--skip-register",
		action="store_true",
		help="Skip the REGISTER transaction",
	)
	parser.add_argument(
		"--skip-options",
		action="store_true",
		help="Skip the OPTIONS capability probe",
	)
	parser.add_argument(
		"--wait",
		type=float,
		default=2.0,
		help="Seconds to keep the client alive to process events",
	)
	parser.add_argument(
		"--register-domain",
		help="Domain/host:port to use in REGISTER request (defaults to host[:port])",
	)
	parser.add_argument(
		"--register-expires",
		type=int,
		default=300,
		help="Expires value (seconds) to use when registering",
	)
	parser.add_argument(
		"--log-level",
		default="INFO",
		choices={"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"},
		help="Logging verbosity",
	)
	parser.add_argument(
		"--debug",
		action="store_true",
		help="Shortcut for --log-level=DEBUG with extra diagnostics",
	)
	parser.add_argument(
		"--show-raw",
		action="store_true",
		help="Log raw SIP responses at DEBUG level",
	)
	return parser




def _configure_logging(level: str, debug: bool) -> None:
	effective_level = "DEBUG" if debug else level
	logging.basicConfig(
		level=getattr(logging, effective_level.upper(), logging.INFO),
		format="%(message)s",
		handlers=[
			RichHandler(
				console=CONSOLE,
				rich_tracebacks=True,
				show_path=False,
				show_time=False,
			)
		],
		force=True,
	)
	if debug:
		logging.getLogger().setLevel(logging.DEBUG)


def _register_event_handlers(show_raw: bool) -> None:
	global SHOW_RAW_RESPONSES
	SHOW_RAW_RESPONSES = show_raw
	Client._event_handlers.clear()
	for name, handler in _EVENT_HANDLERS:
		on(name)(handler)


async def _run_demo(args: argparse.Namespace) -> int:
	_configure_logging(args.log_level, args.debug)
	_register_event_handlers(args.show_raw or args.debug)

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

	identity = args.identity or args.username or "sipx-demo"
	display_name = args.display_name or identity

	remote_uri = args.remote_uri or f"sip:{args.host}:{args.port}"
	register_domain = args.register_domain or args.host
	if register_domain and ":" not in register_domain and args.port:
		register_domain = f"{register_domain}:{args.port}"
	message_uri = args.message_uri
	if not message_uri:
		if args.username:
			message_uri = f"sip:{args.username}@{register_domain}"
		else:
			message_uri = remote_uri

	logging.info(f"Connecting to {remote_uri} via {args.protocol}")

	register_result = "Not attempted"
	options_result = "Not attempted"
	invite_result = "Not attempted"
	message_result = "Not attempted"
	call_to_bye: Optional[Call] = None

	def _render_status(code: Optional[int], text: Optional[str]) -> str:
		if code is not None and text:
			return f"{code} {text}"
		if code is not None:
			return f"{code}"
		if text:
			return text
		return "No status"

	try:
		async with Client(
			(args.host, args.port),
			protocol=args.protocol,
			identity=identity,
			display_name=display_name,
			remote_uri=remote_uri,
			user_agent=args.user_agent,
			credentials=credentials,
		) as client:
			with Progress(
				SpinnerColumn(),
				TextColumn("[progress.description]{task.description}"),
				console=CONSOLE,
				transient=True,
			) as progress:
				if args.skip_register:
					logging.info("Skipping REGISTER step (requested)")
					register_result = "Skipped (requested)"
				elif credentials:
					register_task = progress.add_task("[cyan]REGISTER[/] pending", total=1)
					progress.update(register_task, description="[cyan]REGISTER[/] in progress")
					logging.info(f"Sending REGISTER for {args.username or identity}")
					register_response = await client.register(
						username=args.username,
						domain=register_domain,
						expires=args.register_expires,
					)
					status_line = _render_status(register_response.status_code, register_response.status_text)
					code = register_response.status_code or 0
					if code >= 400:
						logging.warning(f"REGISTER failed with {status_line}")
						register_result = f"Failed ({status_line})"
						progress.update(register_task, advance=1, description=f"[red]REGISTER {status_line}")
					else:
						logging.info(f"REGISTER {status_line}")
						register_result = f"OK ({status_line})" if status_line else "OK"
						progress.update(register_task, advance=1, description=f"[green]REGISTER {status_line or 'success'}")
				else:
					logging.warning("Skipping REGISTER; credentials not provided")
					register_result = "Skipped (no credentials)"

				if args.skip_options:
					logging.info("Skipping OPTIONS step (requested)")
					options_result = "Skipped (requested)"
				else:
					options_task = progress.add_task("[cyan]OPTIONS[/] pending", total=1)
					progress.update(options_task, description="[cyan]OPTIONS[/] in progress")
					options_response = await client.options()
					if options_response.timed_out:
						logging.warning("OPTIONS request timed out")
						options_result = "Timed out"
						progress.update(options_task, advance=1, description="[red]OPTIONS timed out")
					else:
						status_line = _render_status(options_response.status_code, options_response.status_text)
						code = options_response.status_code or 0
						if code >= 400:
							logging.warning(f"OPTIONS rejected with {status_line}")
							options_result = f"Rejected ({status_line})"
							progress.update(options_task, advance=1, description=f"[red]OPTIONS {status_line}")
						elif 100 <= code < 200:
							logging.warning(f"OPTIONS provisional {status_line}")
							options_result = f"Provisional ({status_line})"
							progress.update(options_task, advance=1, description=f"[yellow]OPTIONS {status_line or 'provisional'}")
						else:
							logging.info(f"OPTIONS {status_line}")
							options_result = f"OK ({status_line})" if status_line else "OK"
							progress.update(options_task, advance=1, description=f"[green]OPTIONS {status_line or 'success'}")

				if args.skip_invite:
					logging.info("Skipping INVITE step (requested)")
					invite_result = "Skipped (requested)"
				else:
					invite_task = progress.add_task("[cyan]INVITE[/] pending", total=1)
					progress.update(invite_task, description="[cyan]INVITE[/] in progress")
					invite_call: Optional[Call]
					try:
						invite_call = await client.invite(remote_uri)
					except TimeoutError:
						logging.warning("INVITE request timed out")
						invite_result = "Timed out"
						progress.update(invite_task, advance=1, description="[red]INVITE timed out")
					except Exception as exc:
						logging.exception(f"INVITE failed: {exc}")
						invite_result = f"Error ({exc})"
						progress.update(invite_task, advance=1, description="[red]INVITE error")
					else:
						response = invite_call.last_response
						if not response:
							logging.warning("INVITE finished without transport response")
							invite_result = "No response"
							progress.update(invite_task, advance=1, description="[yellow]INVITE no response")
						elif response.timed_out:
							logging.warning("INVITE request timed out")
							invite_result = "Timed out"
							progress.update(invite_task, advance=1, description="[red]INVITE timed out")
						else:
							status_line = _render_status(response.status_code, response.status_text)
							code = response.status_code or 0
							if code >= 400:
								logging.warning(f"INVITE rejected with {status_line}")
								invite_result = f"Rejected ({status_line})"
								progress.update(invite_task, advance=1, description=f"[red]INVITE {status_line}")
							elif 300 <= code < 400:
								logging.warning(f"INVITE redirected with {status_line}")
								invite_result = f"Redirect ({status_line})"
								progress.update(invite_task, advance=1, description=f"[yellow]INVITE {status_line}")
							elif 200 <= code < 300:
								logging.info(f"INVITE {status_line}")
								invite_result = f"OK ({status_line})" if status_line else "OK"
								progress.update(invite_task, advance=1, description=f"[green]INVITE {status_line or 'success'}")
								call_to_bye = invite_call
							else:
								logging.warning(f"INVITE provisional {status_line}")
								invite_result = f"Provisional ({status_line})"
								progress.update(invite_task, advance=1, description=f"[yellow]INVITE {status_line or 'provisional'}")

				if args.skip_message:
					logging.info("Skipping MESSAGE step (requested)")
					message_result = "Skipped (requested)"
				else:
					payload = args.message or "Hello from sipx demo"
					message_task = progress.add_task("[cyan]MESSAGE[/] pending", total=1)
					progress.update(message_task, description="[cyan]MESSAGE[/] in progress")
					logging.info(f"Sending MESSAGE ({len(payload)} bytes)")
					message_response = await client.message(
						payload,
						uri=message_uri,
						content_type="text/plain",
						wait_response=True,
					)
					if message_response.timed_out:
						logging.warning("MESSAGE request timed out")
						message_result = "Timed out"
						progress.update(message_task, advance=1, description="[red]MESSAGE timed out")
					else:
						status_line = _render_status(message_response.status_code, message_response.status_text)
						code = message_response.status_code or 0
						if code >= 400:
							logging.warning(f"MESSAGE rejected with {status_line}")
							message_result = f"Rejected ({status_line})"
							progress.update(message_task, advance=1, description=f"[red]MESSAGE {status_line}")
						elif 200 <= code < 300:
							logging.info(f"MESSAGE {status_line}")
							message_result = f"OK ({status_line})" if status_line else "OK"
							progress.update(message_task, advance=1, description=f"[green]MESSAGE {status_line or 'success'}")
						elif 100 <= code < 200:
							logging.warning(f"MESSAGE stalled at provisional response {status_line}")
							message_result = f"Provisional only ({status_line})"
							progress.update(message_task, advance=1, description=f"[yellow]MESSAGE {status_line or 'provisional'}")
						else:
							logging.warning("MESSAGE completed without a final status code")
							message_result = "No final status"
							progress.update(message_task, advance=1, description="[yellow]MESSAGE no status")

			if args.wait > 0:
				logging.info(f"Waiting {args.wait:.1f} seconds for incoming events")
				await asyncio.sleep(args.wait)

			if call_to_bye and call_to_bye.state == CallState.CONNECTED:
				logging.info("Sending BYE to terminate established call")
				try:
					bye_response = await call_to_bye.bye(timeout=5.0)
				except Exception as exc:  # pragma: no cover - demo convenience
					logging.warning(f"BYE failed: {exc}")
				else:
					if bye_response.timed_out:
						logging.warning("BYE request timed out")
					else:
						status_line = _render_status(bye_response.status_code, bye_response.status_text)
						logging.info(f"BYE {status_line}")

	except Exception as exc:  # pragma: no cover - demo convenience
		logging.exception(f"Demo failed: {exc}")
		return 1

	summary_lines = [
		f"[bold]REGISTER[/]: {register_result}",
		f"[bold]OPTIONS[/]: {options_result}",
		f"[bold]INVITE[/]: {invite_result}",
		f"[bold]MESSAGE[/]: {message_result}",
	]
	CONSOLE.print(Panel("\n".join(summary_lines), title="Demo Summary", border_style="green"))
	logging.info("Demo finished")
	return 0


def main() -> int:
	parser = _build_parser()
	args = parser.parse_args()
	return asyncio.run(_run_demo(args))


if __name__ == "__main__":
	raise SystemExit(main())
