"""Graduated floor defence (user 2026-08-23: '80% deployed, BUT make sure the
floor is held strong'). At halt_buys (<= 160k) the sleeve doesn't just stop
buying — it halves every target so SELL tickets actively cut exposure well
before the 155k liquidation line.
  targets {TDEX .25, MSFT01 .11} x 0.5 -> {TDEX .125, MSFT01 .055}; zeros stay zero.
"""
from src.paperbot.sizing import scale_targets


def test_scale_targets_halves_every_weight():
    out = scale_targets({"TDEX.BK": 0.25, "MSFT01.BK": 0.11, "CRM01.BK": 0.0}, 0.5)
    assert out == {"TDEX.BK": 0.125, "MSFT01.BK": 0.055, "CRM01.BK": 0.0}


def test_scale_targets_does_not_mutate_input():
    src = {"TDEX.BK": 0.25}
    scale_targets(src, 0.5)
    assert src == {"TDEX.BK": 0.25}
