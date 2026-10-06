"""The circuit breaker that makes the ฿150,000 floor unreachable by construction.

State ladder (thresholds in config/settings.yaml):
  equity > 160k          -> 'normal'     trade freely
  155k < equity <= 160k  -> 'halt_buys'  no new buys, keep/reduce only
  equity <= 155k         -> 'liquidate'  everything to cash, stop until user review

Because 'liquidate' triggers a full ~5k THB above the hard floor, the paper
book goes to cash before 150k can ever print.
"""


def breaker_state(equity_thb: float, settings: dict) -> str:
    paper = settings["books"]["paper"]
    if equity_thb <= paper["liquidate_below_thb"]:
        return "liquidate"
    if equity_thb <= paper["halt_buys_below_thb"]:
        return "halt_buys"
    return "normal"
