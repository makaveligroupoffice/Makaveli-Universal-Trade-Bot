from __future__ import annotations

import json
import os
from config import Config


class BotStateStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    @staticmethod
    def default_state() -> dict:
        return {
            "positions": {},  # symbol -> {entry_price, high_since_entry, side}
            "pending_orders": {},  # order_id -> {symbol, side, submitted_at}
            "last_order_statuses": {}, # order_id -> status
            "dynamic_config": {
                "stop_loss_pct": Config.STOP_LOSS_PCT,
                "take_profit_pct": Config.TAKE_PROFIT_PCT,
                "max_spread_pct": Config.MAX_SPREAD_PCT
            }
        }

    def load(self) -> dict:
        if not os.path.exists(self.path):
            return self.default_state()

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return self.default_state()

        state = self.default_state()
        state.update(data)
        # Handle migration from old flat state if needed
        if "active_symbol" in data and data["active_symbol"]:
            symbol = data["active_symbol"]
            state["positions"][symbol] = {
                "entry_price": data.get("entry_price"),
                "high_since_entry": data.get("high_since_entry"),
                "side": "buy" # assume old state was buy-only
            }
        if "pending_order_id" in data and data["pending_order_id"]:
            oid = data["pending_order_id"]
            state["pending_orders"][oid] = {
                "symbol": symbol,
                "side": data.get("pending_order_side"),
                "submitted_at": data.get("pending_order_submitted_at")
            }
        return state

    def save(self, state: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)