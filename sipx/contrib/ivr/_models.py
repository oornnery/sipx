"""IVR data structures — shared between sync and async."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Prompt:
    """A prompt to play to the caller."""

    text: str = ""
    audio_file: Optional[str] = None
    timeout: float = 5.0


@dataclass
class MenuItem:
    """A single option in an IVR menu, activated by a DTMF digit."""

    digit: str = ""
    prompt: Prompt = field(default_factory=Prompt)
    handler: Optional[Callable[[], None]] = None
    submenu: Optional[Menu] = None


class Menu:
    """An IVR menu with greeting, items, and retry logic."""

    def __init__(
        self,
        greeting: Prompt,
        items: Optional[list[MenuItem]] = None,
        invalid_prompt: Optional[Prompt] = None,
        max_retries: int = 3,
    ) -> None:
        self.greeting = greeting
        self.items: list[MenuItem] = list(items) if items else []
        self.invalid_prompt = invalid_prompt or Prompt(
            text="Invalid selection. Please try again."
        )
        self.max_retries = max_retries
        self._item_map: dict[str, MenuItem] = {item.digit: item for item in self.items}

    def add_item(
        self,
        digit: str,
        prompt: Prompt,
        handler: Optional[Callable] = None,
        submenu: Optional[Menu] = None,
    ) -> None:
        item = MenuItem(digit=digit, prompt=prompt, handler=handler, submenu=submenu)
        self.items.append(item)
        self._item_map[digit] = item
