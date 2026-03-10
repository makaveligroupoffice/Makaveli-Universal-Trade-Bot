from __future__ import annotations

import json
import os
from datetime import datetime
from json import JSONDecodeError

from config import Config


class RiskManager:
    def __init__(self):
        self.state_file = Config.RISK_STATE_FILE
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        self.state = self._load_state()
        self._roll_day_if_needed()

    @staticmethod
    def _today_str() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _default_state(self) -> dict:
        return {
            "date": self._today_str(),
            "trades_today": 0,
            "seen_alert_ids": [],
            "daily_pnl": 0.0,
        }

    def _load_state(self) -> dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, JSONDecodeError, TypeError, ValueError):
                return self._default_state()
        return self._default_state()

    def _save_state(self) -> None:
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def _roll_day_if_needed(self) -> None:
        if self.state.get("date") != self._today_str():
            self.state = self._default_state()
            self._save_state()

    @staticmethod
    def _within_hours() -> bool:
        now = int(datetime.now().strftime("%H%M"))
        start = int(Config.ALLOWED_START_HHMM)
        end = int(Config.ALLOWED_END_HHMM)
        return start <= now <= end

    def seen_alert(self, alert_id: str | None) -> bool:
        """
        Returns True if alert_id was already processed today.
        """
        self._roll_day_if_needed()

        if not alert_id:
            return False

        seen = set(self.state.get("seen_alert_ids", []))
        if str(alert_id) in seen:
            return True

        return False

    def mark_alert_seen(self, alert_id: str | None) -> None:
        """
        Marks alert_id as processed today.
        """
        self._roll_day_if_needed()

        if not alert_id:
            return

        seen = set(self.state.get("seen_alert_ids", []))
        seen.add(str(alert_id))
        self.state["seen_alert_ids"] = list(seen)
        self._save_state()

    def record_trade(self, pnl_change: float = 0.0) -> None:
        self._roll_day_if_needed()
        # Increment trade count for any trade (entry or exit)
        self.state["trades_today"] = int(self.state.get("trades_today", 0)) + 1
        # Accumulate PnL
        self.state["daily_pnl"] = float(self.state.get("daily_pnl", 0.0)) + float(pnl_change)
        self._save_state()

    def get_daily_summary(self) -> dict:
        self._roll_day_if_needed()
        return {
            "daily_pnl": float(self.state.get("daily_pnl", 0.0)),
            "trades_count": int(self.state.get("trades_today", 0))
        }

    def can_trade(self, is_exit: bool = False, current_hhmm: int | None = None) -> bool:
        """
        Exit/sell trades should still be allowed even when risk blocks new buys.
        """
        self._roll_day_if_needed()

        if is_exit:
            return True

        # Use provided hhmm (from market clock) or fall back to local machine time
        now = current_hhmm if current_hhmm is not None else int(datetime.now().strftime("%H%M"))
        start = int(Config.ALLOWED_START_HHMM)
        end = int(Config.ALLOWED_END_HHMM)
        if not (start <= now <= end):
            return False

        if int(self.state.get("trades_today", 0)) >= Config.MAX_TRADES_PER_DAY:
            return False

        max_loss = Config.MAX_DAILY_LOSS_DOLLARS
        if Config.USE_PERCENTAGE_RISK:
            # We don't have broker access here easily, but we can assume starting equity if not found
            # Ideally we'd pass equity or acct to can_trade
            # For now, let's use the STARTING_EQUITY as a base for daily loss if USE_PERCENTAGE_RISK is on
            # and we are in risk.py which is more static.
            max_loss = Config.STARTING_EQUITY * (Config.MAX_DAILY_LOSS_PCT / 100.0)

        if abs(float(self.state.get("daily_pnl", 0.0))) >= max_loss:
            return False

        return True