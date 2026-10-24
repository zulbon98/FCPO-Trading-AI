# FCPO live forward-test kit

Updated 25 October 2026. v1.1 research draft; not activated in TradingView.

The goal is to freeze a formula, observe its decisions on incoming FCPO data for
several months, and retain the records produced at the time. AI can write the
code and review those records. This does not require AI to click broker buttons.

## Included and outstanding

- FCPO_Morning_v1.pine: Pine v6 draft adapted from sections 5–10 of your
  FCPO_Wyckoff_Study_Guide.pdf.
- experiment_manifest.json: proposed configuration and activation record.
- journal.py: importer for original alert JSON, with CSV and summary output.
- test_journal.py: tests of journal reconciliation, deduplication and statistics.
- journal_template.csv: empty columns; no trading results.

The Pine source has NOT been compiled in your TradingView account. No historical
or live FCPO performance is claimed. Python tests validate the journal utility,
not Pine compilation, order sequencing or profitability. The simulation switch
is off until the acceptance checks are completed.

## v1.1 changes

The revised draft is `FCPO-MORNING-1.1-DRAFT`, with a new default run ID,
`FCPO-M02`. Use a separate sample from v1.0. The range, breakout, retest, H1
direction, one-contract size, 2D target and default risk/time settings remain
the baseline below.

- Setup checks require standard candles, a nonblank run ID, valid date/event
  intervals and entry/flatten times aligned to 15-minute bars. The dashboard
  explains blocked settings, current state, available risk and rejection counts.
- Daily counters reset before the first fill or exit on a new local date.
  Entry cancellation preserves protective exits, and a position carried across
  a date is closed when the script next executes. Only a newly opened position
  increments the entry count; a partial liquidation does not count as an entry.
- An armed order consumes the range's attempt for that morning, including when
  it expires without a fill. The range is recognized by its start or matching
  high/low boundaries.
- An unexpected fill is flagged and immediately closed. Its journal record
  retains the positive risk accepted when armed, rather than deriving an
  invalid risk or target from a fill beyond the structural stop.
- Alert IDs include run, version and contract. Numbers retain up to 10 decimal
  places for R reconciliation; string escaping includes newlines and tabs.
  Completed H1 pivot maps persist through intrabar recalculations.

The local suite currently passes 15 tests, including four new tests using
synthetic v1.1 alert messages. They cover precise long/short R values, rejection
of insufficient R precision, distinct contract/version IDs, and unexpected-fill
records. They do not execute or compile Pine.

## How the unattended run works

A Pine strategy sends hypothetical orders to TradingView's broker emulator.
They appear in its strategy report. Pine cannot directly place those orders into
the separate Trading Panel Paper Trading account.

Create a server alert on the strategy to keep it running without leaving your PC
awake. Save original alert messages outside the recalculable chart report. The
first journal route is alerts sent automatically to your own email; it needs no
broker credentials or public webhook. Retain the messages throughout the trial.

This kit does not connect to Moomoo, Webull or a live brokerage. It does not
install a Windows task, host a webhook, or schedule AI reviews.

## Proposed frozen baseline

| Setting | Baseline |
|---|---|
| Test name | FCPO Morning v1.1 draft; FCPO-M02 |
| Proposed period | 26 October 2026 through 24 January 2027 |
| Timezone | Malaysia, UTC+8 |
| Instrument | Liquid actual FCPO expiry; same contract for price and volume |
| Chart | Standard 15-minute candles; keep available session data consistent |
| Context | Completed H1 data; strict two-bar pivot wings; ties rejected |
| Direction | Two rising highs and lows for longs; falling pairs for shorts |
| Setup | Range, breakout, quiet first retest, directional trigger |
| Entry | Stop-limit; trigger one tick beyond Q; one additional tick allowance |
| Size | One whole contract, only if it fits the risk allowance |
| Stop | Retest extreme plus frozen Z buffer |
| Target | 2 times actual fill-to-stop price distance |
| Entry cutoff | 12:00 |
| Time exit | 12:15, aligned to the 15-minute chart |
| Maximum hold | 90 minutes, checked on completed bars |
| Maximum fills | Two per morning; one armed attempt per range, including expired orders |
| Daily loss allowance | RM375; wins do not replenish the gross-loss allowance |
| Per-trade risk | 0.5% of simulated equity |
| Trial equity | RM20,000 scenario, not your broker's current balance |

