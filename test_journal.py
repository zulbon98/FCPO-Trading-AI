import json
import tempfile
import unittest
from pathlib import Path
from journal import CONFIG_FIELDS, closed_trades, load_events, summarize


def exit_event(event_id="example:exit", side="LONG", entry=4000, exit_price=4010, fees=20, risk=170):
    gross = (exit_price - entry) * 25 * (1 if side == "LONG" else -1)
    return {
        "schema": 1, "mode": "SIMULATION", "event": "exit",
        "event_id": event_id, "run_id": "SYNTHETIC-TEST",
        "version": "FIXTURE", "symbol": "MYX:FCPO-EXAMPLE",
        "plan_id": event_id.split(":")[0], "entry_ms": 1000, "exit_ms": 2000,
        "side": side, "qty": 1, "entry_price": entry, "exit_price": exit_price,
        "gross_myr": gross, "fees_myr": fees, "net_myr": gross - fees,
        "planned_r_myr": risk, "net_r": (gross - fees) / risk, "emitted_ms": 3000,
    }


class JournalTests(unittest.TestCase):
    def test_identical_delivery_is_counted_once(self):
        a = exit_event()
        b = dict(a, emitted_ms=5000)
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "events.jsonl"
            file.write_text(json.dumps(a) + "\n" + json.dumps(b), encoding="utf-8")
            events, duplicates = load_events([file])
        self.assertEqual((len(events), duplicates), (1, 1))

    def test_changed_payload_with_same_id_is_rejected(self):
        a, b = exit_event(), exit_event(exit_price=4009)
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "events.jsonl"
            file.write_text(json.dumps(a) + "\n" + json.dumps(b), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
                load_events([file])

    def test_short_pnl_has_correct_sign_and_costs(self):
        rows = closed_trades([exit_event(side="SHORT", exit_price=3990)])
        self.assertEqual(rows[0]["net_myr"], 230)
        self.assertAlmostEqual(rows[0]["net_r"], 230 / 170)

    def test_double_cost_deduction_is_caught(self):
        event = exit_event()
        event["net_myr"] -= event["fees_myr"]
        with self.assertRaisesRegex(ValueError, "does not reconcile"):
            closed_trades([event])

    def test_wrong_tick_value_is_caught(self):
        event = exit_event()
        event.update(gross_myr=10, net_myr=-10)
        with self.assertRaisesRegex(ValueError, "tick-value"):
            closed_trades([event])

    def test_wrong_r_multiple_is_caught(self):
        event = exit_event()
        event["net_r"] = 99
        with self.assertRaisesRegex(ValueError, "R multiple"):
            closed_trades([event])

    def test_nonfinite_number_is_rejected(self):
        event = exit_event()
        event["net_myr"] = float("inf")
        with self.assertRaisesRegex(ValueError, "finite"):
            closed_trades([event])

    def test_drawdown_counts_losses_from_zero(self):
        a = exit_event("a:exit", exit_price=3996)  # -120
        b = exit_event("b:exit", exit_price=4008)  # +180
        c = exit_event("c:exit", exit_price=3995)  # -145
        report = summarize(closed_trades([a, b, c]))[0]
        self.assertEqual(report["closed_trade_drawdown_myr"], 145)
        self.assertEqual(report["net_myr"], -85)
        self.assertAlmostEqual(report["profit_factor"], 180 / 265)

    def test_versions_are_not_pooled(self):
        a = exit_event("a:exit")
        b = exit_event("b:exit")
        b["version"] = "FIXTURE-2"
        self.assertEqual(len(summarize(closed_trades([a, b]))), 2)

    def test_real_mode_file_is_not_accepted(self):
        event = exit_event()
        event["mode"] = "REAL"
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "events.jsonl"
            file.write_text(json.dumps(event), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SIMULATION"):
                load_events([file])

    def test_changed_configuration_is_not_pooled(self):
        a, b = exit_event("a:exit"), exit_event("b:exit")
        for event in (a, b):
            event.update({key: 1 for key in CONFIG_FIELDS})
        b["risk_pct"] = 2
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "events.jsonl"
            file.write_text(json.dumps(a) + "\n" + json.dumps(b), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "configuration changed"):
                load_events([file])


if __name__ == "__main__":
    unittest.main()
