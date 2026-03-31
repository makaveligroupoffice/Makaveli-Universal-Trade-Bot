from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from flask import Flask

from bot_state import BotStateStore
from broker_alpaca import AlpacaBroker
from broker_base import BrokerBase
from config import Config
from market_data import MarketDataClient
from risk import RiskManager
from scanner import Scanner
from strategy import Strategy
from performance import PerformanceAnalyzer
from learning import LearningEngine
from trade_journal import TradeJournal
from notifications import send_notification
from ai_engine import AIEngine
from research import ResearchEngine
from backup import BackupManager
from updater import AutoUpdater
from models import db, User

os.makedirs(Config.LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(Config.LOG_DIR, "autobot.log")),
        logging.StreamHandler(),
    ],
)

from crypto_investor import CryptoInvestor

log = logging.getLogger("autobot")

# We need a dummy flask app context for DB access
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


class AutoTrader:
    def __init__(self, user: User | None = None, broker: BrokerBase | None = None, timeframe: str = "1Min", strategy_active: list | None = None, risk_pct: float | None = None):
        self.user = user
        self.timeframe = timeframe
        self.strategy_active = strategy_active or ["SNIPER", "CONFLUENCE"]
        self.risk_pct_override = risk_pct
        self.last_run = time.time()
        
        if broker:
            self.broker = broker
            user_id = "external"
        elif user and hasattr(user, 'alpaca_key') and user.alpaca_key and user.alpaca_secret:
            self.broker = AlpacaBroker(
                key=user.alpaca_key,
                secret=user.alpaca_secret,
                paper=user.alpaca_paper
            )
            user_id = user.id
        else:
            self.broker = AlpacaBroker()
            user_id = getattr(user, "id", None)

        self._validate_launch_mode()

        self.risk = RiskManager(user_id=user_id)
        self.scanner = Scanner()
        self.strategy = Strategy()
        self.data = MarketDataClient()
        
        self.state_store = BotStateStore(Config.BOT_STATE_FILE, user_id=user_id)
        
        journal_path = Config.TRADE_JOURNAL_FILE
        if user_id and user_id != "external":
            journal_path = os.path.join(Config.LOG_DIR, f"trade_journal_user_{user_id}.jsonl")

        self.journal = TradeJournal(journal_path)
        self.analyzer = PerformanceAnalyzer(journal_path)
        self.learning = LearningEngine(journal_path)
        self.ai = AIEngine()
        self.researcher = ResearchEngine()
        self.backup_mgr = BackupManager()
        self.updater = AutoUpdater()
        self.crypto_investor = CryptoInvestor(self.broker)
        self.state = self.state_store.load()
        self.consecutive_failures = 0
        self.safe_mode = False
        self.summary_date = datetime.now().strftime("%Y-%m-%d")
        self.daily_summary = self._default_daily_summary()

    def _validate_launch_mode(self):
        if hasattr(self.broker, "alpaca_paper"):
            paper = self.broker.alpaca_paper
        else:
            paper = self.user.alpaca_paper if self.user else Config.ALPACA_PAPER
        
        if not paper:
            # Triple-check safety for Live trading
            required_ack = "I_UNDERSTAND_THIS_IS_REAL_MONEY"
            if Config.LIVE_TRADING_ACKNOWLEDGED != required_ack:
                raise RuntimeError(
                    "Live trading blocked. Set LIVE_TRADING_ACKNOWLEDGED="
                    "I_UNDERSTAND_THIS_IS_REAL_MONEY to enable live mode."
                )
            
            # Additional safety toggle check
            if not Config.LIVE_MODE_ENABLED:
                raise RuntimeError(
                    "Live trading blocked. LIVE_MODE_ENABLED is false in Config. "
                    "This is an extra safety layer to prevent accidental real-money trades."
                )
            
            log.warning("!!! BOT IS RUNNING IN LIVE TRADING MODE (REAL MONEY) !!!")

    @staticmethod
    def _default_daily_summary() -> dict:
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "buys_submitted": 0,
            "buys_filled": 0,
            "sells_submitted": 0,
            "sells_filled": 0,
            "order_failures": 0,
            "timeouts": 0,
            "safe_mode_activations": 0,
        }

    def _roll_daily_summary_if_needed(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today == self.summary_date:
            return

        with open(Config.DAILY_SUMMARY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.daily_summary) + "\n")

        self.summary_date = today
        self.daily_summary = self._default_daily_summary()

    def _bump_summary(self, key: str):
        self._roll_daily_summary_if_needed()
        self.daily_summary[key] = int(self.daily_summary.get(key, 0)) + 1

    @property
    def positions(self) -> dict:
        return self.state.get("positions", {})

    @property
    def pending_orders(self) -> dict:
        return self.state.get("pending_orders", {})

    @property
    def dynamic_config(self) -> dict:
        return self.state.get("dynamic_config", {})

    def _save_state(self):
        # Determine operational state for the HUD
        if self.state.get("positions"):
            self.state["operational_state"] = "TRADING"
        else:
            self.state["operational_state"] = "SCANNING"

        # Periodically evolve and adjust dynamic config
        now = time.time()
        if int(now) % 3600 < 60: # once an hour roughly
             self.state["operational_state"] = "READING"
             self.learning.evolve()
             self._monitor_manual_trades()
             self.state["dynamic_config"] = self.learning.get_dynamic_config()
             
             # Also perform internet research if market is closed and it's time
             if not self._market_is_open() and Config.ENABLE_INTERNET_RESEARCH:
                 last_research = self.state.get("last_internet_research", 0)
                 if now - last_research > Config.RESEARCH_INTERVAL_SECONDS:
                     summary = self.researcher.perform_internet_research()
                     if summary:
                         self.researcher.apply_research_to_strategy(summary)
                         self.state["last_internet_research"] = now
        
        self.state_store.save(self.state)

    def _clear_pending_order(self, order_id: str):
        if order_id in self.state["pending_orders"]:
            del self.state["pending_orders"][order_id]
        if order_id in self.state.get("last_order_statuses", {}):
            del self.state["last_order_statuses"][order_id]
        self._save_state()

    def _clear_position_state(self, symbol: str):
        if symbol in self.state["positions"]:
            del self.state["positions"][symbol]
        # also clear any pending orders for this symbol
        to_clear = [oid for oid, info in self.pending_orders.items() if info.get("symbol") == symbol]
        for oid in to_clear:
            self._clear_pending_order(oid)
        self._save_state()

    def _minutes_to_close(self) -> int:
        clock = self.broker.get_clock()
        if clock is not None:
            next_close = clock.next_close.astimezone()
            now = clock.timestamp.astimezone()
            return int((next_close - now).total_seconds() // 60)

        now = int(datetime.now().strftime("%H%M"))
        end = int(Config.ALLOWED_END_HHMM)
        now_minutes = (now // 100) * 60 + (now % 100)
        end_minutes = (end // 100) * 60 + (end % 100)
        return end_minutes - now_minutes

    def _market_is_open(self) -> bool:
        clock = self.broker.get_clock()
        if clock is None:
            return self.risk.can_trade(is_exit=False)
        return bool(clock.is_open)

    def _send_daily_report(self):
        """Generates and sends a comprehensive performance report."""
        from performance import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
        
        account = self.broker.get_account()
        account_info = {"equity": float(getattr(account, "equity", Config.STARTING_EQUITY))}
        
        # Get market condition
        from intelligence import MarketRegimeIntelligence
        # We need some bars to get regime, use SPY or a common symbol
        bars = self.data.get_recent_bars("SPY", minutes=30)
        market_condition = MarketRegimeIntelligence.get_current_regime(bars) if bars else "Unknown"
        
        report = analyzer.generate_report(days=1, account_info=account_info, market_condition=market_condition)
        log.info("Sending daily performance report...")
        send_notification(report, title="📈 DAILY TRADING REPORT")

    def _send_weekly_report(self):
        """Generates and sends a weekly performance report."""
        from performance import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
        report = analyzer.generate_weekly_report()
        log.info("Sending weekly performance report...")
        send_notification(report, title="📊 WEEKLY REPORT")

    def _send_quality_analysis(self):
        """Generates and sends a trade quality analysis report."""
        from performance import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
        report = analyzer.generate_quality_analysis()
        log.info("Sending trade quality analysis...")
        send_notification(report, title="🧠 TRADE QUALITY ANALYSIS")

    def _send_fast_audit_report(self, days: int = 7):
        """Generates and sends the Fast Audit Result report."""
        from performance import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
        report = analyzer.generate_fast_audit_report(days=days)
        log.info(f"Sending Fast Audit Report for last {days} days...")
        send_notification(report, title="⚡ Fast audit result")

    def _send_bot_health_report(self):
        """Generates and sends a bot health status report."""
        # 1. API Status
        api_status = "CONNECTED"
        try:
            self.broker.get_account()
        except:
            api_status = "ERROR"
        
        # 2. Last Trade Time
        last_trade_time = "N/A"
        try:
            with open(Config.TRADE_JOURNAL_FILE, "r") as f:
                lines = f.readlines()
                if lines:
                    last_trade_time = json.loads(lines[-1]).get("timestamp", "N/A")
        except:
            pass

        # 3. Execution Errors
        exec_errors = self.state.get("consecutive_failures", 0)
        
        # 4. Latency (Estimate)
        import time
        start = time.time()
        self.broker.get_clock()
        latency_ms = int((time.time() - start) * 1000)

        system_status = "HEALTHY"
        if api_status == "ERROR" or exec_errors > 2:
            system_status = "CRITICAL"
        elif latency_ms > 500:
            system_status = "WARNING"

        report = [
            "BOT HEALTH STATUS",
            "",
            f"API Status: {api_status}",
            f"Last Trade Time: {last_trade_time}",
            "",
            f"Execution Errors: {exec_errors}",
            f"Missed Trades: {self.state.get('missed_trades', 0)}",
            "",
            f"Latency: {latency_ms}ms",
            "",
            f"System Status: {system_status}"
        ]
        
        msg = "\n".join(report)
        log.info("Sending bot health report...")
        send_notification(msg, title="🛠️ BOT HEALTH STATUS")

    def _check_auto_withdrawal(self):
        """
        Periodically checks if it's the right time and day to perform 
        an automated profit withdrawal to the linked bank account.
        """
        if not Config.BANK_WITHDRAWAL_ENABLED or not Config.AUTO_WITHDRAW_PROFITS:
            return

        from datetime import datetime
        now = datetime.now()
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        current_hhmm = now.strftime("%H%M")

        # Check if it's the configured day and time
        if current_day == Config.WITHDRAWAL_DAY_OF_WEEK and current_hhmm == Config.WITHDRAWAL_TIME_HHMM:
            # Check if we've already withdrawn today to prevent duplicates
            last_withdraw_date = self.state.get("last_auto_withdrawal_date")
            today_str = now.strftime("%Y-%m-%d")
            
            if last_withdraw_date == today_str:
                return

            try:
                equity = self.broker.get_account_equity()
                from performance import PerformanceAnalyzer
                analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
                profit = analyzer.calculate_withdrawable_profit(equity)

                if profit > 0:
                    log.info(f"Triggering AUTO PROFIT WITHDRAWAL: ${profit:.2f}")
                    self.broker.withdraw_to_bank(profit, Config.BANK_ACCOUNT_ID)
                    
                    self.state["last_auto_withdrawal_date"] = today_str
                    self._save_state()
                    
                    msg = f"AUTO PROFIT WITHDRAWAL SUCCESSFUL!\nAmount: ${profit:.2f}\nBank Account: {Config.BANK_ACCOUNT_ID}"
                    send_notification(msg, title="💰 PROFIT ALERT — WITHDRAWAL COMPLETE")
                else:
                    log.info(f"Auto withdrawal skipped: No profit above reserve ${Config.MIN_CAPITAL_RESERVE}")
            except Exception as e:
                log.error(f"Auto withdrawal failed: {e}")
                send_notification(f"Auto withdrawal failed: {e}", title="❌ WITHDRAWAL ERROR")

    @staticmethod
    def _now_ts() -> float:
        return time.time()

    async def _async_evaluate_symbol_entry(self, symbol: str, momentum: float, current_hhmm: int, total_at_risk: float, current_equity: float):
        """Asynchronous wrapper for evaluating a single symbol for entry."""
        return await asyncio.to_thread(self._evaluate_symbol_entry, symbol, momentum, current_hhmm, total_at_risk, current_equity)

    def _evaluate_symbol_entry(self, symbol: str, momentum: float, current_hhmm: int, total_at_risk: float, current_equity: float):
        """
        Evaluates a single symbol for entry logic. 
        Extracted from the main loop to support parallel execution.
        """
        try:
            # Check if there is already a pending order for this symbol
            if any(info.get("symbol") == symbol for info in self.pending_orders.values()):
                return symbol, None, "Pending order exists", 0.0, {}

            allowed, live_reason = self._symbol_allowed_for_live(symbol)
            if not allowed:
                return symbol, None, f"Not allowed: {live_reason}", 0.0, {}

            spread_pct = self.data.get_spread_pct(symbol)
            max_spread = self.dynamic_config.get("max_spread_pct", Config.MAX_SPREAD_PCT)
            if spread_pct is None or spread_pct > max_spread:
                return symbol, None, f"Spread too wide: {spread_pct:.4%}", 0.0, {}

            # Scaling timeframe for multi-bot
            lookback_minutes = 30
            if self.timeframe == "15Min": lookback_minutes = 150
            elif self.timeframe == "5Min": lookback_minutes = 75
            
            bars = self.data.get_recent_bars(symbol, minutes=lookback_minutes)
            if not bars:
                return symbol, None, "No bar data", 0.0, {}

            # Sector/Diversity Check
            if not self.risk.can_trade(is_exit=False, current_hhmm=current_hhmm, symbol=symbol, current_equity=current_equity, total_at_risk=total_at_risk, timeframe=self.timeframe, bars=bars):
                return symbol, None, "Risk limit reached", 0.0, {}

            # --- Number One Bot: Fetch Multi-Timeframe Bars ---
            mtf_bars = {}
            if Config.ENABLE_FRACTAL_MTF:
                for tf in Config.MTF_TIMEFRAMES:
                    if tf == "1Min":
                        mtf_bars[tf] = bars
                    else:
                        tf_unit = int(tf.replace("Min", ""))
                        tf_minutes = tf_unit * 100
                        tf_bars = self.data.get_historical_bars(symbol, minutes=tf_minutes, timeframe=tf)
                        if tf_bars:
                            mtf_bars[tf] = tf_bars

            # News Awareness Filter
            if Config.ENABLE_NEWS_FILTER:
                news = self.data.get_news(symbol, days=1)
                if not self.strategy.is_news_safe(symbol, self.data, news_list=news):
                    return symbol, None, "News unsafe", 0.0, {}

            should_buy, buy_reason, buy_strength, buy_indicators = self.strategy.should_buy(bars, self.dynamic_config, active_strategies=self.strategy_active, symbol=symbol, mtf_bars=mtf_bars)
            should_short, short_reason, short_strength, short_indicators = self.strategy.should_short(bars, self.dynamic_config, active_strategies=self.strategy_active, symbol=symbol)
            
            action = None
            reason = None
            strength = 0.0
            indicators = {}
            is_partial_entry = False

            # Partial Entry Support (Scaling in)
            if symbol in self.positions:
                if not Config.ENABLE_PARTIAL_ENTRIES:
                    return symbol, None, "Partial entries disabled", 0.0, {}, False
                
                pos_info = self.positions[symbol]
                if pos_info.get("side") == "buy" and momentum > 0:
                     entry_price = pos_info.get("entry_price", 0)
                     latest_price = self.data.get_latest_mid_price(symbol)
                     if latest_price and latest_price > entry_price * 1.01:
                         is_partial_entry = True
                elif pos_info.get("side") == "short" and momentum < 0:
                     entry_price = pos_info.get("entry_price", 0)
                     latest_price = self.data.get_latest_mid_price(symbol)
                     if latest_price and latest_price < entry_price * 0.99:
                         is_partial_entry = True
                
                if not is_partial_entry:
                    return symbol, None, "Not ready to scale in", 0.0, {}, False

            if should_buy:
                action = "buy"
                reason = buy_reason
                strength = buy_strength
                indicators = buy_indicators
            elif should_short:
                action = "short"
                reason = short_reason
                strength = short_strength
                indicators = short_indicators

            return symbol, action, reason, strength, indicators, is_partial_entry
        except Exception as e:
            log.error(f"Error evaluating {symbol}: {e}")
            return symbol, None, str(e), 0.0, {}, False

    def _monitor_manual_trades(self):
        """Fetches recent orders from Alpaca and identifies manual trades to learn from."""
        try:
            # Fetch last 50 orders
            orders = self.broker.get_orders(status="all", limit=50)
            if not orders:
                return

            # Get known bot orders from state
            bot_order_ids = set(self.state.get("pending_orders", {}).keys())
            bot_order_ids.update(self.state.get("last_order_statuses", {}).keys())
            
            # Also check journal for recent bot orders to be sure
            journal_path = Config.TRADE_JOURNAL_FILE
            if os.path.exists(journal_path):
                with open(journal_path, "r") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            oid = entry.get("order_id")
                            if oid: bot_order_ids.add(str(oid))
                        except: pass

            for order in orders:
                oid = str(order.id)
                if oid in bot_order_ids:
                    continue
                
                # This is a manual trade (not initiated by bot)
                if order.status != "filled":
                    continue

                # Check if we already processed this manual trade
                processed_manual = self.state.get("processed_manual_orders", [])
                if oid in processed_manual:
                    continue

                symbol = order.symbol
                side = order.side
                qty = float(order.qty)
                price = float(order.filled_avg_price) if order.filled_avg_price else float(order.limit_price or 0)
                
                log.info(f"Detected manual trade: {side} {qty} {symbol} at {price}. Recording for learning.")
                
                # Capture context (indicators) at this moment
                # Scaling timeframe for multi-bot
                lookback_minutes = 30
                if self.timeframe == "15Min": lookback_minutes = 150
                elif self.timeframe == "5Min": lookback_minutes = 75
            
                bars = self.data.get_recent_bars(symbol, minutes=lookback_minutes)
                indicators = {}
                if len(bars) >= 20:
                    indicators = self.strategy._calculate_indicators(bars)
                
                market_state = self.data.get_market_regime()
                
                # Record in journal with manual flag and context
                context = {
                    "indicators": indicators,
                    "market_state": market_state,
                    "order_id": oid
                }
                
                # We need to estimate PnL for exits
                pnl = None
                if side in ["sell", "cover"]:
                    # Try to find the entry in recent positions or journal
                    # For now, we'll just record it and let LearningEngine handle it
                    pass

                # Use the detection reason
                det_reason = f"Manual Trade Detection (ID: {oid})"
                # Extract tags from reason for trade memory
                tags = []
                if "BREAKOUT" in det_reason.upper(): tags.append("breakout")
                if "SCALPING" in det_reason.upper(): tags.append("scalp")
                if "SNIPER" in det_reason.upper(): tags.append("sniper")
                if "REVERSAL" in det_reason.upper(): tags.append("reversal")

                self.journal.record_trade(
                    symbol=symbol,
                    action=side,
                    qty=qty,
                    price=price,
                    side=side,
                    pnl=pnl,
                    reason=det_reason,
                    manual=True,
                    context=context,
                    tags=tags
                )
                
                # Attach context to the last recorded entry in journal (hacky but works if we update record_trade)
                # Actually, let's update record_trade to accept context
                
                processed_manual.append(oid)
                # Keep list reasonable
                if len(processed_manual) > 200:
                    processed_manual = processed_manual[-200:]
                self.state["processed_manual_orders"] = processed_manual
                self._save_state()

        except Exception as e:
            log.error(f"Error monitoring manual trades: {e}")

    @staticmethod
    def _elapsed_seconds(start_ts: float | None) -> float:
        if not start_ts:
            return 0.0
        return time.time() - float(start_ts)

    def _calc_qty(self, price: float, symbol: str, signal_strength: float = 1.0, indicators: dict | None = None) -> float:
        if price <= 0:
            return 0.0

        is_crypto = "/" in symbol or any(c in symbol for c in ["BTC", "ETH", "SOL", "LTC"])
        
        # --- Volatility-Adjusted Stop Loss (ATR) ---
        atr = indicators.get("atr14") if indicators else None
        if atr and atr > 0:
            # Position Size = (Account Risk Amount) / (Stop Loss Distance)
            # Stop Loss Distance = ATR * Multiplier
            risk_per_share = atr * Config.ATR_MULTIPLIER
            log.info(f"Using ATR-based risk for {symbol}: ATR={atr:.4f}, SL_Dist={risk_per_share:.4f} ({Config.ATR_MULTIPLIER}x)")
        else:
            sl_pct = (self.dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) if self.dynamic_config else Config.STOP_LOSS_PCT) / 100.0
            risk_per_share = price * sl_pct
            
        if risk_per_share <= 0:
            return 0.0

        # Calculate Risk Amount based on Account Size
        acct = self.broker.get_account()
        equity = float(acct.equity)

        # Base Risk: 1% of account or fixed dollar amount
        risk_amount = Config.RISK_PER_TRADE_DOLLARS
        if Config.USE_PERCENTAGE_RISK:
            # Kelly Criterion Integration
            perf = self.dynamic_config.get("symbol_performance", {}).get(symbol, {})
            # Use general stats or default if no symbol specific stats
            win_rate = 0.55 # Default assumption
            win_loss_ratio = 1.5 # Default 1.5:1
            
            # Scale Kelly based on signal strength
            kelly_pct = self.risk.calculate_kelly_size(win_rate, win_loss_ratio, equity)
            risk_amount = equity * kelly_pct
            
            # Volatility Scaling: Reduce risk if current ATR is high relative to price
            if Config.VOL_SCALING_ENABLED and atr:
                # Relative Volatility = ATR / Price
                rel_vol = atr / price
                # If rel_vol > 2%, start scaling down
                if rel_vol > 0.02:
                    scale_factor = 0.02 / rel_vol
                    risk_amount *= (scale_factor * Config.VOL_SCALING_FACTOR)
                    log.info(f"Volatility scaling applied to {symbol}: {scale_factor:.2f}x multiplier")

            log.info(f"Calculated risk for {symbol}: {kelly_pct*100:.2f}% risk (${risk_amount:.2f})")

        # Scale risk based on signal strength (Tiered Aggression)
        risk_amount = risk_amount * signal_strength

        # Quantity = Risk Amount / Risk Per Share (Stop Loss Distance)
        qty = risk_amount / risk_per_share
        
        # Determine dynamic max position value
        max_pos_value = Config.MAX_POSITION_VALUE_DOLLARS
        if Config.USE_PERCENTAGE_RISK:
            # Position value cap to ensure diversification (max 10% of equity per position)
            max_pos_value = min(Config.MAX_POSITION_VALUE_DOLLARS, equity * 0.10)

        max_by_position_value = max_pos_value / price
        qty = min(qty, max_by_position_value) if max_by_position_value > 0 else 0
        
        if not is_crypto:
            # For stocks, allow fractional if Alpaca allows, but most accounts use integers
            qty = int(qty)
            return float(qty) if qty > 0 else 0.0

        return qty

    def _account_allows_new_position(self, price: float, qty: float) -> tuple[bool, str]:
        acct = self.broker.get_account()
        try:
            buying_power = float(acct.buying_power)
            equity = float(acct.equity)
        except (TypeError, ValueError, AttributeError):
            return False, "invalid account values"

        position_value = price * qty
        max_deployment = equity * (Config.MAX_ACCOUNT_DEPLOYMENT_PCT / 100.0)

        if position_value > Config.MAX_POSITION_VALUE_DOLLARS:
            return False, "position value exceeds max position value"

        if position_value > buying_power:
            return False, "insufficient buying power"

        if position_value > max_deployment:
            return False, "position value exceeds account deployment cap"

        return True, "account checks passed"

    @staticmethod
    def _symbol_allowed_for_live(symbol: str) -> tuple[bool, str]:
        if Config.ALPACA_PAPER:
            return True, "paper mode"

        if not Config.LIVE_MODE_WHITELIST_ONLY:
            return True, "live whitelist disabled"

        if symbol.upper() not in Config.LIVE_WHITELIST:
            return False, "symbol not allowed by live whitelist"

        return True, "allowed by live whitelist"

    @staticmethod
    def _normalize_order_status(status_obj) -> str:
        if status_obj is None:
            return ""
        value = getattr(status_obj, "value", status_obj)
        return str(value).strip().lower()

    def _record_failure(self, context: str, exc: Exception):
        self.consecutive_failures += 1
        msg = f"{context}: {exc}"
        log.exception(msg)

        if self.consecutive_failures >= Config.MAX_CONSECUTIVE_FAILURES:
            self.safe_mode = True
            self._bump_summary("safe_mode_activations")
            crit_msg = f"SAFE MODE activated after {self.consecutive_failures} consecutive failures"
            log.critical(crit_msg)
            send_notification(crit_msg, title="CRITICAL: Safe Mode")

    def _reset_failures(self):
        self.consecutive_failures = 0

    def _log_startup_reconciliation(self):
        positions = self.broker.get_all_positions()
        orders = self.broker.get_orders(status="all", limit=20)

        open_order_statuses = {
            "new",
            "accepted",
            "pending_new",
            "partially_filled",
            "accepted_for_bidding",
        }
        working_orders = [
            o for o in orders
            if self._normalize_order_status(getattr(o, "status", "")) in open_order_statuses
        ]

        log.info(
            "Startup reconciliation | "
            f"mode={'PAPER' if Config.ALPACA_PAPER else 'LIVE'} | "
            f"positions_on_broker={len(positions)} | working_orders_on_broker={len(working_orders)} | "
            f"state_positions={list(self.positions.keys())} | state_pending_orders={list(self.pending_orders.keys())}"
        )

        for pos in positions:
            log.info(
                f"Startup position | symbol={getattr(pos, 'symbol', None)} "
                f"qty={getattr(pos, 'qty', None)} avg_entry_price={getattr(pos, 'avg_entry_price', None)}"
            )

        for order in working_orders:
            log.info(
                f"Startup working order | id={getattr(order, 'id', None)} "
                f"symbol={getattr(order, 'symbol', None)} side={getattr(order, 'side', None)} "
                f"qty={getattr(order, 'qty', None)} status={self._normalize_order_status(getattr(order, 'status', None))}"
            )

    def _reconcile_existing_position(self):
        broker_positions = self.broker.get_all_positions()
        if not broker_positions:
            # Check if we think we have positions but broker says no
            if self.positions:
                for symbol in list(self.positions.keys()):
                    log.warning(f"Position for {symbol} exists in local state but not on broker. Clearing local state.")
                    self._clear_position_state(symbol)
            return

        broker_symbols = set()
        for pos in broker_positions:
            symbol = pos.symbol
            broker_symbols.add(symbol)
            qty = float(pos.qty)
            side = "buy" if qty > 0 else "short"
            avg_entry = float(pos.avg_entry_price)

            if symbol not in self.positions:
                self.state["positions"][symbol] = {
                    "entry_price": avg_entry,
                    "high_since_entry": avg_entry,
                    "side": side,
                    "manual": True,
                    "sold_half": False
                }
                log.info(f"Adopted existing position | symbol={symbol} side={side} qty={qty}")
                send_notification(f"Bot is now monitoring your manual {side} position in {symbol} at ${avg_entry:.2f}", title="Manual Trade Adopted")
            else:
                # Update high_since_entry if needed
                # We need latest price for this, will happen in try_exit
                pass

        # Cleanup positions that no longer exist on broker
        for symbol in list(self.positions.keys()):
            if symbol not in broker_symbols:
                log.info(f"Position for {symbol} closed externally. Clearing local state.")
                self._clear_position_state(symbol)

        self._save_state()

    def _handle_stale_pending_order(self):
        if not self.pending_orders:
            return

        if not self._market_is_open():
            return

        to_cancel = []
        for oid, info in self.pending_orders.items():
            submitted_at = info.get("submitted_at")
            elapsed = self._elapsed_seconds(submitted_at)
            if elapsed >= Config.ORDER_TIMEOUT_SECONDS:
                log.warning(
                    f"Pending order exceeded timeout | id={oid} "
                    f"symbol={info.get('symbol')} side={info.get('side')} elapsed={elapsed:.0f}s"
                )
                to_cancel.append(oid)

        if to_cancel:
            self.broker.cancel_all_orders()
            for oid in to_cancel:
                info = self.pending_orders.get(oid, {})
                self.trade_journal.record(
                    "pending_order_timeout",
                    {
                        "order_id": oid,
                        "symbol": info.get("symbol"),
                        "side": info.get("side"),
                    },
                )
                self._bump_summary("timeouts")
                self._clear_pending_order(oid)

    def _reconcile_pending_order(self):
        if not self.pending_orders:
            return

        for oid in list(self.pending_orders.keys()):
            order = self.broker.get_order_by_id(oid)
            if order is None:
                log.info(f"Pending order {oid} no longer found, clearing")
                self._clear_pending_order(oid)
                continue

            status = self._normalize_order_status(getattr(order, "status", ""))
            self.state.setdefault("last_order_statuses", {})[oid] = status
            self._save_state()

            if status in {"new", "accepted", "pending_new", "partially_filled", "accepted_for_bidding"}:
                continue

            symbol = getattr(order, "symbol", None)
            side_info = self.pending_orders[oid].get("side")

            if status == "filled":
                filled_avg_price = float(getattr(order, "filled_avg_price", 0.0))
                filled_qty = float(getattr(order, "filled_qty", 0.0))

                if side_info in {"buy", "short"}: # Entries
                    self.state["positions"][symbol] = {
                        "entry_price": filled_avg_price,
                        "high_since_entry": filled_avg_price,
                        "side": side_info,
                        "sold_half": False
                    }
                    msg = f"{side_info.upper()} filled | {symbol} | Price: ${filled_avg_price:.2f} | Qty: {filled_qty}"
                    log.info(msg)
                    send_notification(msg, title=f"Trade {side_info.upper()} Filled")
                    self.trade_journal.record_trade(
                        symbol=symbol,
                        action=side_info,
                        qty=filled_qty,
                        price=filled_avg_price,
                        side=side_info
                    )
                    self._bump_summary("buys_filled" if side_info == "buy" else "sells_filled")
                    self.risk.record_trade(0.0, symbol=symbol, is_entry=True)
                else: # Exits (sell/cover)
                    pos_info = self.positions.get(symbol, {})
                    entry_price = pos_info.get("entry_price", 0.0)
                    if side_info == "sell":
                        pnl = (filled_avg_price - entry_price) * filled_qty
                    else: # cover
                        pnl = (entry_price - filled_avg_price) * filled_qty

                    msg = f"{side_info.upper()} filled | {symbol} | Price: ${filled_avg_price:.2f} | Qty: {filled_qty} | PnL: ${pnl:.2f}"
                    log.info(msg)
                    send_notification(msg, title=f"Trade {side_info.upper()} Filled")
                    self.trade_journal.record_trade(
                        symbol=symbol,
                        action=side_info,
                        qty=filled_qty,
                        price=filled_avg_price,
                        side=side_info,
                        pnl=pnl
                    )
                    self._bump_summary("sells_filled" if side_info == "sell" else "buys_filled")
                    self.risk.record_trade(pnl, symbol=symbol, is_entry=False)
                    # Only clear position if it was NOT a partial exit
                    if not self.pending_orders[oid].get("is_partial", False):
                        if symbol in self.state["positions"]:
                            del self.state["positions"][symbol]

                self._clear_pending_order(oid)
            
            elif status in {"canceled", "expired", "rejected", "stopped", "suspended"}:
                log.warning(f"Pending order {oid} failed with status: {status}")
                if self.pending_orders[oid].get("is_partial", False):
                    if symbol in self.state["positions"]:
                        self.state["positions"][symbol]["sold_half"] = False
                self.trade_journal.record("order_failed", {"order_id": oid, "status": status, "symbol": symbol})
                self._bump_summary("order_failures")
                self._clear_pending_order(oid)
            
            self._save_state()

    def sync_state(self):
        self._roll_daily_summary_if_needed()
        self._handle_stale_pending_order()
        self._reconcile_pending_order()
        self._reconcile_existing_position()

        # Clean up stale position state if broker says we are flat
        for symbol in list(self.positions.keys()):
            qty = self.broker.get_position_qty(symbol)
            # Find if there are pending exit orders for this symbol
            pending_exit = any(info.get("symbol") == symbol and info.get("side") in {"sell", "cover"} 
                               for info in self.pending_orders.values())
            
            if qty == 0 and not pending_exit:
                log.info(f"Position for {symbol} closed externally or already reconciled")
                self._clear_position_state(symbol)

    def _should_shutdown_for_day(self) -> bool:
        if not Config.AUTO_SHUTDOWN_AFTER_CLOSE:
            return False

        if self.pending_orders:
            return False

        if self.positions:
            return False

        if self._market_is_open():
            return False

        return self._minutes_to_close() <= 0

    def try_entry(self, current_hhmm: int | None = None):
        if self.safe_mode:
            log.warning("Safe mode active: new entries disabled")
            return

        if not Config.ENABLE_NEW_ENTRIES:
            log.warning("Kill switch active: new entries disabled")
            return

        if not self._market_is_open():
            log.info("Skipping entries: market is closed")
            return

        # 0. META-RISK ENGINE (Total At Risk)
        total_at_risk = 0.0
        for pos in self.positions.values():
            entry_price = float(pos.get("entry_price", 0))
            current_price = self.data.get_latest_mid_price(pos["symbol"]) or entry_price
            qty = float(pos.get("qty", 0))
            # Risk is defined as the distance between current price and stop loss (or current loss)
            # Simplified: Risk is current equity exposure * stop_loss_pct
            total_at_risk += (qty * current_price) * (Config.STOP_LOSS_PCT / 100.0)

        if not self.risk.can_trade(is_exit=False, current_hhmm=current_hhmm, total_at_risk=total_at_risk, timeframe=self.timeframe):
            log.info("Risk rules block new entries")
            return

        # 4. Global Equity Check
        account = self.broker.get_account()
        current_equity = float(getattr(account, "equity", Config.STARTING_EQUITY))
        if not self.risk.can_trade(is_exit=False, current_hhmm=current_hhmm, current_equity=current_equity, total_at_risk=total_at_risk, timeframe=self.timeframe):
            log.warning(f"Risk rules (Equity/Drawdown) block new entries. Equity: ${current_equity:.2f}")
            return

        if self._minutes_to_close() <= 10:
            log.info("Skipping entries: too close to end of trading window")
            return

        open_positions_count = self.broker.get_open_positions_count()
        if open_positions_count >= Config.MAX_OPEN_POSITIONS:
            log.info(f"Max open positions reached ({open_positions_count})")
            return

        # 4.5. Market Regime Filter
        market_regime, index_30m_return = self.data.get_market_regime("SPY")
        log.info(f"Current Market Regime: {market_regime} | SPY 30m Change: {index_30m_return:.2f}%")

        ranked_candidates = self.scanner.get_ranked_candidates(self.dynamic_config)
        log.info(
            "Scanner ranked candidates: "
            + ", ".join(f"{symbol}={momentum:.4%}" for symbol, momentum in ranked_candidates)
        )

        # Speed Optimization: Parallel Candidate Evaluation
        eval_tasks = []
        # Limit the number of candidates we evaluate in parallel for speed and API limits
        max_eval = getattr(Config, "MAX_CANDIDATE_EVALUATION", 20)
        candidates_to_eval = ranked_candidates[:max_eval]

        async def evaluate_all():
            tasks = [self._async_evaluate_symbol_entry(s, m, current_hhmm, total_at_risk, current_equity) for s, m in candidates_to_eval]
            return await asyncio.gather(*tasks)

        try:
            eval_results = asyncio.run(evaluate_all())
        except Exception as e:
            log.error(f"Error in parallel entry evaluation: {e}")
            eval_results = []

        for symbol, action, reason, strength, last_indicators, is_partial_entry in eval_results:
            if action is None:
                continue

            momentum = next((m for s, m in candidates_to_eval if s == symbol), 0.0)
            
            # --- Continue with Entry Logic for the first successful candidate ---
            # Re-check limits before each entry execution
            open_positions_count = self.broker.get_open_positions_count()
            if open_positions_count >= Config.MAX_OPEN_POSITIONS:
                log.info(f"Max open positions reached ({open_positions_count}) during parallel execution")
                break

            # ... existing entry execution logic follows ...

            # bars is now fetched within _evaluate_symbol_entry, so we don't need to re-fetch most things.
            # But we check account limits again as they might have changed between parallel evals
            account = self.broker.get_account()
            current_equity = float(getattr(account, "equity", Config.STARTING_EQUITY))
            
            allowed, live_reason = self._symbol_allowed_for_live(symbol)
            if not allowed:
                continue

            # We need bars for the remaining logic below (like _calc_qty if it uses ATR)
            # Fetching once more is fast if cached or using latest_price
            lookback_minutes = 30
            if self.timeframe == "15Min": lookback_minutes = 150
            elif self.timeframe == "5Min": lookback_minutes = 75
            bars = self.data.get_recent_bars(symbol, minutes=lookback_minutes)
            
            latest_price = self.data.get_latest_mid_price(symbol)
            if not bars or not latest_price or latest_price <= 0:
                continue

            # --- Expert Tuning: Market Regime & Relative Strength ---
            symbol_30m_return = momentum * 100.0 # momentum is decimal change
            relative_strength = symbol_30m_return - index_30m_return
            
            if market_regime == "BEARISH" and action == "buy":
                log.info(f"Skipping {symbol}: BEARISH market regime blocks long entries.")
                continue
            if market_regime == "BULLISH" and action == "short":
                log.info(f"Skipping {symbol}: BULLISH market regime blocks short entries.")
                continue
            
            # Fast Path Execution: Expedite if confidence is very high
            fast_path = False
            if Config.FAST_PATH_ENABLED and strength >= 0.9:
                log.info(f"🚀 FAST PATH ACTIVATED for {symbol} (Strength: {strength:.2f})")
                fast_path = True
            
            # Relative Strength Filtering:
            # Long: Symbol should be stronger than SPY
            # Short: Symbol should be weaker than SPY
            if not is_partial_entry and not fast_path:
                if action == "buy" and relative_strength < 0.2:
                    log.info(f"Skipping {symbol}: Weak relative strength ({relative_strength:.2f}%) vs SPY.")
                    continue
                if action == "short" and relative_strength > -0.2:
                    log.info(f"Skipping {symbol}: Weak relative weakness ({relative_strength:.2f}%) vs SPY.")
                    continue

            # Risk/Reward Enforcement
            sl_pct = (self.dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) if self.dynamic_config else Config.STOP_LOSS_PCT) / 100.0
            tp_pct = (self.dynamic_config.get("take_profit_pct", Config.TAKE_PROFIT_PCT) if self.dynamic_config else Config.TAKE_PROFIT_PCT) / 100.0
            rr_ratio = tp_pct / sl_pct if sl_pct > 0 else 0
            if rr_ratio < Config.MIN_RISK_REWARD_RATIO:
                log.info(f"Skipping {symbol}: Risk/Reward ratio {rr_ratio:.2f} is below minimum {Config.MIN_RISK_REWARD_RATIO}")
                continue
                
            # Increase threshold for NEUTRAL market to avoid chop
            effective_min_strength = 0.70 if market_regime == "NEUTRAL" else 0.60
            if action == "short":
                effective_min_strength += 0.05 # Higher bar for shorts
            
            # ELITE FEATURE: 'The Slicer' (Performance Self-Throttling)
            slicer_data = self.analyzer.get_performance_slicer(days=30)
            if slicer_data:
                current_hour = datetime.now().hour
                current_day = datetime.now().weekday()
                
                # Check if we are in a 'Dead Zone'
                is_power_hour = current_hour in slicer_data.get("power_hours", [])
                is_power_day = current_day in slicer_data.get("power_days", [])
                
                if not is_power_hour or not is_power_day:
                    effective_min_strength += 0.10 # Raise the bar in dead zones
                    log.info(f"Slicer: Dead Zone detected (Hour {current_hour}, Day {current_day}). Raising threshold to {effective_min_strength}")
                else:
                    log.info(f"Slicer: POWER ZONE active. Maintaining optimal threshold {effective_min_strength}")

            # 4.6. Time-Based Chop Zone Filter (9:30 - 10:30 AM EST)
            # Increase strength requirements during high-volatility market open
            if current_hhmm and 930 <= current_hhmm <= 1030:
                effective_min_strength += 0.10
                log.info(f"Market open 'Chop Zone' active. Minimum strength raised to {effective_min_strength}")
                
            if strength < effective_min_strength:
                log.info(f"Skipping {symbol}: {action} signal strength {strength} is below effective threshold {effective_min_strength}")
                continue

            # --- SIGNAL DELAY FILTER (Reject late signals) ---
            if Config.SIGNAL_DELAY_FILTER_SECONDS > 0:
                # Assuming bars[-1].timestamp exists or using now() - bar_time
                bar_time = bars[-1].timestamp
                from datetime import timezone
                if (datetime.now(timezone.utc) - bar_time).total_seconds() > Config.SIGNAL_DELAY_FILTER_SECONDS:
                    log.info(f"Skipping {symbol}: Signal is too old ({Config.SIGNAL_DELAY_FILTER_SECONDS}s delay limit).")
                    continue

            # --- DECISION DELAY SYSTEM ---
            if Config.DECISION_DELAY_MINS > 0:
                delay_key = f"delay_{symbol}_{action}"
                last_seen = self.state.get("decision_delays", {}).get(delay_key)
                if not last_seen:
                    log.info(f"Signal for {symbol} {action} detected. Delaying for {Config.DECISION_DELAY_MINS}m for confirmation.")
                    delays = self.state.get("decision_delays", {})
                    delays[delay_key] = datetime.now().isoformat()
                    self.state["decision_delays"] = delays
                    self._save_state()
                    continue
                else:
                    last_seen_dt = datetime.fromisoformat(last_seen)
                    elapsed = (datetime.now() - last_seen_dt).total_seconds() / 60.0
                    if elapsed < Config.DECISION_DELAY_MINS:
                        log.info(f"Waiting for decision delay on {symbol} {action} ({elapsed:.1f}/{Config.DECISION_DELAY_MINS}m)")
                        continue
                    else:
                        # Clear delay after it passes
                        delays = self.state.get("decision_delays", {})
                        delays.pop(delay_key, None)
                        self.state["decision_delays"] = delays
                        self._save_state()
                        log.info(f"Decision delay passed for {symbol} {action}. Proceeding.")

            # --- MANUAL APPROVAL MODE ---
            if Config.MANUAL_APPROVAL_MODE:
                approval_id = f"approve_{symbol}_{action}_{datetime.now().strftime('%Y%m%d%H%M')}"
                if not self.risk.seen_alert(approval_id):
                    msg = f"🔔 MANUAL APPROVAL REQUIRED\nBot wants to {action.upper()} {symbol}\nReason: {reason}\nStrength: {strength:.2f}\nUse Web HUD to approve."
                    log.info(msg)
                    send_notification(msg, title="Manual Approval Required")
                    self.risk.mark_alert_seen(approval_id)
                    continue
                else:
                    # In a real app, we'd check a "confirmed_approvals" list in state
                    # For now, if we already notified, we skip until manually cleared or implemented.
                    log.info(f"Waiting for manual approval for {symbol} {action}...")
                    continue

            # 3. AI Signal Verification (Final Check)
            if Config.ENABLE_AI_TRADE_FILTER and not fast_path:
                # Prepare indicators for AI analysis
                df = self.strategy._calculate_indicators(bars)
                last_indicators = df.iloc[-1].to_dict() if df is not None else {}
                if not self.ai.verify_trade_signal(symbol, reason, last_indicators):
                    log.info(f"Skipping {symbol}: AI rejected the {reason} signal")
                    continue

            latest_price = self.data.get_latest_mid_price(symbol)
            if not latest_price or latest_price <= 0:
                continue

            qty = self._calc_qty(latest_price, symbol, signal_strength=strength, indicators=last_indicators)
            if Config.ENABLE_PARTIAL_ENTRIES and not is_partial_entry:
                # First entry is partial
                qty = qty * (Config.PARTIAL_ENTRY_PCT / 100.0)
            elif is_partial_entry:
                # Scaling in: use the remaining or a smaller piece
                qty = qty * (Config.PARTIAL_ENTRY_PCT / 100.0)

            if qty <= 0:
                continue

            account_ok, account_reason = self._account_allows_new_position(latest_price, qty)
            if not account_ok:
                log.info(f"Skipping {symbol}: {account_reason}")
                continue

            try:
                limit_price = None
                stop_loss_price = None
                take_profit_price = None
                
                if Config.USE_LIMIT_ORDERS:
                    # For entry, use a very tight offset (e.g. 0.01% - 0.05%) to avoid slippage
                    offset = Config.LIMIT_OFFSET_PCT / 100.0
                    if action == "buy":
                        limit_price = latest_price * (1 + offset)
                    else:
                        limit_price = latest_price * (1 - offset)

                # Hard Stop-Loss and Take-Profit (Bracket Orders)
                sl_pct = (self.dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) if self.dynamic_config else Config.STOP_LOSS_PCT) / 100.0
                tp_pct = (self.dynamic_config.get("take_profit_pct", Config.TAKE_PROFIT_PCT) if self.dynamic_config else Config.TAKE_PROFIT_PCT) / 100.0
            
                # Risk Parity adjustment
                risk_parity_pct = self.risk.calculate_risk_parity_size(symbol, current_equity, bars)
                if Config.RISK_PARITY_ENABLED:
                    log.info(f"Risk Parity suggested size: {risk_parity_pct*100:.2f}% (Base: {Config.RISK_PCT_PER_TRADE}%)")
                    # We can either override qty here or use it to scale the base qty
                    scale_factor = risk_parity_pct / (Config.RISK_PCT_PER_TRADE / 100.0)
                    qty = qty * scale_factor
                    if qty <= 0: continue

                if action == "buy":
                    stop_loss_price = latest_price * (1 - sl_pct)
                    take_profit_price = latest_price * (1 + tp_pct)
                else:
                    stop_loss_price = latest_price * (1 + sl_pct)
                    take_profit_price = latest_price * (1 - tp_pct)

                if action == "buy":
                    order = self.broker.buy(symbol, qty, limit_price=limit_price, stop_loss_price=stop_loss_price, take_profit_price=take_profit_price)
                else:
                    order = self.broker.short(symbol, qty, limit_price=limit_price, stop_loss_price=stop_loss_price, take_profit_price=take_profit_price)

                oid = str(getattr(order, "id", None))
                self.state["pending_orders"][oid] = {
                    "symbol": symbol,
                    "side": action,
                    "submitted_at": self._now_ts(),
                    "entry_time": datetime.now().isoformat()
                }
                self.state.setdefault("last_order_statuses", {})[oid] = self._normalize_order_status(getattr(order, "status", None))
                self._save_state()
                
                # Audit Trail Log
                self.state_store.log_action(f"{action.upper()} ENTRY", f"symbol={symbol} qty={qty} reason={reason}")

                # Confidence and Trade Score
                from intelligence import ConfidenceEngine
                score_data = ConfidenceEngine.calculate_scores(bars, reason, self.risk)
                score = score_data.get("score", 0)

                self.trade_journal.record(
                    f"{action}_submitted",
                    {
                        "symbol": symbol,
                        "qty": qty,
                        "entry_est": latest_price,
                        "limit_price": limit_price,
                        "reason": reason,
                        "order_id": oid,
                        "context": {
                            "score": score,
                            "market_condition": market_regime
                        }
                    },
                )
                self._bump_summary("buys_submitted" if action == "buy" else "sells_submitted")
                
                # Requested Report Format: TRADE EXECUTED
                risk_amount = (qty * latest_price) * (sl_pct)
                risk_percent = sl_pct * 100
                
                report = [
                    "TRADE EXECUTED",
                    "",
                    f"Asset: {symbol}",
                    f"Type: {action.upper()}",
                    f"Strategy: {reason}",
                    "",
                    f"Entry: ${latest_price:.2f}",
                    f"Stop Loss: ${stop_loss_price:.2f}",
                    f"Take Profit: ${take_profit_price:.2f}",
                    "",
                    f"Risk: ${risk_amount:.2f} ({risk_percent:.2f}%)",
                    "",
                    f"Trade Score: {score}/100",
                    f"Market Condition: {market_regime}",
                    "",
                    "Reason:",
                    f"- {reason}"
                ]
                
                msg = "\n".join(report)
                log.info(f"{action.upper()} submitted | symbol={symbol} qty={qty} order_id={oid}")
                send_notification(msg, title=f"Trade Bot {action.upper()}")
                return # only one entry per loop
            except Exception as e:
                self._record_failure(f"{action.capitalize()} failed for {symbol}", e)

    def try_exit(self):
        if not self.positions:
            return

        if not self._market_is_open():
            return

        minutes_to_close = self._minutes_to_close()
        for symbol, pos_info in list(self.positions.items()):
            # 0. EOD Force Liquidation
            should_exit = False
            exit_reason = ""
            
            if Config.INTRA_DAY_MODE_ONLY and minutes_to_close <= Config.MARKET_CLOSE_LIQUIDATION_WINDOW_MINS:
                # Check if it's marked as long-term (we don't have this yet, but we'll exclude those if we had a flag)
                if not pos_info.get("long_term", False):
                    should_exit = True
                    exit_reason = f"EOD Liquidation ({minutes_to_close} mins to close)"

            # Check if there is already a pending exit order for this symbol
            if not should_exit and any(info.get("symbol") == symbol and info.get("side") in {"sell", "cover"} 
                   for info in self.pending_orders.values()):
                continue

            qty = self.broker.get_position_qty(symbol)
            if qty == 0:
                self._clear_position_state(symbol)
                continue

            # Scaling timeframe for multi-bot
            lookback_minutes = 30
            if self.timeframe == "15Min": lookback_minutes = 150
            elif self.timeframe == "5Min": lookback_minutes = 75
            
            bars = self.data.get_recent_bars(symbol, minutes=lookback_minutes) # Increased lookback for indicators
            latest_price = self.data.get_latest_mid_price(symbol)
            if not latest_price:
                continue

            # Update high/low since entry for trailing stop
            side = pos_info.get("side", "buy")
            current_extreme = pos_info.get("high_since_entry")
            if side == "buy":
                if current_extreme is None or latest_price > current_extreme:
                    pos_info["high_since_entry"] = latest_price
            else: # short
                # For shorts, "high_since_entry" actually stores the LOWest price seen
                if current_extreme is None or latest_price < current_extreme:
                    pos_info["high_since_entry"] = latest_price
            self._save_state()

            pos_info["sold_half"] = pos_info.get("sold_half", False) # Ensure key exists
            is_manual = pos_info.get("manual", False)
            
            entry_price = pos_info.get("entry_price", 0)
            pnl_dollars = 0
            if entry_price > 0:
                if side == "buy":
                    pnl_dollars = (latest_price - entry_price) * qty
                else: # short
                    pnl_dollars = (entry_price - latest_price) * qty

            # 1. Partial TP Rules (Dollar based)
            exit_qty = qty
            if not should_exit:
                # Last-hour greed reduction: if within 30 mins of close, take ANY profit
                if minutes_to_close <= 30 and pnl_dollars > 1.00:
                    should_exit = True
                    exit_reason = f"EOD_PROFIT_TAKE (PnL: ${pnl_dollars:.2f})"
                    exit_qty = qty
                elif side == "short" and pnl_dollars >= Config.SHORT_EXIT_PROFIT_DOLLARS:
                    should_exit = True
                    exit_reason = f"SHORT_TP_REACHED_{Config.SHORT_EXIT_PROFIT_DOLLARS}_DOLLARS (PnL: ${pnl_dollars:.2f})"
                    exit_qty = qty
                elif pnl_dollars >= Config.PARTIAL_TP2_DOLLARS:
                    should_exit = True
                    exit_reason = f"TP_REACHED_{Config.PARTIAL_TP2_DOLLARS}_DOLLARS (PnL: ${pnl_dollars:.2f})"
                    exit_qty = qty
                elif pnl_dollars >= Config.PARTIAL_TP1_DOLLARS and not pos_info.get("sold_half", False):
                    should_exit = True
                    exit_reason = f"TP_REACHED_{Config.PARTIAL_TP1_DOLLARS}_DOLLARS_PARTIAL (PnL: ${pnl_dollars:.2f})"
                    exit_qty = max(1, int(qty / 2))
                    pos_info["sold_half"] = True
                    self._save_state()
                else:
            # 2. Standard Exit Rules (should_sell)
                    # Convert entry_time string to datetime
                    entry_time_dt = None
                    if pos_info.get("entry_time"):
                        try:
                            entry_time_dt = datetime.fromisoformat(pos_info["entry_time"])
                        except Exception:
                            pass

                    should_exit, exit_reason, exit_fraction = self.strategy.should_sell(
                        entry_price, 
                        latest_price, 
                        bars, 
                        high_since_entry=pos_info["high_since_entry"],
                        side=side,
                        dynamic_config=self.dynamic_config,
                        is_manual=is_manual,
                        entry_time=entry_time_dt
                    )
                    exit_qty = max(1, int(qty * exit_fraction))
                    if exit_fraction < 1.0:
                        # Mark that we have already taken this partial TP to avoid re-triggering
                        if "TP 1" in exit_reason:
                            if pos_info.get("tp1_hit"): should_exit = False
                            else: pos_info["tp1_hit"] = True
                        elif "TP 2" in exit_reason:
                            if pos_info.get("tp2_hit"): should_exit = False
                            else: pos_info["tp2_hit"] = True
                        self._save_state()

            is_partial = (exit_qty < qty)

            if not should_exit:
                continue

            try:
                # Record cooldown
                self.risk.record_cooldown(symbol)
                
                # Exit with Market Order to ensure execution
                limit_price = None
                action = "sell" if side == "buy" else "cover"
                
                if exit_qty >= qty:
                    order = self.broker.sell_all(symbol, limit_price=limit_price)
                else:
                    # Partial exit
                    if action == "sell":
                        order = self.broker.sell(symbol, exit_qty, limit_price=limit_price)
                    else:
                        order = self.broker.cover(symbol, exit_qty, limit_price=limit_price)
                
                oid = str(getattr(order, "id", None))
                self.state["pending_orders"][oid] = {
                    "symbol": symbol,
                    "side": action,
                    "submitted_at": self._now_ts(),
                    "is_partial": is_partial
                }
                self._save_state()

                # Calculate PnL and R:R for TRADE CLOSED report
                final_pnl = 0.0
                achieved_rr = 0.0
                sl_val = (self.dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) if self.dynamic_config else Config.STOP_LOSS_PCT) / 100.0
                if entry_price > 0:
                    if side == "buy":
                        final_pnl = (latest_price - entry_price) * exit_qty
                        risk_val = entry_price * sl_val
                        achieved_rr = (latest_price - entry_price) / risk_val if risk_val > 0 else 0
                    else:
                        final_pnl = (entry_price - latest_price) * exit_qty
                        risk_val = entry_price * sl_val
                        achieved_rr = (entry_price - latest_price) / risk_val if risk_val > 0 else 0

                duration_str = "N/A"
                if entry_time_dt:
                    duration = datetime.now() - entry_time_dt
                    duration_str = str(duration).split('.')[0]

                score = pos_info.get("context", {}).get("score", 0)

                self.trade_journal.record(
                    f"{action}_submitted",
                    {
                        "symbol": symbol,
                        "exit_est": latest_price,
                        "reason": exit_reason,
                        "order_id": oid,
                        "pnl": final_pnl,
                        "rr_ratio": achieved_rr,
                        "duration": duration_str
                    },
                )
                self._bump_summary("sells_submitted" if action == "sell" else "buys_submitted")
                
                # Requested Report Format: TRADE CLOSED
                report = [
                    "TRADE CLOSED",
                    "",
                    f"Asset: {symbol}",
                    f"Result: {'WIN' if final_pnl > 0 else 'LOSS'}",
                    "",
                    f"Entry: ${entry_price:.2f}",
                    f"Exit: ${latest_price:.2f}",
                    "",
                    f"P/L: ${final_pnl:.2f}",
                    f"R:R Achieved: {achieved_rr:.2f}",
                    "",
                    f"Duration: {duration_str}",
                    "",
                    "Exit Reason:",
                    f"- {exit_reason}",
                    "",
                    f"Was this A+ setup? {'Yes' if score >= 90 else 'No'}"
                ]
                
                msg = "\n".join(report)
                log.info(f"{action.upper()} submitted | symbol={symbol} order_id={oid} reason={exit_reason}")
                send_notification(msg, title=f"Trade Bot {action.upper()}")
            except Exception as e:
                self._record_failure(f"Exit failed for {symbol}", e)
                if is_partial:
                    pos_info["sold_half"] = False
                self._save_state()

    def run(self, single_cycle: bool = False):
        # 1. License / Sharing Authorization Check
        try:
            from license_manager import LicenseManager
            LicenseManager.verify_license(store=self.state_store) # Remote check
            
            # Refresh internal state to pick up any license binding/status changes
            self.state = self.state_store.load()
            
            if self.state.get("license_revoked", False):
                log.critical("LICENSE HAS BEEN REVOKED. Terminating cycle for this user.")
                return # Exit the run cycle for this user
                
            if not self.state.get("sharing_authorized", False):
                # If not authorized, we check if the SHARING_ACTIVATION_KEY is provided.
                # Only the owner knows this key (MAKA-VALI-PRIME-2026).
                # New users CANNOT bypass this by just generating a local AUTH_TOKEN.
                log.warning(f"Bot sharing NOT AUTHORIZED for user {self.user.username if self.user else 'DEFAULT'}. Access Denied.")
                log.warning("Please contact the owner for the Sharing Activation Key.")
                
                # Check for interactive terminal to allow prompt authorization
                if sys.stdin.isatty():
                    try:
                        print(f"\n{'='*50}")
                        print(f"AUTHORIZATION REQUIRED FOR USER: {self.user.username.upper()}")
                        print(f"ID: {self.user.id}")
                        print(f"{'='*50}")
                        token = input(f"ENTER SHARING TOKEN TO AUTHORIZE: ").strip()
                        
                        # Verify against user's specific sharing_token or the Master Key
                        if token == Config.SHARING_ACTIVATION_KEY or (hasattr(self.user, 'sharing_token') and token == self.user.sharing_token):
                            self.state["sharing_authorized"] = True
                            self.state_store.save(self.state)
                            log.info(f"SUCCESS: User {self.user.username} has been AUTHORIZED via terminal.")
                            # Proceed with the run cycle
                            return self.run(single_cycle=single_cycle)
                        else:
                            log.error("INVALID TOKEN. Authorization failed.")
                    except EOFError:
                        pass
                
                if not single_cycle:
                    send_notification("Trade Bot startup blocked: Authorization Required", title="Security Alert")
                
                # In a real scenario, we might wait for input or a web trigger.
                # For now, we'll just skip to prevent unauthorized use of the bot source.
                if not single_cycle:
                    time.sleep(5)
                return # Exit the run cycle for this user
        except Exception as e:
            log.error(f"Error checking authorization: {e}")
            return # Exit the run cycle for this user

        if not single_cycle:
            msg = f"AutoTrader started for user: {self.user.username if self.user else 'DEFAULT'}"
            log.info(msg)
            send_notification(msg)
            log.info(
                f"Mode={'PAPER' if (self.user.alpaca_paper if self.user else Config.ALPACA_PAPER) else 'LIVE'} | "
                f"new_entries_enabled={Config.ENABLE_NEW_ENTRIES} | "
                f"max_spread_pct={Config.MAX_SPREAD_PCT} | "
                f"order_timeout_seconds={Config.ORDER_TIMEOUT_SECONDS} | "
                f"max_consecutive_failures={Config.MAX_CONSECUTIVE_FAILURES} | "
                f"auto_shutdown_after_close={Config.AUTO_SHUTDOWN_AFTER_CLOSE}"
            )
            self._log_startup_reconciliation()

        import importlib
        import strategy
        last_strategy_mtime = os.path.getmtime("strategy.py")
        last_update_check = 0
        last_license_check = time.time()
        last_log_submission = time.time() # Initial timestamp

        while True:
            try:
                # Periodic License Check
                if time.time() - last_license_check > Config.LICENSE_CHECK_INTERVAL_SECONDS:
                    from license_manager import LicenseManager
                    LicenseManager.verify_license()
                    last_license_check = time.time()

                # Check global enable switch and kill switch
                try:
                    state_raw = self.state_store.load()
                    if state_raw.get("kill_switch_active", False):
                        log.critical("KILL SWITCH IS ACTIVE. Bot will not trade.")
                        if not single_cycle:
                            self.sync_state()
                            time.sleep(60)
                            continue
                        else:
                            break

                    if not state_raw.get("enabled", True):
                        # If disabled, we still want to keep the UI informed and handle exits for safety,
                        # but we skip everything else.
                        self.sync_state()
                        time.sleep(10)
                        continue
                except Exception as e:
                    log.error(f"Error checking enabled status: {e}")

                # Periodic Auto-Update check (every 1 hour)
                if Config.ENABLE_AUTO_UPDATE and time.time() - last_update_check > 3600 and not single_cycle:
                    try:
                        if self.updater.check_for_updates():
                            log.info("Repository updated via git. Triggering reloads.")
                        last_update_check = time.time()
                    except Exception as e:
                        log.error(f"Auto-update failed: {e}")

                # Hot-reload logic
                current_strategy_mtime = os.path.getmtime("strategy.py")
                if current_strategy_mtime > last_strategy_mtime:
                    log.info("strategy.py changed, reloading...")
                    importlib.reload(strategy)
                    self.strategy = strategy.Strategy() # Re-instantiate if needed
                    last_strategy_mtime = current_strategy_mtime
                    if not single_cycle:
                        send_notification("New trading strategy detected and applied live!", title="Strategy Updated")

                self.sync_state()

                # Market clock for risk checks
                clock = self.broker.get_clock()
                current_hhmm = None
                if clock:
                    current_hhmm = int(clock.timestamp.strftime("%H%M"))

                self.try_exit()
                
                # --- GLOBAL NEWS FILTER CHECK ---
                from news_engine import NewsEngine
                safe, reason = NewsEngine.is_market_safe(None, self.broker)
                if not safe:
                    log.warning(f"Global News Filter Active: {reason}. Skipping entries.")
                else:
                    self.try_entry(current_hhmm=current_hhmm)

                # Periodic Auto-Withdrawal Check
                self._check_auto_withdrawal()
                    
                self._reset_failures()

                if single_cycle:
                    break

                # Periodic Log Submission to Central Server
                if Config.ENABLE_LOG_SUBMISSION and time.time() - last_log_submission > Config.SUBMIT_LOGS_EVERY_SECONDS:
                    log.info("Attempting to submit paper trading logs to central server...")
                    bot_id = self.user.username if self.user else os.getenv("USER", "bot_user")
                    if self.analyzer.submit_logs_to_central_server(bot_id):
                        last_log_submission = time.time()
                    else:
                        # Retry in 10 minutes if failed
                        last_log_submission = time.time() - Config.SUBMIT_LOGS_EVERY_SECONDS + 600

                # End of session logic (8:30 PM local time)
                report_time_hhmm = 2030
                if current_hhmm is not None and current_hhmm >= report_time_hhmm:
                    # We check if we already sent today's report
                    if self.summary_date != datetime.now().strftime("%Y-%m-%d"):
                        self.summary_date = datetime.now().strftime("%Y-%m-%d") # Reset for next day
                        
                        summary = self.risk.get_daily_summary()
                        pnl = summary.get("daily_pnl", 0.0)
                        trades = summary.get("trades_count", 0)
                        bot_id = self.user.username if self.user else os.getenv("USER", "bot_user")
                        msg = f"Trading day + Extended Session complete for {bot_id}. Final Daily PnL: ${pnl:.2f} | Trades: {trades}."
                        log.info(msg)
                        send_notification(msg, title="Daily Performance Report Triggered")

                        # Final Daily Report
                        try:
                            self._send_daily_report()
                        except Exception as e:
                            log.error(f"Daily report failed: {e}")

                        # Run Nightly Research before maintenance
                        try:
                            self.researcher.perform_internet_research()
                            # Perform Crypto Investment Scan after research
                            self.crypto_investor.scan_and_invest()
                            # Also perform backup after research
                            self.backup_mgr.create_backup()
                        except Exception as e:
                            log.error(f"Nightly Research or Backup failed: {e}")

                if self._should_shutdown_for_day():
                    summary = self.risk.get_daily_summary()
                    pnl = summary.get("daily_pnl", 0.0)
                    trades = summary.get("trades_count", 0)
                    bot_id = self.user.username if self.user else os.getenv("USER", "bot_user")
                    msg = f"Trading day complete for {bot_id}. Final Daily PnL: ${pnl:.2f} | Trades: {trades}. Shutting down."
                    log.info(msg)
                    send_notification(msg, title="Bot Shutdown")

                    # Final Daily Report
                    try:
                        self._send_daily_report()
                    except Exception as e:
                        log.error(f"Daily report failed: {e}")

                    # Run Nightly Research before final shutdown
                    try:
                        self.researcher.perform_internet_research()
                        # Perform Crypto Investment Scan after research
                        self.crypto_investor.scan_and_invest()
                        # Also perform backup after research
                        self.backup_mgr.create_backup()
                    except Exception as e:
                        log.error(f"Nightly Research or Backup failed: {e}")

                    break

            except Exception as e:
                self._record_failure("Main loop error", e)

            if single_cycle:
                break
            time.sleep(20)