These are research settings, not optimized parameters. Change them before
starting if needed; a later rule change creates a new version and sample.

### Formula

1. Inspect the 8–24 completed bars before breakout B and select the longest
   qualifying range. Require two strict confirmed highs near its upper boundary
   and two lows near its lower boundary.
2. Freeze Z at max(2, ceiling(0.10 × prior ATR(14) / tick_size)) ticks.
3. A completed directional B clears the boundary by Z, agrees with H1 direction,
   closes in its outer third, and meets the preceding 20-bar median range and
   volume. Those baselines exclude B.
4. Find Q only on bars 2–4 after B. Require the reaction, boundary touch, permitted
   closes and directional Q described in the guide. Reaction mean range and
   volume exclude Q and must be smaller than B's.
5. Freeze trigger and structural stop. Check worst permitted fill risk and room
   for a 2D target before a known opposing H1 pivot. No opposing level means no
   trade.
6. Pending entries expire after two completed bars, the cutoff, an invalidating
   completed bar or loss of H1 permission. An armed attempt consumes that
   range for the morning even if it expires. Never widen the original stop.

### Adaptations and limitations

- The guide's night window becomes a separate morning experiment. It does not
  validate the night strategy.
- The opposing map contains the latest 50 confirmed H1 highs/lows. Range pivot
  wings must lie completely inside the selected range.
- Entry-cancellation, event and time decisions use bar-close checks. A pending
  stop-limit can fill intrabar before an invalidating close becomes available.
  This cannot reproduce immediate discretionary gap/stop-before-entry
  cancellation. Retain such sequencing cases for review.
- Fill recalculations set the 2D target from the emulator fill. They only manage
  protection and journals; they do not use current OHLC to discover a new entry.
  Historical assumptions can still be optimistic. Check lower-timeframe detail
  and compare original forward alerts with reloaded results.
- Time exits use an immediate emulator market close on a completed-bar check.
  A real order would involve latency and slippage. Maximum hold can exceed
  exactly 90 minutes by up to one chart interval for an intrabar fill while data
  is arriving normally; the session exit takes precedence.
- No automated spread/depth filter, announcement calendar, weekly loss budget,
  holiday feed or broker margin lookup is included. One manually maintained
  event-exclusion interval is available.
- The 10% emulator margin setting is an illustration, not actual FCPO margin.
  The RM10 per-side fee is also a placeholder. Verify actual research inputs.
- There is no validation of liquidity, queue priority, partial fills, actual
  execution or profitability.
- Exceptional partial liquidations retain separate exit records. The losing-exit
  limit and journal statistics count those records separately; inspect them before
  interpreting results as whole-position statistics.

## TradingView setup

1. Open a liquid DATED FCPO contract on standard 15-minute candles. The source
   blocks continuous symbols containing ! unless explicitly allowed.
   MYX:FCPO1! is useful for analysis but needs a documented roll convention.
2. Confirm real-time Bursa data. TradingView lists the free Bursa feed as
   15 minutes delayed; platform plans and exchange data are separate
   entitlements. Verify your account before buying anything. The script cannot
   detect a delayed feed.
3. Keep available session data consistent and load sufficient earlier history
   for H1 pivots. Open Pine Editor, paste FCPO_Morning_v1.pine, save and add it to
   the chart. Retain exact compile/runtime errors, if any.
4. In Inputs AND Properties, set the per-side fee to the same researched value.
   Defaults are illustrative. Record equity, margin, slippage, commissions and
   all inputs. Model slippage is embedded in fill prices: do not subtract it
   again from journal P&L. The extra stop tick is only a planned-risk allowance.
5. Complete the acceptance checks below. For historical inspection, use a separate
   TEST run ID, an earlier start date and enabled simulated orders. Setup backtests
   are not part of the later measured forward sample.
6. Choose a future start date and unique run ID. Turn off smoke-test mode, enable
   simulated orders, and save source/settings plus the manifest.
7. Create a strategy alert for "alert() function calls only" and enable email to
   yourself. The script supplies JSON messages. Verify plan support and the
   alert expiration time; retain/renew alerts throughout the trial.
8. Confirm the first server-produced event arrives. Keep original messages.
   Editing the chart does not update the alert's saved script/input copy.
