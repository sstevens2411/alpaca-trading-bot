"""
Alpaca broker client — paper trading only.

Raises RuntimeError immediately if the resolved base URL is not the
Alpaca paper-trading endpoint, so live credentials can never be used.
"""

import os

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://api.alpaca.markets"


def _load_keys() -> tuple[str, str]:
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not secret_key:
        raise EnvironmentError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in the environment."
        )
    return api_key, secret_key


def get_trading_client() -> TradingClient:
    """Return a TradingClient wired to the paper endpoint. Refuses live."""
    api_key, secret_key = _load_keys()
    client = TradingClient(api_key, secret_key, paper=True)

    # Defensive check: inspect the resolved base URL.
    resolved = getattr(client._base_url, "_url", str(client._base_url))
    if LIVE_BASE_URL in str(resolved):
        raise RuntimeError(
            "Live trading endpoint detected. This bot only supports paper trading. "
            "Aborting to protect your capital."
        )
    return client


def get_data_client() -> StockHistoricalDataClient:
    api_key, secret_key = _load_keys()
    return StockHistoricalDataClient(api_key, secret_key)


def place_market_order(
    client: TradingClient,
    symbol: str,
    notional: float,
    side: str,
) -> dict:
    """
    Place a notional market order (buy/sell by dollar amount).

    Returns the order object as a dict with at least:
      id, symbol, side, status
    """
    order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
    request = MarketOrderRequest(
        symbol=symbol,
        notional=round(notional, 2),
        side=order_side,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(request)
    return {
        "id": str(order.id),
        "symbol": order.symbol,
        "side": order.side.value,
        "status": order.status.value,
        "filled_avg_price": str(order.filled_avg_price or ""),
    }


def get_positions(client: TradingClient) -> dict[str, float]:
    """Return {symbol: market_value} for all open positions."""
    positions = client.get_all_positions()
    return {p.symbol: float(p.market_value) for p in positions}


def fetch_bars(
    data_client: StockHistoricalDataClient,
    symbols: list[str],
    start,
    end,
) -> "pandas.DataFrame":
    """Fetch daily bars for *symbols* between *start* and *end* (date objects)."""
    from datetime import datetime, timezone

    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, tzinfo=timezone.utc)

    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start_dt,
        end=end_dt,
    )
    bars = data_client.get_stock_bars(request)
    return bars.df
