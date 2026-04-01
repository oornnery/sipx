#!/usr/bin/env python3
"""sipx — IVR menu builder example (no network needed)."""

from sipx._utils import console
from sipx.contrib import Menu, MenuItem, Prompt

# Build a menu
menu = Menu(
    greeting=Prompt(
        text="Welcome to sipx. Press 1 for sales, 2 for support, 0 for operator."
    ),
    items=[
        MenuItem(
            digit="1",
            prompt=Prompt(text="Transferring to sales..."),
            handler=lambda: console.print("  -> Sales handler"),
        ),
        MenuItem(
            digit="2",
            prompt=Prompt(text="Connecting to support..."),
            handler=lambda: console.print("  -> Support handler"),
        ),
        MenuItem(
            digit="0",
            prompt=Prompt(text="Please hold for an operator."),
            handler=lambda: console.print("  -> Operator handler"),
        ),
    ],
    invalid_prompt=Prompt(text="Invalid option. Try again."),
    max_retries=2,
)

# Add more items dynamically
menu.add_item(
    "9", Prompt(text="Goodbye!"), handler=lambda: console.print("  -> Goodbye handler")
)

# Inspect
console.print("[bold]IVR Menu Structure[/bold]")
console.print(f"  Greeting: {menu.greeting.text}")
console.print(f"  Items: {len(menu.items)}")
for item in menu.items:
    console.print(f"    [{item.digit}] {item.prompt.text}")
console.print(
    f"  Invalid prompt: {menu.invalid_prompt.text if menu.invalid_prompt else 'None'}"
)
console.print(f"  Max retries: {menu.max_retries}")

# Simulate digit selection
console.print("\n[bold]Simulating digit '1':[/bold]")
for item in menu.items:
    if item.digit == "1":
        console.print(f"  Prompt: {item.prompt.text}")
        if item.handler:
            item.handler()
        break
