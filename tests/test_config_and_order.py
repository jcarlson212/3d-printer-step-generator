"""Tests for registry resolution and order validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from printforge.core.order import OrderInfo, ShippingAddress
from printforge.core.registry import resolve_machine_material


def _addr() -> ShippingAddress:
    return ShippingAddress(line1="1 Test St", city="Townsville", postal_code="12345")


def test_resolve_defaults_to_bambu_pla():
    machine, material = resolve_machine_material()
    assert machine.key == "bambu_a1_mini"
    assert material.key == "bambu_pla_basic"


def test_resolve_unknown_machine_raises():
    with pytest.raises(KeyError):
        resolve_machine_material("no_such_machine")


def test_resolve_unsupported_material_raises():
    with pytest.raises(ValueError):
        resolve_machine_material("bambu_a1_mini", "exotic_resin")


def test_order_requires_valid_email():
    with pytest.raises(ValidationError):
        OrderInfo(first_name="A", last_name="B", email="nope", shipping_address=_addr())


def test_order_auto_id_and_summary():
    o = OrderInfo(
        first_name="Ada", last_name="Lovelace", email="ada@example.com",
        shipping_address=_addr(), notes="framed piece",
    )
    assert o.order_id.startswith("GC-")
    assert o.customer_name == "Ada Lovelace"
    joined = "\n".join(o.summary_lines())
    assert "ada@example.com" in joined
    assert "framed piece" in joined


def test_address_postal_must_have_alnum():
    with pytest.raises(ValidationError):
        ShippingAddress(line1="1 Test St", city="X", postal_code="---")


def test_stripe_link_must_be_url():
    with pytest.raises(ValidationError):
        OrderInfo(
            first_name="A", last_name="B", email="a@b.com",
            shipping_address=_addr(), stripe_payment_link="not-a-url",
        )