9. For expiry rollover, confirm the old simulated position is flat, stop its
   alert, and create a new contract segment with its own ID and activation date.
   Record liquidity and the roll reason. Analyze segments separately first.

## Acceptance checks

- Compile the Pine source. Confirm dated FCPO, MYR, tick size 1, point value 25,
  standard candles and 15-minute bars.
- Confirm the dashboard blocks nonstandard candles, blank run IDs, invalid
  date/event intervals and nonaligned entry/flatten times. Restore valid inputs
  before continuing.
- With orders disabled, enable smoke-test mode and create a test alert. Wait for
  a real completed bar and confirm receipt. Stop/delete the test alert afterward.
  Weekends or market holidays do not create new market bars.
- Inspect at least one long, short, failed retest, expired stop-limit, risk
  rejection and no-trade session. Confirm that pivots were available at decision
  time, rather than at their older pivot candle.
- Inspect gaps, a stop and target inside one bar, and a stop touched while entry
  is pending. Use lower-timeframe data where available; flag uncertainty.
- After an armed stop-limit expires, confirm a later setup from the same range
  cannot arm again that morning; check that a different range remains eligible.
- Inspect an unexpected fill beyond the structural stop or permitted limit.
  Confirm the emergency close, `unexpected_fill` flag and positive reserved
  `planned_r_myr`; import the original exit JSON without editing it.
- Inspect a partial liquidation, if the emulator produces one. Confirm it does
  not add an entry or duplicate an entry alert, and that exit IDs remain unique.
- Inspect overnight carry and missing-bar cases. Confirm that the new day's
  first fill/exit affects the new day's counters, existing protection is retained,
  and a carried position is closed at the next script execution. No script can
  submit a close while market updates are absent.
- Confirm stop, 2D target, quantity, no pyramiding/reversal, 12:00 cancellation,
  12:15 exit and final flat status. Confirm no-trade session messages.
- Reconcile a trade as signed price change × 25 × contracts minus fees.
- Import original test alerts from separate contract/version streams sharing a
  timestamp. Confirm unique IDs, separate summary groups and R reconciliation
  at the emitted precision. Check that intrabar fill recalculations retain the
  completed H1 opposing levels used at the decision.
- Compare original forward messages with the report after reload. Investigate
  any changed/deleted trades without overwriting the original evidence.

These checks have NOT been completed by generating the kit. They require your
TradingView account and actual data.

## Journal and AI review

Each event includes its version, run ID, contract and input settings. Events
cover armed orders, rejected setups, entry/exit fills, session end, and optional
test heartbeats. Missing session records need investigation: an exchange holiday,
expired alert, missing data or script error may be responsible.

The initial email route retains alerts automatically in your inbox. Local
import/extraction is optional: put unchanged JSON bodies in events.jsonl,
one event per line, then run with Python 3.10 or newer on Windows:

    py -3 journal.py events.jsonl --out journal.csv

This utility does not fetch email. It rejects conflicting duplicates, changed
inputs within a run and invalid FCPO P&L/R arithmetic. It separates
version/contract groups and preserves the
input. The summary's drawdown covers closed trades only; retain a separate record
of intratrade/open-equity drawdown.

For AI reviews, use the journal, original messages and frozen manifest. Review net
expectancy, profit factor, win rate, average win/loss, drawdown, streaks, count,
missing sessions, costs and risk rejections. Compare direction, contract and
month. Do not let AI silently rewrite the active formula; try suggested changes
as separately labelled versions.

Three months with a few trades or one favourable regime does not establish an
edge. A 2D price target is not net +2R after costs.

At RM20,000, a 0.5% budget is RM100 per trade. FCPO is RM25 per tick before fees,
so many structural stops can fail the budget. Preserve rejection records;
do not shrink stops or silently increase risk merely to generate trades.

## Official sources checked 24 October 2026

- Pine strategies / separate Paper Trading account:
  https://www.tradingview.com/pine-script-docs/faq/strategies/
- Server alerts and saved settings:
  https://www.tradingview.com/pine-script-docs/concepts/alerts/
- Emulator mechanics and fill settings:
  https://www.tradingview.com/pine-script-docs/concepts/strategies/
- Market data: https://www.tradingview.com/data-coverage/
- Alert setup/expiration:
  https://www.tradingview.com/support/solutions/43000595315-how-to-set-up-alerts/
