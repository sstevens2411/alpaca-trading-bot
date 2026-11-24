"""
CSV trade logger.

Columns: timestamp, ticker, signal, order_id, fill_price, notes
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path


COLUMNS = ["timestamp", "ticker", "signal", "order_id", "fill_price", "notes"]


class TradeLogger:
    def __init__(self, csv_path: str):
        self.path = Path(csv_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_header()

    def _ensure_header(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            with open(self.path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                writer.writeheader()

    def log(
        self,
        ticker: str,
        signal: str,
        order_id: str = "",
        fill_price: str = "",
        notes: str = "",
    ) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker,
            "signal": signal,
            "order_id": order_id,
            "fill_price": fill_price,
            "notes": notes,
        }
        with open(self.path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writerow(row)
        print(
            f"[LOG] {row['timestamp']} | {ticker:6s} | {signal:4s} | "
            f"order={order_id or 'n/a':36s} | fill={fill_price or 'n/a'} | {notes}"
        )
