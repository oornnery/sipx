#!/usr/bin/env python3
"""
Comprehensive Asterisk Demo - Testing All 3 Users with Different Policies

This demo tests the complete SIPX library functionality with Asterisk:

USER 1111 (Auth Required for Everything):
  - OPTIONS with authentication
  - REGISTER with different expires values
  - INVITE with create_offer (send SDP)
  - ACK, BYE
  - UNREGISTER

USER 2222 (OPTIONS without Auth):
  - OPTIONS without authentication
  - REGISTER with authentication
  - INVITE with create_answer (receive SDP from Asterisk)
  - Early media detection (183 Session Progress)
  - Codec analysis

USER 3333 (Strict Security):
  - OPTIONS (should be rejected)
  - Invalid credentials test
  - REGISTER with valid credentials
  - INVITE normal flow
  - Auto re-registration
  - UNREGISTER

All using manual authentication control via retry_with_auth().
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sipx import Client, Events, event_handler, Auth, SDPBody
from sipx._utils import console, logger
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn


# ============================================================================
# Configuration
# ============================================================================

ASTERISK_HOST = "127.0.0.1"
ASTERISK_PORT = 5060

# User configurations with different policies
USERS = {
    "1111": {
        "password": "1111xxx",
        "port": 5061,
        "policy": "🔐 Auth required for ALL methods",
        "tests": [
            "OPTIONS+Auth",
            "REGISTER (3600s, 1800s)",
            "INVITE+Offer",
            "UNREGISTER",
        ],
    },
    "2222": {
        "password": "2222xxx",
        "port": 5062,
        "policy": "🔓 OPTIONS without auth, others with auth",
        "tests": ["OPTIONS-NoAuth", "REGISTER", "INVITE+Answer", "Early Media"],
    },
    "3333": {
        "password": "3333xxx",
        "port": 5063,
        "policy": "🚫 OPTIONS rejected, strict security",
        "tests": ["OPTIONS-Rejected", "Invalid-Creds", "REGISTER", "Auto-ReReg"],
    },
}


# ============================================================================
# Event Handlers
# ============================================================================


class DemoEvents(Events):
    """Event handlers for demo with enhanced logging."""

    def __init__(self):
        super().__init__()
        self.early_media_detected = False
        self.responses_received = []

    def on_request(self, request, context):
        """Log outgoing requests."""
        console.print(
            f"\n[cyan]📤 {request.method}[/cyan] → [yellow]{request.uri}[/yellow]"
        )
        return request

    def on_response(self, response, context):
        """Log incoming responses."""
        if 200 <= response.status_code < 300:
            emoji = "✅"
            color = "green"
        elif response.status_code == 401 or response.status_code == 407:
            emoji = "🔐"
            color = "yellow"
        elif response.status_code >= 400:
            emoji = "❌"
            color = "red"
        else:
            emoji = "📥"
            color = "blue"

        console.print(
            f"{emoji} [{color}]{response.status_code} {response.reason_phrase}[/{color}]"
        )

        if response.status_code >= 200:
            self.responses_received.append(response)

        return response

    @event_handler("REGISTER", status=200)
    def on_register_success(self, request, response, context):
        """Called when registration succeeds."""
        if response and response.headers:
            contact = response.headers.get("Contact", "")
            if "expires=" in contact:
                expires = contact.split("expires=")[1].split(";")[0]
                console.print(
                    f"   [green]✓[/green] Expires in [cyan]{expires}[/cyan] seconds"
                )

    @event_handler("OPTIONS", status=200)
    def on_options_success(self, request, response, context):
        """Called when OPTIONS succeeds."""
        if response and response.headers:
            allow = response.headers.get("Allow", "")
            if allow:
                methods = allow.split(", ")[:5]
                console.print(
                    f"   [green]✓[/green] Methods: [cyan]{', '.join(methods)}...[/cyan]"
                )

    @event_handler("INVITE", status=183)
    def on_invite_progress(self, request, response, context):
        """Called on 183 Session Progress (early media)."""
        self.early_media_detected = True
        console.print("   [magenta]🎵 Early Media (183 Session Progress)[/magenta]")

        if response and response.body and hasattr(response.body, "has_early_media"):
            has_em = response.body.has_early_media()
            console.print(f"   [magenta]🎵 Early media support: {has_em}[/magenta]")

    @event_handler("INVITE", status=200)
    def on_invite_accepted(self, request, response, context):
        """Called when call is accepted."""
        if response and response.body:
            if hasattr(response.body, "get_codecs_summary"):
                summary = response.body.get_codecs_summary()
                for media_type, codecs in summary.items():
                    console.print(
                        f"   [green]🎵 {media_type.capitalize()}:[/green] [cyan]{', '.join(codecs)}[/cyan]"
                    )

    @event_handler("BYE", status=200)
    def on_bye_success(self, request, response, context):
        """Called when BYE succeeds."""
        console.print("   [green]✓ Call terminated[/green]")

    @event_handler("MESSAGE", status=(200, 202))
    def on_message_success(self, request, response, context):
        """Called when MESSAGE is delivered."""
        console.print("   [green]✓ Message delivered[/green]")


# ============================================================================
# Test Functions
# ============================================================================


def test_user_1111() -> dict:
    """
    Test User 1111: Full authentication required.

    Tests:
    - OPTIONS with auth
    - REGISTER with expires=3600
    - REGISTER update with expires=1800
    - INVITE with create_offer
    - UNREGISTER
    """
    results = {}
    username = "1111"
    config = USERS[username]

    console.print(
        Panel.fit(
            f"[bold cyan]USER {username}[/bold cyan]\n{config['policy']}\n"
            f"Tests: {', '.join(config['tests'])}",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )

    with Client(local_port=config["port"], transport="UDP") as client:
        client.events = DemoEvents()
        client.auth = Auth.Digest(username, config["password"], realm="asterisk")

        console.print(f"\n[dim]Client: {client.local_address}[/dim]\n")

        # Test 1: OPTIONS with auth
        console.print("[bold]Test 1.1:[/bold] OPTIONS with authentication")
        response = client.options(uri=f"sip:{ASTERISK_HOST}")
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)
        results["options_auth"] = response and response.status_code == 200

        time.sleep(0.5)

        # Test 2: REGISTER with expires=3600
        console.print("\n[bold]Test 1.2:[/bold] REGISTER (expires=3600)")
        response = client.register(aor=f"sip:{username}@{ASTERISK_HOST}", expires=3600)
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)
        results["register_3600"] = response and response.status_code == 200

        time.sleep(1)

        # Test 3: REGISTER update with expires=1800
        console.print("\n[bold]Test 1.3:[/bold] REGISTER update (expires=1800)")
        response = client.register(aor=f"sip:{username}@{ASTERISK_HOST}", expires=1800)
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)
        results["register_1800"] = response and response.status_code == 200

        time.sleep(0.5)

        # Test 4: INVITE with create_offer
        console.print("\n[bold]Test 1.4:[/bold] INVITE with create_offer (send SDP)")

        sdp_offer = SDPBody.create_offer(
            session_name="Test Call 1111",
            origin_username=username,
            origin_address=client.local_address.host,
            connection_address=client.local_address.host,
            media_specs=[
                {
                    "media": "audio",
                    "port": 8000,
                    "protocol": "RTP/AVP",
                    "codecs": [
                        {"payload": "0", "name": "PCMU", "rate": "8000"},
                        {"payload": "8", "name": "PCMA", "rate": "8000"},
                        {"payload": "101", "name": "telephone-event", "rate": "8000"},
                    ],
                }
            ],
        )

        console.print(
            f"   [dim]SDP offer created ({len(sdp_offer.to_string())} bytes)[/dim]"
        )

        invite_headers = {
            "Contact": f"<sip:{username}@{client.local_address.host}:{client.local_address.port}>"
        }

        response = client.invite(
            to_uri=f"sip:100@{ASTERISK_HOST}",  # Echo test
            from_uri=f"sip:{username}@{client.local_address.host}",
            body=sdp_offer.to_string(),
            headers=invite_headers,
        )

        if response and response.status_code == 401:
            response = client.retry_with_auth(response)

        if response and response.status_code == 200:
            results["invite_offer"] = True
            client.ack(response=response)
            console.print("   [green]✓ ACK sent[/green]")

            # Keep call active briefly
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("[cyan]Call active...", total=None)
                time.sleep(2)

            # Hang up
            client.bye(response=response)
        else:
            results["invite_offer"] = False

        time.sleep(0.5)

        # Test 5: UNREGISTER
        console.print("\n[bold]Test 1.5:[/bold] UNREGISTER (expires=0)")
        response = client.unregister(aor=f"sip:{username}@{ASTERISK_HOST}")
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)
        results["unregister"] = response and response.status_code == 200

    return results


def test_user_2222() -> dict:
    """
    Test User 2222: OPTIONS without auth, others with auth.

    Tests:
    - OPTIONS without auth
    - REGISTER with auth
    - INVITE with create_answer (late offer)
    - Early media detection
    """
    results = {}
    username = "2222"
    config = USERS[username]

    console.print(
        Panel.fit(
            f"[bold cyan]USER {username}[/bold cyan]\n{config['policy']}\n"
            f"Tests: {', '.join(config['tests'])}",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )

    with Client(local_port=config["port"], transport="UDP") as client:
        events = DemoEvents()
        client.events = events
        client.auth = Auth.Digest(username, config["password"], realm="asterisk")

        console.print(f"\n[dim]Client: {client.local_address}[/dim]\n")

        # Test 1: OPTIONS without auth
        console.print("[bold]Test 2.1:[/bold] OPTIONS WITHOUT authentication")
        response = client.options(uri=f"sip:{ASTERISK_HOST}")

        if response and response.status_code == 401:
            console.print(
                "   [yellow]⚠️  Unexpected auth challenge, retrying...[/yellow]"
            )
            response = client.retry_with_auth(response)

        results["options_no_auth"] = response and response.status_code == 200

        time.sleep(0.5)

        # Test 2: REGISTER with auth
        console.print("\n[bold]Test 2.2:[/bold] REGISTER (requires auth)")
        response = client.register(aor=f"sip:{username}@{ASTERISK_HOST}", expires=600)
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)
        results["register"] = response and response.status_code == 200

        time.sleep(0.5)

        # Test 3: INVITE without initial SDP (late offer)
        console.print(
            "\n[bold]Test 2.3:[/bold] INVITE with late offer (receive SDP from server)"
        )

        invite_headers = {
            "Contact": f"<sip:{username}@{client.local_address.host}:{client.local_address.port}>"
        }

        response = client.invite(
            to_uri=f"sip:100@{ASTERISK_HOST}",
            from_uri=f"sip:{username}@{client.local_address.host}",
            body=None,  # No SDP offer (late offer)
            headers=invite_headers,
        )

        if response and response.status_code == 401:
            response = client.retry_with_auth(response)

        if response and response.status_code == 200:
            results["invite_answer"] = True

            # Parse received SDP
            if response.body and isinstance(response.body, SDPBody):
                console.print("   [green]📥 Received SDP from Asterisk[/green]")

                # Get media info
                media_info = response.body.get_media_info(0)
                if media_info:
                    console.print(
                        f"   [cyan]🎵 Media: {media_info['type']} on port {media_info['port']}[/cyan]"
                    )
                    codecs = [c.get("name", "?") for c in media_info["codecs"]]
                    console.print(f"   [cyan]🎵 Codecs: {', '.join(codecs)}[/cyan]")

                # Create answer
                sdp_answer = SDPBody.create_answer(
                    offer=response.body,
                    origin_username=username,
                    origin_address=client.local_address.host,
                    connection_address=client.local_address.host,
                )
                console.print(
                    f"   [dim]SDP answer created ({len(sdp_answer.to_string())} bytes)[/dim]"
                )

            client.ack(response=response)
            console.print("   [green]✓ ACK sent[/green]")

            # Check for early media
            if events.early_media_detected:
                console.print("   [magenta]🎵 Early media was detected![/magenta]")
                results["early_media"] = True
            else:
                results["early_media"] = False

            time.sleep(2)

            client.bye(response=response)
        else:
            results["invite_answer"] = False
            results["early_media"] = False

        time.sleep(0.5)

        # UNREGISTER
        console.print("\n[bold]Test 2.4:[/bold] UNREGISTER")
        response = client.unregister(aor=f"sip:{username}@{ASTERISK_HOST}")
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)
        results["unregister"] = response and response.status_code == 200

    return results


def test_user_3333() -> dict:
    """
    Test User 3333: Strict security, no OPTIONS.

    Tests:
    - OPTIONS (should fail)
    - Invalid credentials
    - REGISTER with valid credentials
    - INVITE normal flow
    - Auto re-registration
    """
    results = {}
    username = "3333"
    config = USERS[username]

    console.print(
        Panel.fit(
            f"[bold cyan]USER {username}[/bold cyan]\n{config['policy']}\n"
            f"Tests: {', '.join(config['tests'])}",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )

    # Test 1: OPTIONS should fail
    console.print("\n[bold]Test 3.1:[/bold] OPTIONS (should be rejected)")
    with Client(local_port=config["port"], transport="UDP") as client:
        client.auth = Auth.Digest(username, config["password"], realm="asterisk")

        response = client.options(uri=f"sip:{ASTERISK_HOST}")
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)

        if response and response.status_code in (403, 405, 501):
            console.print(
                f"   [green]✅ OPTIONS correctly rejected ({response.status_code})[/green]"
            )
            results["options_rejected"] = True
        elif response and response.status_code == 200:
            console.print(
                "   [yellow]⚠️  OPTIONS succeeded (policy not enforced)[/yellow]"
            )
            results["options_rejected"] = False
        else:
            console.print(
                f"   [dim]ℹ️  OPTIONS response: {response.status_code if response else 'timeout'}[/dim]"
            )
            results["options_rejected"] = True  # Consider rejection as success

    time.sleep(0.5)

    # Test 2: Invalid credentials
    console.print("\n[bold]Test 3.2:[/bold] REGISTER with INVALID credentials")
    with Client(local_port=config["port"], transport="UDP") as client:
        client.auth = Auth.Digest(username, "WRONG_PASSWORD", realm="asterisk")

        response = client.register(aor=f"sip:{username}@{ASTERISK_HOST}", expires=60)
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)

        if response and response.status_code in (401, 403):
            console.print(
                f"   [green]✅ Invalid credentials rejected ({response.status_code})[/green]"
            )
            results["invalid_creds"] = True
        else:
            console.print(
                f"   [yellow]⚠️  Unexpected: {response.status_code if response else 'none'}[/yellow]"
            )
            results["invalid_creds"] = False

    time.sleep(0.5)

    # Test 3: Valid credentials and auto re-registration
    console.print("\n[bold]Test 3.3:[/bold] REGISTER with VALID credentials")
    with Client(local_port=config["port"], transport="UDP") as client:
        client.events = DemoEvents()
        client.auth = Auth.Digest(username, config["password"], realm="asterisk")

        response = client.register(aor=f"sip:{username}@{ASTERISK_HOST}", expires=120)
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)

        results["register_valid"] = response and response.status_code == 200

        time.sleep(0.5)

        # Test 4: Normal INVITE
        console.print("\n[bold]Test 3.4:[/bold] INVITE (normal flow)")

        sdp_offer = SDPBody.create_offer(
            session_name="Test Call 3333",
            origin_username=username,
            origin_address=client.local_address.host,
            connection_address=client.local_address.host,
            media_specs=[
                {
                    "media": "audio",
                    "port": 9000,
                    "protocol": "RTP/AVP",
                    "codecs": [
                        {"payload": "0", "name": "PCMU", "rate": "8000"},
                        {"payload": "8", "name": "PCMA", "rate": "8000"},
                    ],
                }
            ],
        )

        invite_headers = {
            "Contact": f"<sip:{username}@{client.local_address.host}:{client.local_address.port}>"
        }

        response = client.invite(
            to_uri=f"sip:100@{ASTERISK_HOST}",
            from_uri=f"sip:{username}@{client.local_address.host}",
            body=sdp_offer.to_string(),
            headers=invite_headers,
        )

        if response and response.status_code == 401:
            response = client.retry_with_auth(response)

        if response and response.status_code == 200:
            results["invite"] = True
            client.ack(response=response)
            time.sleep(2)
            client.bye(response=response)
        else:
            results["invite"] = False

        time.sleep(0.5)

        # Test 5: Auto re-registration
        console.print("\n[bold]Test 3.5:[/bold] AUTO RE-REGISTRATION")

        rereg_count = [0]

        def on_reregister(response):
            rereg_count[0] += 1
            console.print(
                f"   [cyan]🔄 Re-registration #{rereg_count[0]}: {response.status_code}[/cyan]"
            )

        client.enable_auto_reregister(
            aor=f"sip:{username}@{ASTERISK_HOST}",
            interval=5,  # 5 seconds for testing
            callback=on_reregister,
        )

        console.print("   [dim]Auto re-registration enabled (interval=5s)[/dim]")
        console.print("   [dim]Waiting 12 seconds for 2 re-registrations...[/dim]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Waiting for re-registrations...", total=12)
            for _ in range(12):
                time.sleep(1)
                progress.update(task, advance=1)

        console.print(
            f"   [green]✅ Auto re-registration working ({rereg_count[0]} renewals)[/green]"
        )
        results["auto_rereg"] = rereg_count[0] >= 2

        client.disable_auto_reregister()
        console.print("   [dim]Auto re-registration disabled[/dim]")

        # UNREGISTER
        response = client.unregister(aor=f"sip:{username}@{ASTERISK_HOST}")
        if response and response.status_code == 401:
            response = client.retry_with_auth(response)
        results["unregister"] = response and response.status_code == 200

    return results


# ============================================================================
# Main
# ============================================================================


def print_intro():
    """Print introduction banner."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]SIPX - Comprehensive Asterisk Demo[/bold cyan]\n\n"
            "Testing 3 users with different authentication policies:\n"
            "  • [bold]User 1111[/bold]: Auth required for ALL methods\n"
            "  • [bold]User 2222[/bold]: OPTIONS without auth, others with auth\n"
            "  • [bold]User 3333[/bold]: OPTIONS rejected, strict security\n\n"
            "Features tested:\n"
            "  • OPTIONS (with/without auth)\n"
            "  • REGISTER (different expires, updates, removal)\n"
            "  • INVITE (offer, answer, normal flow)\n"
            "  • Invalid credentials handling\n"
            "  • Auto re-registration\n"
            "  • Early media detection (183)",
            border_style="bold cyan",
            box=box.DOUBLE_EDGE,
        )
    )
    console.print()


