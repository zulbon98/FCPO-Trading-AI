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


class PineAlertInteropTests(unittest.TestCase):
    """Handwritten synthetic v1.1 messages; these tests do not execute Pine."""

    def synthetic_exit(self, *, side="LONG", symbol="MYX:FCPO-EXAMPLE",
                       version="FCPO-MORNING-1.1-DRAFT", entry=4000,
                       exit_price=None, unexpected_fill=False):
        if exit_price is None:
            exit_price = 4010 if side == "LONG" else 3990
        event = exit_event(side=side, entry=entry, exit_price=exit_price, risk=195)
        event.update({
            "version": version, "symbol": symbol, "timeframe": "15",
            "risk_pct": 0.5, "daily_loss_cap_myr": 375,
            "assumed_fee_per_side_myr": 10, "extra_stop_ticks": 1,
            "max_trades": 2, "entry_cut_h": 12, "entry_cut_m": 0,
            "flat_h": 12, "flat_m": 15, "max_hold_m": 90,
            "test_start_ms": 0, "test_end_ms": 86400000,
            "event_exclusion": False, "event_start_ms": 45000000,
            "event_end_ms": 46800000, "continuous_allowed": False,
            "stop": 3994 if side == "LONG" else 4006,
            "target": None if unexpected_fill else (4012 if side == "LONG" else 3988),
            "unexpected_fill": unexpected_fill,
        })
        self.assertTrue(set(CONFIG_FIELDS).issubset(event))
        event["plan_id"] = f"{event['run_id']}:{version}:{symbol}:1000"
        event["event_id"] = event["plan_id"] + ":exit:2000:1"
        event["net_r"] = float(f"{event['net_r']:.10f}")
        return event

    def load_synthetic(self, *messages):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "synthetic_alerts.jsonl"
            file.write_text("\n".join(json.dumps(item) for item in messages),
                            encoding="utf-8")
            return load_events([file])

    def test_precise_long_and_short_exit_alerts_reconcile(self):
        for side in ("LONG", "SHORT"):
            with self.subTest(side=side):
                events, duplicates = self.load_synthetic(self.synthetic_exit(side=side))
                rows = closed_trades(events)
                self.assertEqual(duplicates, 0)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["side"], side)
                self.assertEqual(rows[0]["net_myr"], 230)
                self.assertAlmostEqual(rows[0]["net_r"], 230 / 195)

    def test_three_decimal_r_alert_fails_reconciliation(self):
        for side in ("LONG", "SHORT"):
            with self.subTest(side=side):
                event = self.synthetic_exit(side=side)
                event["net_r"] = round(event["net_r"], 3)
                events, _ = self.load_synthetic(event)
                with self.assertRaisesRegex(ValueError, "R multiple"):
                    closed_trades(events)

    def test_scoped_ids_keep_same_timestamp_contracts_and_versions_separate(self):
        messages = [
            self.synthetic_exit(symbol=symbol, version=version)
            for symbol in ("MYX:FCPO-EXAMPLE-A", "MYX:FCPO-EXAMPLE-B")
            for version in ("FCPO-MORNING-1.1-DRAFT", "FCPO-MORNING-1.2-FIXTURE")
        ]
        events, duplicates = self.load_synthetic(*messages)
        self.assertEqual((len(events), duplicates), (4, 0))
        reports = summarize(closed_trades(events))
        self.assertEqual(len(reports), 4)
        self.assertTrue(all(report["closed_trades"] == 1 for report in reports))
        self.assertEqual(
            {(report["symbol"], report["version"]) for report in reports},
            {(message["symbol"], message["version"]) for message in messages},
        )

    def test_unexpected_fill_exit_preserves_importable_reserved_risk(self):
        # A long stop-limit fills below its frozen stop, then exits immediately.
        event = self.synthetic_exit(entry=3990, exit_price=3989, unexpected_fill=True)
        events, duplicates = self.load_synthetic(event)
        rows = closed_trades(events)
        self.assertEqual(duplicates, 0)
        self.assertTrue(events[0]["unexpected_fill"])
        self.assertLess(events[0]["entry_price"], events[0]["stop"])
        self.assertEqual(rows[0]["planned_r_myr"], 195)
        self.assertEqual(rows[0]["net_myr"], -45)
        self.assertAlmostEqual(rows[0]["net_r"], -45 / 195)


if __name__ == "__main__":
    unittest.main()
