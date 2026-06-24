"""Tests for request scoping, overrides, prompt building, and delivery."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from printforge.core.delivery import Attachment, DeliveryConfig, DeliveryMethod, deliver
from printforge.core.order import OrderInfo, ShippingAddress
from printforge.workflows.chess.models import ChessWorkflowRequest, PieceDimensions
from printforge.workflows.chess.pieces import Color, PieceType
from printforge.workflows.chess.templates import get_template


def _order() -> OrderInfo:
    return OrderInfo(
        first_name="Ada", last_name="Lovelace", email="ada@example.com",
        shipping_address=ShippingAddress(line1="1 Test St", city="X", postal_code="12345"),
    )


def _req(**kw) -> ChessWorkflowRequest:
    base = dict(order=_order(), colors=[Color.WHITE], pieces=[PieceType.KNIGHT])
    base.update(kw)
    return ChessWorkflowRequest(**base)


def test_rejects_disabled_piece():
    with pytest.raises(ValidationError):
        _req(pieces=[PieceType.QUEEN])


def test_both_colors_expand_to_work_units():
    req = _req(colors=[Color.WHITE, Color.BLACK])
    units = req.work_units()
    assert (Color.WHITE, PieceType.KNIGHT) in units
    assert (Color.BLACK, PieceType.KNIGHT) in units
    assert len(units) == 2


def test_colors_deduped():
    req = _req(colors=[Color.WHITE, Color.WHITE])
    assert req.colors == [Color.WHITE]


def test_target_defaults_to_standard_then_override():
    req = _req()
    assert req.target_for(PieceType.KNIGHT).height_mm == 60.0  # standard Staunton
    req2 = _req(dimensions=PieceDimensions(height_mm=80.0))
    assert req2.target_for(PieceType.KNIGHT).height_mm == 80.0
    # width still standard since not overridden
    assert req2.target_for(PieceType.KNIGHT).max_footprint_mm == 33.0


def test_gotchas_override_replaces_defaults():
    custom = ["only this one"]
    req = _req(gotcha_overrides={"knight": custom})
    assert req.gotchas_for(PieceType.KNIGHT) == custom
    # default (no override) returns the template defaults
    assert len(_req().gotchas_for(PieceType.KNIGHT)) >= 4


def test_preferred_material_selects_primary_and_validates():
    req = _req()
    assert req.material_key == "bambu_pla_basic"
    with pytest.raises(ValidationError):
        _req(preferred_materials=["unsupported_material"])


def test_prompt_includes_machine_material_gotchas_and_theme():
    req = _req(theme="weathered marble")
    from printforge.core.registry import resolve_machine_material

    machine, material = resolve_machine_material(req.machine_key, req.material_key)
    template = get_template(PieceType.KNIGHT)
    prompt = template.user_prompt(
        machine=machine, material=material, color="white",
        theme=req.theme, target=req.target_for(PieceType.KNIGHT),
        gotchas=req.gotchas_for(PieceType.KNIGHT), prior=None,
    )
    assert "Bambu Lab A1 mini" in prompt
    assert "Bambu PLA Basic" in prompt
    assert "weathered marble" in prompt
    assert "reinforce" in prompt.lower()  # knight neck gotcha
    assert "result" in template.system_prompt().lower()


def test_delivery_save_to_disk(tmp_path):
    cfg = DeliveryConfig(method=DeliveryMethod.SAVE, save_dir=str(tmp_path))
    res = deliver(
        cfg,
        subject="Order GC-TEST",
        body="explanation body",
        attachments=[Attachment(filename="white_knight.step", content=b"ISO-10303-21;")],
    )
    assert res.method is DeliveryMethod.SAVE
    assert (tmp_path / "white_knight.step").exists()
    txt = list(tmp_path.glob("*.txt"))
    assert txt and "explanation body" in txt[0].read_text()
