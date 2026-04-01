#!/usr/bin/env python3
"""
sipx — Session Timers (RFC 4028) + Subscriptions

Shows session timer configuration and subscription lifecycle.
These are used for keeping calls alive and monitoring presence.

No network required — exercises config models in-memory.
"""

from sipx._utils import console
from sipx.session import SessionTimerConfig


def demo_session_timer():
    """Session timer configuration and lifecycle."""
    console.print("[bold]1. Session Timer (RFC 4028)[/bold]\n")

    # Default config
    config = SessionTimerConfig()
    console.print("  Default config:")
    console.print(f"    interval: {config.interval}s")
    console.print(f"    min_se: {config.min_se}s")
    console.print(f"    refresher: {config.refresher}")
    console.print(f"    method: {config.method}")

    # Custom config
    config = SessionTimerConfig(
        interval=1800,
        min_se=90,
        refresher="uac",
        method="UPDATE",
    )
    console.print("\n  Custom config:")
    console.print(f"    interval: {config.interval}s (30 min)")
    console.print(f"    min_se: {config.min_se}s")
    console.print(f"    refresher: {config.refresher}")

    # Show how it integrates with a call
    console.print("\n  Usage in call flow:")
    console.print("    from sipx.session import SessionTimer, SessionTimerConfig")
    console.print("    config = SessionTimerConfig(interval=1800)")
    console.print("    r = client.invite('sip:bob@x', body=sdp)")
    console.print("    timer = SessionTimer(client, r, config=config)")
    console.print("    timer.start()   # starts refresh loop")
    console.print("    # ... call in progress, timer auto-refreshes ...")
    console.print("    timer.stop()    # stop on BYE")

    console.print("\n  Async variant:")
    console.print("    from sipx.session import AsyncSessionTimer")
    console.print("    timer = AsyncSessionTimer(client, r, config=config)")
    console.print("    await timer.start()")


def demo_subscription():
    """Subscription model lifecycle."""
    console.print("\n[bold]2. Subscription Model[/bold]\n")

    console.print("  Usage pattern:")
    console.print("    from sipx.session import Subscription")
    console.print("    sub = Subscription(client, 'sip:bob@x', event='presence')")
    console.print("    sub.subscribe(expires=3600)")
    console.print("    print(sub.state)        # SubscriptionState.ACTIVE")
    console.print("    print(sub.last_notify)  # last NOTIFY body")
    console.print("    sub.unsubscribe()       # sends Expires: 0")

    console.print("\n  Async variant:")
    console.print("    from sipx.session import AsyncSubscription")
    console.print("    sub = AsyncSubscription(client, 'sip:bob@x', event='presence')")
    console.print("    await sub.subscribe(expires=3600)")
    console.print("    await sub.unsubscribe()")

    console.print("\n  Subscription states:")
    console.print("    INIT -> PENDING -> ACTIVE -> TERMINATED")


def main():
    console.print("[bold]sipx — Session Timers + Subscriptions[/bold]\n")

    demo_session_timer()
    demo_subscription()

    console.print("\n[bold green]Session demo complete.[/bold green]")


if __name__ == "__main__":
    main()
