"""Customer + order information attached to every generation request.

These fields travel with the request so the final delivery email can identify the
order, and so fulfilment has everything it needs. Email is validated; the shipping
address gets a light sanity check (required fields present, plausible postal code).
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field, field_validator


def _new_order_id() -> str:
    return f"GC-{uuid.uuid4().hex[:10].upper()}"


class ShippingMethod(StrEnum):
    STANDARD = "standard"
    EXPEDITED = "expedited"
    OVERNIGHT = "overnight"


class ShippingAddress(BaseModel):
    """Postal address with a basic validity check (not full carrier validation)."""

    line1: str = Field(min_length=3)
    line2: str | None = None
    city: str = Field(min_length=1)
    state_province: str | None = Field(
        default=None, description="State/province/region; optional for some countries."
    )
    postal_code: str = Field(min_length=3, max_length=12)
    country: str = Field(default="US", min_length=2, description="ISO country name or code.")

    @field_validator("postal_code")
    @classmethod
    def _postal_has_alnum(cls, v: str) -> str:
        if not any(c.isalnum() for c in v):
            raise ValueError("postal_code must contain letters or digits")
        return v.strip()

    def one_line(self) -> str:
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        loc = ", ".join(p for p in [self.city, self.state_province] if p)
        parts.append(f"{loc} {self.postal_code}".strip())
        parts.append(self.country)
        return ", ".join(parts)


class OrderInfo(BaseModel):
    """Everything needed to identify and fulfil an order."""

    # Auto-generated reference so every run/email is traceable.
    order_id: str = Field(default_factory=_new_order_id)

    # Required customer identity.
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: EmailStr
    shipping_address: ShippingAddress

    # Optional but commonly needed.
    phone: str | None = None
    quantity: int = Field(default=1, ge=1, description="Number of this piece to print.")
    stripe_payment_link: str | None = Field(
        default=None, description="Optional Stripe payment/checkout link."
    )
    deadline: str | None = Field(
        default=None, description="Optional requested-by date (free text or ISO date)."
    )
    shipping_method: ShippingMethod = Field(default=ShippingMethod.STANDARD)
    filament_shade: str | None = Field(
        default=None,
        description="Specific filament shade beyond piece color, e.g. 'marble white', "
        "'matte black' (informs the theme/look).",
    )
    engraving_message: str | None = Field(
        default=None, description="Optional personalization to engrave on the base / gift note."
    )
    marketing_opt_in: bool = Field(
        default=False, description="Customer consents to future marketing emails."
    )
    notes: str | None = None

    @field_validator("stripe_payment_link")
    @classmethod
    def _stripe_link_plausible(cls, v: str | None) -> str | None:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("stripe_payment_link must be a URL (http/https)")
        return v

    @property
    def customer_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def summary_lines(self) -> list[str]:
        """Human-readable order block for the delivery email / CLI confirmation."""
        lines = [
            f"Order:     {self.order_id}",
            f"Customer:  {self.customer_name} <{self.email}>",
            f"Ship to:   {self.shipping_address.one_line()}",
            f"Quantity:  {self.quantity}",
        ]
        if self.phone:
            lines.append(f"Phone:     {self.phone}")
        lines.append(f"Shipping:  {self.shipping_method.value}")
        if self.deadline:
            lines.append(f"Deadline:  {self.deadline}")
        if self.filament_shade:
            lines.append(f"Shade:     {self.filament_shade}")
        if self.engraving_message:
            lines.append(f"Engraving: {self.engraving_message}")
        if self.stripe_payment_link:
            lines.append(f"Payment:   {self.stripe_payment_link}")
        lines.append(f"Marketing: {'opted in' if self.marketing_opt_in else 'no'}")
        if self.notes:
            lines.append(f"Notes:     {self.notes}")
        return lines
