"""Tests for SIP-I/ISUP interworking and IVR builder."""

from __future__ import annotations

from sipx.contrib._ivr import Menu, MenuItem, Prompt
from sipx.contrib._sipi import SipI
from sipx._models._message import Request


class TestSipI:
    def test_isup_to_sip_known(self):
        assert SipI.isup_to_sip(17) == 486

    def test_isup_to_sip_unknown(self):
        assert SipI.isup_to_sip(999) == 500

    def test_sip_to_isup_known(self):
        assert SipI.sip_to_isup(486) == 17

    def test_sip_to_isup_unknown(self):
        assert SipI.sip_to_isup(999) == 127

    def test_add_pai(self):
        req = Request("INVITE", "sip:bob@example.com")
        SipI.add_pai(req, "sip:alice@example.com")
        assert req.headers["P-Asserted-Identity"] == "sip:alice@example.com"

    def test_get_pai(self):
        req = Request("INVITE", "sip:bob@example.com")
        SipI.add_pai(req, "tel:+15551234567")
        assert SipI.get_pai(req) == "tel:+15551234567"

    def test_get_pai_missing(self):
        req = Request("INVITE", "sip:bob@example.com")
        assert SipI.get_pai(req) is None

    def test_add_charging_vector_with_orig_ioi(self):
        req = Request("INVITE", "sip:bob@example.com")
        SipI.add_charging_vector(req, icid="abc123", orig_ioi="operator.com")
        value = req.headers["P-Charging-Vector"]
        assert "icid-value=abc123" in value
        assert "orig-ioi=operator.com" in value

    def test_add_charging_vector_without_ioi(self):
        req = Request("INVITE", "sip:bob@example.com")
        SipI.add_charging_vector(req, icid="xyz")
        assert req.headers["P-Charging-Vector"] == "icid-value=xyz"


class TestIVR:
    def test_menu_creation(self):
        greeting = Prompt(text="Welcome")
        menu = Menu(greeting=greeting)
        assert menu.greeting.text == "Welcome"
        assert menu.items == []

    def test_menu_add_item(self):
        menu = Menu(greeting=Prompt(text="Hello"))
        menu.add_item("1", Prompt(text="Option 1"))
        assert len(menu.items) == 1
        assert menu.items[0].digit == "1"
        assert menu._item_map["1"].digit == "1"

    def test_prompt_text_field(self):
        p = Prompt(text="Press 1 for sales")
        assert p.text == "Press 1 for sales"

    def test_menu_item_fields(self):
        def handler():
            pass
        item = MenuItem(digit="5", prompt=Prompt(text="Five"), handler=handler)
        assert item.digit == "5"
        assert item.prompt.text == "Five"
        assert item.handler is handler

    def test_menu_with_items(self):
        items = [
            MenuItem(digit="1", prompt=Prompt(text="One")),
            MenuItem(digit="2", prompt=Prompt(text="Two")),
        ]
        menu = Menu(greeting=Prompt(text="Menu"), items=items)
        assert len(menu.items) == 2
        assert "1" in menu._item_map
        assert "2" in menu._item_map
