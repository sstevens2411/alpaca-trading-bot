# Alpaca Paper-Trading Bot

A Python trading bot implementing a 20/50-day SMA crossover strategy on a configurable watchlist of large-cap tickers. Runs **paper trading only** — connecting to the live Alpaca endpoint is blocked at the client level.

---

## Project structure

```
alpaca-trading-bot/
├── config/
│   └── config.yaml          # Watchlist, strategy params, risk limits
├── src/
│   ├── broker.py            # Alpaca client (paper-only guard)
│   ├── strategy.py          # SMA crossover signal logic
│   ├── risk.py              # Daily-loss & exposure checks
│   ├── logger.py            # CSV trade logger
│   └── backtest.py          # Historical backtest engine
├── tests/
│   ├── test_strategy.py
│   └── test_risk.py
├── logs/
│   └── trades.csv           # Created at runtime
├── main.py                  # Entry point
├── requirements.txt
└── .env.example
```

---

## Prerequisites

- Python 3.11+
- An [Alpaca](https://alpaca.markets) account with **paper trading** API keys

---

## Setup

### 1. Clone & create a virtual environment

```bash
git clone <repo-url>
cd alpaca-trading-bot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

```bash
cp .env.example .env
# Edit .env and fill in your paper API key and secret
```

Then export them in your shell (or use a tool like `direnv`):

```bash
export ALPACA_API_KEY="your_paper_key"
export ALPACA_SECRET_KEY="your_paper_secret"
```

### 4. (Optional) Edit `config/config.yaml`

| Key | Default | Description |
|-----|---------|-------------|
| `watchlist` | AAPL, MSFT, GOOGL, AMZN, NVDA | Tickers to trade |
| `strategy.short_window` | 20 | Short SMA period (days) |
| `strategy.long_window` | 50 | Long SMA period (days) |
| `position.size_usd` | 100 | Dollar amount per trade |
| `risk.max_total_exposure_usd` | 500 | Max sum of open position values |
| `risk.max_daily_loss_usd` | 25 | Max loss before halting for the day |

---

## Running the bot

### Live (paper) mode

Runs a trading session immediately on startup, then reschedules at **09:45 AM Eastern** every weekday:

```bash
python main.py --live
```

The bot will:
1. Fetch recent daily bars for each ticker in the watchlist.
2. Compute 20-day and 50-day SMAs.
3. Generate BUY/SELL/HOLD signals based on crossover.
4. Check risk limits before every order.
5. Place notional market orders via Alpaca paper API.
6. Log every decision to `logs/trades.csv`.

Press **Ctrl+C** to stop.

### Backtest mode

Fetches 2 years of daily bars and simulates the strategy from scratch:

```bash
python main.py --backtest
```

Output example:
```
==================================================
  BACKTEST RESULTS
==================================================
  Starting capital : $10,000.00
  Final value      : $11,342.17
  Total return     : +13.42%
  Number of trades : 24
  Max drawdown     : -8.31%
==================================================
```

---

## Running the tests

```bash
pytest tests/ -v
```

The tests cover:
- `test_strategy.py` — SMA computation, crossover detection, edge cases
- `test_risk.py` — exposure limits, daily-loss halting, `DailyRiskManager` state

No network calls are made during tests.

---

## Trade log format

`logs/trades.csv` columns:

| Column | Description |
|--------|-------------|
| `timestamp` | UTC ISO-8601 timestamp |
| `ticker` | Symbol (e.g. `AAPL`) |
| `signal` | `BUY`, `SELL`, `HOLD`, `SKIP`, `BLOCKED`, `ERROR` |
| `order_id` | Alpaca order UUID (empty if no order placed) |
| `fill_price` | Average fill price (empty if pending/not filled) |
| `notes` | Reason for skip/block, order status, or error message |

---

## Safety notes

- The bot will raise `RuntimeError` and refuse to start if the Alpaca client resolves to the **live** endpoint.
- API keys are read from environment variables only — never hard-coded.
- If the daily loss limit or total exposure limit is breached, trading is halted and the reason is logged to CSV.
