"""Commission models. Rates live in config/settings.yaml, not here."""
from src.config import load_settings


def thai_fee(notional_thb: float, settings: dict | None = None) -> float:
    """BLS Thai equity/DR commission per side (rate UNVERIFIED until user confirms tier)."""
    fees = (settings or load_settings())["fees"]["thai"]
    return max(notional_thb * fees["commission_rate"], fees["min_fee_thb"])


def us_paper_fee(qty: float, settings: dict | None = None) -> float:
    """US paper-book commission model: per-share with a minimum."""
    fees = (settings or load_settings())["fees"]["us_paper"]
    return max(qty * fees["per_share_usd"], fees["min_fee_usd"])
