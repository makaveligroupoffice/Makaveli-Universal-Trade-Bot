from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


class TradeJournal:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    @staticmethod
    def _json_safe(value):
        if isinstance(value, dict):
            return {str(k): TradeJournal._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [TradeJournal._json_safe(v) for v in value]
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def record_trade(self, symbol: str, action: str, qty: float, price: float, side: str, pnl: float | None = None, reason: str | None = None, manual: bool = False, context: dict | None = None, tags: list | None = None) -> None:
        payload = {
            "symbol": symbol,
            "action": action,
            "qty": qty,
            "price": price,
            "side": side,
            "pnl": pnl,
            "reason": reason,
            "manual": manual,
            "context": context,
            "tags": tags or [] # Trade memory tagging
        }
        self.record(f"{action}_filled", payload)

    def record(self, event_type: str, payload: dict) -> None:
        row = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            **self._json_safe(payload),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")