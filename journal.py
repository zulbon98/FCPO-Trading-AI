"""Import original TradingView alert JSON lines. Python 3.10+, no dependencies.

This utility only reads local event files and writes a research journal.
It has no network, brokerage, execution, or model API capability.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

EVENTS = {"heartbeat", "armed", "rejected", "entry", "exit", "session_end"}
CONFIG_FIELDS = (
    "risk_pct", "daily_loss_cap_myr", "assumed_fee_per_side_myr", "extra_stop_ticks",
    "max_trades", "entry_cut_h", "entry_cut_m", "flat_h", "flat_m", "max_hold_m",
    "test_start_ms", "test_end_ms", "event_exclusion", "event_start_ms", "event_end_ms",
    "continuous_allowed",
)
FIELDS = [
    "run_id", "version", "symbol", "event_id", "plan_id", "entry_utc", "exit_utc",
    "side", "qty", "entry_price", "exit_price", "stop", "target", "gross_myr",
    "fees_myr", "net_myr", "planned_r_myr", "net_r", "emitted_ms",
]


def finite_number(event: dict, key: str) -> float:
    value = event.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a finite number")
    if not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    return float(value)


def utc_time(milliseconds: int | float) -> str:
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).isoformat()


def load_events(paths: list[Path]) -> tuple[list[dict], int]:
    """Reject conflicting duplicates; do not silently overwrite the first record."""
    by_id: dict[str, tuple[str, dict]] = {}
    by_experiment: dict[tuple, str] = {}
    duplicates = 0
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("each line must be a JSON object")
                if event.get("schema") != 1 or event.get("mode") != "SIMULATION":
                    raise ValueError("expected schema 1 and SIMULATION")
                if event.get("event") not in EVENTS:
                    raise ValueError("unrecognized event type")
                for key in ("run_id", "version", "symbol", "event_id"):
                    if not isinstance(event.get(key), str) or not event[key].strip():
                        raise ValueError(f"{key} is missing")
                if any(key in event for key in CONFIG_FIELDS):
                    if not all(key in event for key in CONFIG_FIELDS):
                        raise ValueError("incomplete experiment configuration")
                    experiment = (event["run_id"], event["version"], event["symbol"])
                    config = json.dumps({key: event[key] for key in CONFIG_FIELDS},
                                        sort_keys=True, allow_nan=False)
                    if experiment in by_experiment and by_experiment[experiment] != config:
                        raise ValueError("configuration changed inside the same experiment")
                    by_experiment[experiment] = config
                # Delivery/emission timestamps may vary on retransmission/restart.
                canonical = {k: v for k, v in event.items() if k != "emitted_ms"}
                digest = hashlib.sha256(
                    json.dumps(canonical, sort_keys=True, allow_nan=False).encode()
                ).hexdigest()
                eid = event["event_id"]
                if eid in by_id:
                    if by_id[eid][0] != digest:
                        raise ValueError(f"conflicting duplicate event_id: {eid}")
                    duplicates += 1
                else:
                    by_id[eid] = (digest, event)
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
    return [item[1] for item in by_id.values()], duplicates


def closed_trades(events: list[dict]) -> list[dict]:
    rows = []
    for event in events:
        if event["event"] != "exit":
            continue
        row = {key: event.get(key, "") for key in FIELDS}
        for key in ("gross_myr", "fees_myr", "net_myr", "planned_r_myr",
                    "entry_ms", "exit_ms", "entry_price", "exit_price", "qty"):
            finite_number(event, key)
        gross, fees, net = (float(event[key]) for key in ("gross_myr", "fees_myr", "net_myr"))
        planned_r = float(event["planned_r_myr"])
        if fees < 0 or planned_r <= 0 or float(event["qty"]) <= 0:
            raise ValueError(f"{event['event_id']}: invalid fees, size, or planned R")
        if event["exit_ms"] < event["entry_ms"]:
            raise ValueError(f"{event['event_id']}: exit precedes entry")
        if event.get("side") not in {"LONG", "SHORT"}:
            raise ValueError(f"{event['event_id']}: invalid side")
        expected_gross = (event["exit_price"] - event["entry_price"]) * event["qty"] * 25
        if event["side"] == "SHORT":
            expected_gross = -expected_gross
        if not math.isclose(gross, expected_gross, abs_tol=0.05):
            raise ValueError(f"{event['event_id']}: FCPO tick-value reconciliation failed")
        if not math.isclose(gross - fees, net, abs_tol=0.05):
            raise ValueError(f"{event['event_id']}: P&L does not reconcile")
        expected_r = net / planned_r
        if event.get("net_r") is not None and not math.isclose(
                finite_number(event, "net_r"), expected_r, abs_tol=0.0001):
            raise ValueError(f"{event['event_id']}: R multiple does not reconcile")
        row["net_r"] = expected_r
        row["entry_utc"] = utc_time(event["entry_ms"])
        row["exit_utc"] = utc_time(event["exit_ms"])
        rows.append(row)
    return sorted(rows, key=lambda r: (r["exit_utc"], r["event_id"]))


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        groups[(row["run_id"], row["version"], row["symbol"])].append(row)
    summaries = []
    for (run, version, symbol), trades in sorted(groups.items()):
        pnls = [float(row["net_myr"]) for row in trades]
        gains = sum(max(0.0, pnl) for pnl in pnls)
        losses = sum(max(0.0, -pnl) for pnl in pnls)
        cumulative = peak = drawdown = 0.0
        for pnl in pnls:
            cumulative += pnl
            peak = max(peak, cumulative)
            drawdown = max(drawdown, peak - cumulative)
        summaries.append({
            "run_id": run, "version": version, "symbol": symbol,
            "closed_trades": len(trades), "net_myr": sum(pnls),
            "win_rate_pct": 100 * sum(pnl > 0 for pnl in pnls) / len(trades),
            "profit_factor": gains / losses if losses else None,
            "expectancy_myr_per_trade": sum(pnls) / len(trades),
            "mean_net_r": sum(float(row["net_r"]) for row in trades) / len(trades),
            "closed_trade_drawdown_myr": drawdown,
            "drawdown_scope": "closed trades only; intratrade drawdown is excluded",
            "sample_note": "a small or single-regime sample does not validate an edge",
        })
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("journal.csv"))
    args = parser.parse_args()
    events, duplicates = load_events(args.events)
    rows = closed_trades(events)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "events": len(events), "duplicates_ignored": duplicates,
        "closed_trades": len(rows), "experiments": summarize(rows),
        "journal": str(args.out.resolve()),
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
