from __future__ import annotations

import json
import os
from datetime import datetime
from json import JSONDecodeError

from config import Config


class RiskManager:
    def __init__(self, user_id: int | None = None):
        self.user_id = user_id
        if user_id:
            self.state_file = os.path.join(Config.LOG_DIR, f"risk_state_user_{user_id}.json")
        else:
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
            "weekly_pnl": 0.0,
            "peak_equity": Config.STARTING_EQUITY,
            "sector_counts": {},
            "symbol_correlations": {}, # Symbol to [returns_list]
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

    def process_pnl_withdrawals(self, daily_pnl: float, current_balance: float = 0.0, notify_func=None):
        """Checks if PnL thresholds are met and alerts/records for withdrawal."""
        # Check if threshold exists in Config, else use default 50
        threshold = getattr(Config, "PROFIT_WITHDRAWAL_THRESHOLD_DOLLARS", 50.0)
        if daily_pnl <= threshold:
            return
            
        trading_share = current_balance * (getattr(Config, "PROFIT_SPLIT_TRADING_PCT", 70.0) / 100.0)
        vault_share = current_balance * (getattr(Config, "PROFIT_SPLIT_COLD_STORAGE_PCT", 30.0) / 100.0)
        
        # Requested Report Format: PROFIT ALERT — WITHDRAWAL READY
        report = [
            "PROFIT ALERT — WITHDRAWAL READY",
            "",
            f"Current Balance: ${current_balance:.2f}",
            f"Profit Above Threshold: ${daily_pnl:.2f}",
            "",
            "Suggested Action:",
            "Transfer profits to cold storage (Tangem)",
            "",
            f"Recommended Amount: ${vault_share:.2f}",
            "",
            "Status:",
            f"- Trading Capital: ${trading_share:.2f}",
            f"- Vault Capital: ${vault_share:.2f}"
        ]
        
        msg = "\n".join(report)
               
        if notify_func:
            notify_func(msg)
            
        # Record in audit trail
        audit_msg = f"Vault transfer suggested: ${vault_share:.2f} (30% of ${current_balance:.2f})"
        self.state["last_vault_transfer"] = datetime.now().isoformat()
        self.state["last_vault_amount"] = vault_share
        self._save_state()

    def _roll_day_if_needed(self) -> None:
        # Weekly PnL Reset on Monday
        if self.state.get("date") != self._today_str():
            # Process vault transfer before resetting daily
            daily_pnl = float(self.state.get("daily_pnl", 0.0))
            if daily_pnl > 0:
                 # We need current balance here. In _roll_day_if_needed we don't have it easily.
                 # But we can use Config.STARTING_EQUITY + daily_pnl as estimate if needed, 
                 # or just daily_pnl.
                 from broker_alpaca import AlpacaBroker
                 try:
                     balance = AlpacaBroker().get_account_equity()
                 except:
                     balance = Config.STARTING_EQUITY + daily_pnl
                 self.process_pnl_withdrawals(daily_pnl, current_balance=balance)

            old_peak = self.state.get("peak_equity", Config.STARTING_EQUITY)
            old_weekly_pnl = self.state.get("weekly_pnl", 0.0)
            
            # Reset weekly PnL on Monday
            is_monday = datetime.now().weekday() == 0
            new_weekly_pnl = 0.0 if is_monday else old_weekly_pnl
            
            self.state = self._default_state()
            self.state["peak_equity"] = old_peak # Peak equity persists across days
            self.state["weekly_pnl"] = new_weekly_pnl
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

    def record_cooldown(self, symbol: str) -> None:
        self._roll_day_if_needed()
        cooldowns = self.state.get("cooldowns", {})
        cooldowns[symbol] = datetime.now().isoformat()
        self.state["cooldowns"] = cooldowns
        self._save_state()

    def is_in_cooldown(self, symbol: str) -> bool:
        self._roll_day_if_needed()
        cooldowns = self.state.get("cooldowns", {})
        if symbol not in cooldowns:
            return False
        
        last_exit_str = cooldowns[symbol]
        try:
            last_exit = datetime.fromisoformat(last_exit_str)
            elapsed = (datetime.now() - last_exit).total_seconds() / 60.0
            if elapsed < Config.TRADE_COOLDOWN_MINUTES:
                return True
        except Exception:
            pass
        return False

    def check_spread(self, symbol: str) -> bool:
        """
        Verifies if the bid-ask spread is within acceptable limits.
        This prevents bad fills in low-liquidity stocks.
        """
        from market_data import MarketDataClient
        md = MarketDataClient()
        spread_pct = md.get_spread_pct(symbol)
        
        if spread_pct is None:
            return True # Assume OK if we can't get quote (might be data feed lag)
            
        if spread_pct > Config.MAX_SPREAD_PCT:
            return False
            
        return True

    def calculate_kelly_size(self, win_rate: float, win_loss_ratio: float, account_equity: float) -> float:
        """
        Calculates the optimal position size using the Kelly Criterion.
        Formula: K% = W - (1 - W) / R
        W = Win Rate, R = Win/Loss Ratio
        """
        if win_loss_ratio <= 0:
            return Config.RISK_PCT_PER_TRADE / 100.0
            
        # Standard Kelly
        kelly_pct = win_rate - (1 - win_rate) / win_loss_ratio
        
        # Use Fractional Kelly (usually 0.5) to be conservative
        # Profit Reinvestment / Capital Growth scaling
        if Config.AUTO_REINVEST_PROFITS:
            daily_pnl = float(self.state.get("daily_pnl", 0.0))
            if daily_pnl > 0:
                # Be more aggressive when in profit
                kelly_pct *= (1.0 + (daily_pnl / Config.STARTING_EQUITY))
            elif daily_pnl < 0:
                # Be more conservative when in drawdown
                kelly_pct *= (1.0 - (abs(daily_pnl) / Config.STARTING_EQUITY))
        
        fractional_kelly = Config.KELLY_FRACTION * kelly_pct
        
        # Clamp between a minimum (0.5%) and maximum (Config.MAX_POSITION_SIZE_PCT)
        clamped_kelly = max(0.005, min(fractional_kelly, Config.MAX_ACCOUNT_DEPLOYMENT_PCT / 200.0))
        
        return clamped_kelly

    def record_trade(self, pnl_change: float = 0.0, symbol: str | None = None, is_entry: bool = True) -> None:
        self._roll_day_if_needed()
        # Increment trade count for any trade (entry or exit)
        self.state["trades_today"] = int(self.state.get("trades_today", 0)) + 1
        # Accumulate PnL
        self.state["daily_pnl"] = float(self.state.get("daily_pnl", 0.0)) + float(pnl_change)
        self.state["weekly_pnl"] = float(self.state.get("weekly_pnl", 0.0)) + float(pnl_change)
        
        if not is_entry and pnl_change != 0:
            # Update consecutive losses
            if pnl_change < 0:
                self.state["consecutive_losses"] = self.state.get("consecutive_losses", 0) + 1
            else:
                self.state["consecutive_losses"] = 0

        # Track sectors for entries
        if is_entry and symbol:
            sector = self._get_symbol_sector(symbol)
            counts = self.state.get("sector_counts", {})
            counts[sector] = counts.get(sector, 0) + 1
            self.state["sector_counts"] = counts
        elif not is_entry and symbol:
            sector = self._get_symbol_sector(symbol)
            counts = self.state.get("sector_counts", {})
            if sector in counts:
                counts[sector] = max(0, counts[sector] - 1)
            self.state["sector_counts"] = counts

        self._save_state()

    def update_peak_equity(self, current_equity: float) -> None:
        peak = self.state.get("peak_equity", 0.0)
        if current_equity > peak:
            self.state["peak_equity"] = current_equity
            self._save_state()

    def _get_symbol_sector(self, symbol: str) -> str:
        """
        Retrieves the sector for a given symbol. 
        In a real app, this would use a proper API. 
        For now, we'll use a simplified mapping or 'Unknown'.
        """
        # Bond Universe is its own 'sector'
        from universe import BOND_UNIVERSE
        if symbol in BOND_UNIVERSE:
            return "Bonds"
        
        # Crypto is its own 'sector'
        if "/" in symbol or symbol in ["BTC", "ETH", "LTC"]:
            return "Crypto"

        # Simplified stock mapping for demonstration
        sector_map = {
            "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "TSLA": "Consumer Cyclical",
            "F": "Consumer Cyclical", "SOFI": "Financial Services", "PLTR": "Technology",
            "SNAP": "Communication Services", "NIO": "Consumer Cyclical", "ACB": "Healthcare",
            "SNDL": "Healthcare", "TLT": "Bonds", "GLD": "Commodities"
        }
        return sector_map.get(symbol, "Other")

    def can_trade(self, is_exit: bool = False, current_hhmm: int | None = None, symbol: str | None = None, current_equity: float | None = None, bars: list | None = None, total_at_risk: float = 0.0, timeframe: str = "1Min") -> bool:
        """
        Exit/sell trades should still be allowed even when risk blocks new buys.
        """
        self._roll_day_if_needed()

        if is_exit:
            return True

        # 0. META-RISK ENGINE (Global Risk Cap)
        if current_equity and total_at_risk > (current_equity * (Config.GLOBAL_RISK_CAP_PCT / 100.0)):
            return False

        # 0.1 Crisis Mode / Defensive AI
        if bars and len(bars) >= 2:
            # Sudden drop detection (flash crash logic)
            last_close = float(bars[-1].close)
            prev_close = float(bars[-2].close)
            drop_pct = (prev_close - last_close) / prev_close
            if drop_pct >= (Config.FLASH_CRASH_PROTECTION_PCT / 100.0):
                # Shutdown and notify
                return False 

        # 1. Trading Window
        now = current_hhmm if current_hhmm is not None else int(datetime.now().strftime("%H%M"))
        start = int(Config.ALLOWED_START_HHMM)
        end = int(Config.ALLOWED_END_HHMM)
        if not (start <= now <= end):
            return False

        # 2. Daily Trade Limit (Independent by timeframe)
        max_trades = Config.MAX_SCALPING_TRADES_PER_DAY if timeframe == "1Min" else Config.MAX_SWING_TRADES_PER_DAY
        if int(self.state.get("trades_today", 0)) >= max_trades:
            return False

        # 3. Loss Limits (Daily & Weekly) - NON-NEGOTIABLE HARD SHUTDOWN
        base_equity = current_equity if current_equity else Config.STARTING_EQUITY
        
        # Kill Switch: 3 Losses in a Row
        max_consecutive = getattr(Config, "KILL_SWITCH_CONSECUTIVE_LOSSES", 3)
        if int(self.state.get("consecutive_losses", 0)) >= max_consecutive:
            alert_id = f"kill_switch_consecutive_losses_{self._today_str()}"
            if not self.seen_alert(alert_id):
                from bot_runner import log, send_notification
                msg = f"KILL SWITCH TRIGGERED: {max_consecutive} consecutive losses hit. Bot stopping for safety."
                log(msg, level="ERROR")
                send_notification(msg)
                self.mark_alert_seen(alert_id)
            return False

        # Daily Loss
        max_daily_loss = Config.MAX_DAILY_LOSS_DOLLARS
        if Config.USE_PERCENTAGE_RISK:
            max_daily_loss = base_equity * (Config.MAX_DAILY_LOSS_PCT / 100.0)

        daily_pnl = float(self.state.get("daily_pnl", 0.0))
        if daily_pnl < 0 and abs(daily_pnl) >= max_daily_loss:
            # HARD SHUTDOWN
            alert_id = f"daily_loss_limit_{self._today_str()}"
            if not self.seen_alert(alert_id):
                from bot_runner import log, send_notification
                report = [
                    "RISK ALERT",
                    "",
                    "Daily Loss Limit Reached / Approaching",
                    "",
                    f"Current Loss: ${abs(daily_pnl):.2f}",
                    f"Max Allowed: ${max_daily_loss:.2f}",
                    "",
                    "Bot Status:",
                    "- PAUSED",
                    "",
                    "Action:",
                    "- Trading will stop if loss exceeds limit"
                ]
                msg = "\n".join(report)
                send_notification(msg, title="RISK ALERT: DAILY LOSS")
                self.mark_alert_seen(alert_id)
            return False
            
        # Weekly Loss
        max_weekly_loss = Config.MAX_WEEKLY_LOSS_DOLLARS
        if Config.USE_PERCENTAGE_RISK:
            max_weekly_loss = base_equity * (Config.MAX_WEEKLY_LOSS_PCT / 100.0)
            
        weekly_pnl = float(self.state.get("weekly_pnl", 0.0))
        if weekly_pnl < 0 and abs(weekly_pnl) >= max_weekly_loss:
            # HARD SHUTDOWN
            return False

        # 3.1 Loss Pattern Kill Switch
        if self.state.get("consecutive_losses", 0) >= 3:
             # Stop trading after 3 consecutive losses to re-evaluate
             return False

        # 4. Equity Drawdown Protection (Circuit Breaker)
        if current_equity:
            self.update_peak_equity(current_equity)
            peak = self.state.get("peak_equity", current_equity)
            drawdown = (peak - current_equity) / peak
            if drawdown >= (Config.MAX_EQUITY_DRAWDOWN_PCT / 100.0):
                return False

        # 5. Sector Diversification
        if symbol:
            sector = self._get_symbol_sector(symbol)
            counts = self.state.get("sector_counts", {})
            if counts.get(sector, 0) >= Config.MAX_POSITIONS_PER_SECTOR:
                return False
        
        # 6. Correlation Risk Control
        # In multi-bot mode, check if we are already too exposed to a single direction
        # across correlated assets (e.g., BTC/ETH)
        # Simplified: If crypto sector count >= 2, only allow if they are in opposite directions?
        # For now, just a hard limit on crypto positions.
        if symbol and self._get_symbol_sector(symbol) == "Crypto":
            crypto_count = counts.get("Crypto", 0)
            if crypto_count >= 2: # Max 2 crypto positions
                return False

        # 7. Trade Cooldown
        if symbol and self.is_in_cooldown(symbol):
            return False

        # 8. Adaptive Frequency Control
        if Config.ADAPTIVE_FREQUENCY_CONTROL:
            # If we've traded a lot today and PnL is negative, slow down.
            if int(self.state.get("trades_today", 0)) > 5 and float(self.state.get("daily_pnl", 0.0)) < 0:
                return False

        # 9. Market Stress Index (Avoid trading in chaotic conditions)
        # In practice, this would check a collection of symbol bars. 
        # For now, it's a placeholder logic within bot_runner's call.

        # 10. ELITE FEATURE: 'Auto-Hedge' (Market Crash Detection)
        if Config.AUTO_HEDGE_ENABLED and current_equity:
            # If SPY (market proxy) is down > 2% in the last 60 bars, 
            # we are in a high-risk 'Crash' regime.
            # This would normally fetch SPY bars, here we assume it's passed or 
            # we check general portfolio drawdown as a proxy.
            if self.state.get("daily_pnl", 0.0) < -(base_equity * 0.02):
                # Trigger 'Defensive Mode'
                self.state["hedge_active"] = True
                self._save_state()

        return True

    def calculate_risk_parity_size(self, symbol: str, current_equity: float, bars: list) -> float:
        """
        Adjusts position size based on asset volatility (Risk Parity).
        Higher volatility = Smaller position size.
        """
        if not Config.RISK_PARITY_ENABLED or not bars or len(bars) < 20:
            return Config.RISK_PCT_PER_TRADE / 100.0
            
        from strategy import Strategy
        df = Strategy._calculate_indicators(bars)
        atr = df['atr'].iloc[-1]
        price = df['close'].iloc[-1]
        
        # Risk Parity: Size = (Target Risk $) / (ATR * ATR_SL_MULTIPLIER)
        risk_dollars = current_equity * (Config.RISK_PCT_PER_TRADE / 100.0)
        risk_per_share = atr * Config.ATR_SL_MULTIPLIER
        
        if risk_per_share <= 0:
            return 0.0
            
        shares = risk_dollars / risk_per_share
        size_pct = (shares * price) / current_equity
        
        return min(size_pct, Config.MAX_ACCOUNT_DEPLOYMENT_PCT / 100.0)