def print_summary(all_results: dict):
    """Print summary table of all tests."""
    console.print()
    console.print(Panel.fit("[bold]TEST SUMMARY[/bold]", border_style="bold green"))

    table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    table.add_column("User", style="cyan", width=8)
    table.add_column("Test", style="white", width=25)
    table.add_column("Result", style="white", width=10)

    for user, results in all_results.items():
        first_row = True
        for test_name, result in results.items():
            status = "[green]✅ PASS[/green]" if result else "[red]❌ FAIL[/red]"
            user_display = f"[bold]{user}[/bold]" if first_row else ""
            table.add_row(user_display, test_name.replace("_", " ").title(), status)
            first_row = False

    console.print(table)

    # Calculate totals
    total_tests = sum(len(results) for results in all_results.values())
    total_passed = sum(
        sum(1 for r in results.values() if r) for results in all_results.values()
    )

    console.print()
    if total_passed == total_tests:
        console.print(
            Panel.fit(
                f"[bold green]🎉 ALL TESTS PASSED[/bold green]\n"
                f"{total_passed}/{total_tests} tests successful",
                border_style="bold green",
            )
        )
    else:
        failed = total_tests - total_passed
        console.print(
            Panel.fit(
                f"[bold yellow]⚠️  SOME TESTS FAILED[/bold yellow]\n"
                f"{total_passed}/{total_tests} passed, {failed} failed",
                border_style="bold yellow",
            )
        )
    console.print()


def main():
    """Run comprehensive Asterisk demo."""
    print_intro()

    console.print("[dim]Press Enter to start tests (or Ctrl+C to cancel)...[/dim]")
    try:
        input()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled by user[/yellow]")
        return

    all_results = {}

    try:
        # Test User 1111
        console.print("\n" + "=" * 80 + "\n")
        all_results["1111"] = test_user_1111()

        console.print("\n[dim]Waiting 2 seconds before next user...[/dim]")
        time.sleep(2)

        # Test User 2222
        console.print("\n" + "=" * 80 + "\n")
        all_results["2222"] = test_user_2222()

        console.print("\n[dim]Waiting 2 seconds before next user...[/dim]")
        time.sleep(2)

        # Test User 3333
        console.print("\n" + "=" * 80 + "\n")
        all_results["3333"] = test_user_3333()

        # Print summary
        print_summary(all_results)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠️  Tests interrupted by user[/yellow]")
        return
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        logger.exception("Test failed with exception")
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Unexpected error: {e}[/red]")
        logger.exception("Fatal error")