if __name__ == "__main__":
    import os
    import subprocess
    
    # Start the Bot HUD Display
    hud_proc = None
    def start_hud():
        try:
            log.info("Starting Bot HUD Display (bot_display.py)...")
            # Log HUD output to a file for debugging
            hud_log = open("logs/bot_display.log", "a")
            return subprocess.Popen([sys.executable, "bot_display.py"], 
                                         stdout=hud_log, 
                                         stderr=hud_log)
        except Exception as e:
            log.error(f"Failed to start Bot HUD Display: {e}")
            return None

    hud_proc = start_hud()

    try:
        # Initialize DB in case it doesn't exist or is outdated
        with app.app_context():
            db.create_all()
        
        # Check for updates and update codebase if needed
        updater = AutoUpdater()
        if Config.ENABLE_AUTO_UPDATE:
            try:
                if updater.check_for_updates():
                    log.info("Update found on startup. Restarting to apply changes...")
                    os._exit(0) # launchd will restart
            except Exception as e:
                log.error(f"Startup auto-update failed: {e}")

        last_update_check = time.time()
        while True:
            # Ensure Bot HUD is running
            if hud_proc is None or hud_proc.poll() is not None:
                log.warning("Bot HUD Display not running. Restarting...")
                hud_proc = start_hud()

            with app.app_context():
                users = User.query.all()
                if not users:
                    # If no users yet, run with default credentials from .env
                    log.info("No users found in database. Running with default credentials.")
                    AutoTrader().run() # This might need a non-infinite run or we handle it differently
                    # For now, let's break or sleep to avoid infinite loop of no-users
                    time.sleep(60)
                    continue

                for user in users:
                    try:
                        log.info(f"Processing trading cycle for user: {user.username}")
                        trader = AutoTrader(user=user)
                        
                        # Run one cycle for this user
                        trader.run(single_cycle=True)
                        
                    except Exception as e:
                        log.error(f"Error processing user {user.username}: {e}")

            # Periodic Auto-Update check (every 1 hour)
            if Config.ENABLE_AUTO_UPDATE and time.time() - last_update_check > 3600:
                try:
                    if updater.check_for_updates():
                        log.info("New update found. Restarting to apply changes...")
                        os._exit(0) # launchd will restart
                    last_update_check = time.time()
                except Exception as e:
                    log.error(f"Auto-update failed: {e}")

            time.sleep(20)
    finally:
        if hud_proc:
            log.info("Shutting down Bot HUD Display...")
            hud_proc.terminate()
            try:
                hud_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                hud_proc.kill()