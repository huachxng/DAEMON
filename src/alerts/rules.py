"""Individual alert rules as pure functions. Bilingual by construction:
every alert carries both msg_en and msg_th so delivery never has to translate.
"""
from dataclasses import dataclass


@dataclass
class Alert:
    rule_id: str
    severity: str  # 'urgent' or 'info'
    msg_en: str
    msg_th: str


# Thai name for each book, so a message never mislabels whose money is at risk.
# 'live' is the daemon's REAL-money sleeve (the user executes every ticket), so
# calling it a paper book — as this file used to for anything that wasn't 'real' —
# would be actively misleading.
BOOK_TH = {
    "real": "พอร์ตจริง",           # user's own BLS positions (report-only)
    "live": "พอร์ตไลฟ์ (เงินจริง)",  # daemon's real-money sleeve
    "paper": "พอร์ตจำลอง",         # simulated book
}


def check_concentration(weights: dict, threshold_pct: float, book: str,
                        benchmark: str = None,
                        benchmark_limit_pct: float = None) -> list:
    """Fire when a position is a bigger slice of the book than it should be.

    weights: {ticker: percent of book equity}, e.g. {"TDEX.BK": 44.9}.
    benchmark / benchmark_limit_pct: the benchmark ETF is held at a DESIGNED
    sleeve weight (TDEX.BK is the whole Thai sleeve), so it is judged against
    its own, higher ceiling instead of the ordinary per-name cap. Leave both
    None and every name is judged against threshold_pct.
    """
    alerts = []
    book_th = BOOK_TH.get(book, book)
    for ticker, weight in weights.items():
        # Which ceiling applies to THIS name?
        is_benchmark = benchmark is not None and ticker == benchmark and \
            benchmark_limit_pct is not None
        limit = benchmark_limit_pct if is_benchmark else threshold_pct
        if weight <= limit:
            continue
        name = ticker.replace(".BK", "")
        # Say WHY the limit is what it is, so an urgent push is self-explaining.
        why_en = " = designed sleeve + tolerance" if is_benchmark else ""
        why_th = " = น้ำหนักที่ออกแบบไว้ + ส่วนเผื่อ" if is_benchmark else ""
        alerts.append(Alert(
            "concentration", "urgent",
            f"{name} is {weight:.1f}% of the {book} book "
            f"(limit {limit:.0f}%{why_en})",
            f"{name} คิดเป็น {weight:.1f}% ของ{book_th} "
            f"(เกินเพดาน {limit:.0f}%{why_th})",
        ))
    return alerts


def check_floor(equity: float, warn_at: float, urgent_at: float) -> list:
    if equity <= urgent_at:
        return [Alert(
            "floor_proximity_real", "urgent",
            f"REAL book equity ฿{equity:,.0f} is close to the ฿150,000 cut-loss line "
            f"(urgent threshold ฿{urgent_at:,.0f})",
            f"พอร์ตจริงเหลือ ฿{equity:,.0f} ใกล้เส้นตัดขาดทุน ฿150,000 มาก "
            f"(เกณฑ์เร่งด่วน ฿{urgent_at:,.0f})",
        )]
    if equity <= warn_at:
        return [Alert(
            "floor_proximity_real", "info",
            f"REAL book equity ฿{equity:,.0f} approaching the cut-loss line "
            f"(warning threshold ฿{warn_at:,.0f})",
            f"พอร์ตจริงเหลือ ฿{equity:,.0f} เริ่มเข้าใกล้เส้นตัดขาดทุน "
            f"(เกณฑ์เตือน ฿{warn_at:,.0f})",
        )]
    return []


def check_volume_anomaly(ticker: str, today_volume: float, avg20: float,
                         multiple: float) -> list:
    if avg20 <= 0 or today_volume < multiple * avg20:
        return []
    x = today_volume / avg20
    name = ticker.replace(".BK", "")
    return [Alert(
        "volume_anomaly", "info",
        f"{name} traded {x:.1f}x its 20-day average volume today",
        f"{name} มีปริมาณซื้อขายวันนี้สูงกว่าค่าเฉลี่ย 20 วันถึง {x:.1f} เท่า",
    )]
