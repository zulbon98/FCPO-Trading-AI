# Validation status

25 October 2026 — FCPO-MORNING-1.1-DRAFT, default run FCPO-M02

- Python importer: 15 automated tests passed.
- Four added synthetic v1.1 alert interoperability tests cover long/short R
  precision, insufficient precision rejection, contract/version ID separation
  and unexpected-fill records retaining positive reserved risk.
- Python source: parsed successfully.
- Journal CLI: synthetic long/short input produced two CSV rows and ignored one
  duplicate, with the expected P&L totals.
- Journal template: headers only; no performance data.
- Pine strategy: revised and reviewed as a draft; NOT compiled in TradingView.
- TradingView acceptance checks and original server alert: NOT completed.
- Historical performance and live forward-test results: NOT obtained.
- Live brokerage connection: none.

The executable Python tests concern journal integrity and handwritten synthetic
alert messages. They do not execute Pine and are not evidence that the strategy
compiles, matches live execution, or has an edge. The v1.1 TradingView acceptance
cases in START_HERE.md, including invalid settings, expired range attempts,
unexpected fills, partial liquidations and overnight/data gaps, remain pending.
