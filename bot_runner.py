from __future__ import annotations

import importlib
import json
import logging
import os
import sys
import time
from datetime import datetime

from flask import Flask

from bot_state import BotStateStore
from broker_alpaca import AlpacaBroker
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

log = logging.getLogger("autobot")

# We need a dummy flask app context for DB access
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


class AutoTrader:
    def __init__(self, user: User | None = None):
        self.user = user
        self._validate_launch_mode()

        if user and user.alpaca_key and user.alpaca_secret:
            self.broker = AlpacaBroker(
                key=user.alpaca_key,
                secret=user.alpaca_secret,
                paper=user.alpaca_paper
            )
            user_id = user.id
        else:
            self.broker = AlpacaBroker()
            user_id = None

        self.risk = RiskManager(user_id=user_id)
        self.scanner = Scanner()
        self.strategy = Strategy()
        self.data = MarketDataClient()
        
        state_path = Config.BOT_STATE_FILE
        journal_path = Config.TRADE_JOURNAL_FILE
        if user_id:
            state_path = os.path.join(Config.LOG_DIR, f"bot_state_user_{user_id}.json")
            journal_path = os.path.join(Config.LOG_DIR, f"trade_journal_user_{user_id}.jsonl")

        self.state_store = BotStateStore(state_path)
        self.trade_journal = TradeJournal(journal_path)
        self.analyzer = PerformanceAnalyzer(journal_path)
        self.learning = LearningEngine(journal_path)
        self.ai = AIEngine()
        self.researcher = ResearchEngine()
        self.backup_mgr = BackupManager()
        self.updater = AutoUpdater()
        self.state = self.state_store.load()
        self.consecutive_failures = 0
        self.safe_mode = False
        self.summary_date = datetime.now().strftime("%Y-%m-%d")
        self.daily_summary = self._default_daily_summary()

    def _validate_launch_mode(self):
        paper = self.user.alpaca_paper if self.user else Config.ALPACA_PAPER
        if not paper:
            required_ack = "I_UNDERSTAND_THIS_IS_REAL_MONEY"
            if Config.LIVE_TRADING_ACKNOWLEDGED != required_ack:
                raise RuntimeError(
                    "Live trading blocked. Set LIVE_TRADING_ACKNOWLEDGED="
                    "I_UNDERSTAND_THIS_IS_REAL_MONEY to enable live mode."
                )

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
        report = analyzer.generate_report(days=1)
        log.info("Sending daily performance report...")
        send_notification(report, title="📈 Daily Performance Summary")

    @staticmethod
    def _now_ts() -> float:
        return time.time()

    @staticmethod
    def _elapsed_seconds(start_ts: float | None) -> float:
        if not start_ts:
            return 0.0
        return time.time() - float(start_ts)

    def _calc_qty(self, price: float, symbol: str, signal_strength: float = 1.0) -> float:
        if price <= 0:
            return 0.0

        is_crypto = "/" in symbol or any(c in symbol for c in ["BTC", "ETH", "SOL", "LTC"])
        
        sl_pct = (self.dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT)) / 100.0
        risk_per_share = price * sl_pct
        if risk_per_share <= 0:
            return 0.0

        risk_amount = Config.RISK_PER_TRADE_DOLLARS
        if Config.USE_PERCENTAGE_RISK:
            acct = self.broker.get_account()
            equity = float(acct.equity)
            
            # Kelly Criterion Integration
            perf = self.dynamic_config.get("symbol_performance", {}).get(symbol, {})
            # Use general stats or default if no symbol specific stats
            win_rate = 0.55 # Default assumption
            win_loss_ratio = 1.5 # Default 1.5:1
            
            # Adjust based on learning engine history if available
            if perf.get("count", 0) >= 5:
                # Real data available for this symbol
                # This is simplified; real logic would track win_rate and avg_win/avg_loss
                pass 
                
            kelly_pct = self.risk.calculate_kelly_size(win_rate, win_loss_ratio, equity)
            risk_amount = equity * kelly_pct
            log.info(f"Kelly sizing for {symbol}: {kelly_pct*100:.2f}% risk (${risk_amount:.2f})")

        # Scale risk based on signal strength (Tiered Aggression)
        risk_amount = risk_amount * signal_strength

        qty = risk_amount / risk_per_share
        
        # Determine dynamic max position value
        max_pos_value = Config.MAX_POSITION_VALUE_DOLLARS
        if Config.USE_PERCENTAGE_RISK:
            # Removed overly aggressive compounding to ensure safety
            max_pos_value = Config.MAX_POSITION_VALUE_DOLLARS

        max_by_position_value = max_pos_value / price
        qty = min(qty, max_by_position_value) if max_by_position_value > 0 else 0
        
        if not is_crypto:
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

        if not self.risk.can_trade(is_exit=False, current_hhmm=current_hhmm):
            log.info("Risk rules block new entries")
            return

        # 4. Global Equity Check
        account = self.broker.get_account()
        current_equity = float(getattr(account, "equity", Config.STARTING_EQUITY))
        if not self.risk.can_trade(is_exit=False, current_hhmm=current_hhmm, current_equity=current_equity):
            log.warning(f"Risk rules (Equity/Drawdown) block new entries. Equity: ${current_equity:.2f}")
            return

        if self._minutes_to_close() <= 10:
            log.info("Skipping entries: too close to end of trading window")
            return

        open_positions_count = self.broker.get_open_positions_count()
        if open_positions_count >= Config.MAX_OPEN_POSITIONS:
            log.info(f"Max open positions reached ({open_positions_count})")
            return

        ranked_candidates = self.scanner.get_ranked_candidates(self.dynamic_config)
        log.info(
            "Scanner ranked candidates: "
            + ", ".join(f"{symbol}={momentum:.4%}" for symbol, momentum in ranked_candidates)
        )

        for symbol, momentum in ranked_candidates:
            if symbol in self.positions:
                continue
            
            # Check if there is already a pending order for this symbol
            if any(info.get("symbol") == symbol for info in self.pending_orders.values()):
                continue

            # 5. Sector/Diversity Check
            if not self.risk.can_trade(is_exit=False, current_hhmm=current_hhmm, symbol=symbol, current_equity=current_equity):
                log.info(f"Skipping {symbol}: Sector limit reached or Portfolio too concentrated.")
                continue

            allowed, live_reason = self._symbol_allowed_for_live(symbol)
            if not allowed:
                continue

            spread_pct = self.data.get_spread_pct(symbol)
            max_spread = self.dynamic_config.get("max_spread_pct", Config.MAX_SPREAD_PCT)
            if spread_pct is None or spread_pct > max_spread:
                continue

            bars = self.data.get_recent_bars(symbol, minutes=30)
            
            # News Awareness Filter
            if Config.ENABLE_NEWS_FILTER:
                news = self.data.get_news(symbol, days=1)
                # 1. Rule-based filter
                if not self.strategy.is_news_safe(symbol, self.data, news_list=news):
                    log.info(f"Skipping {symbol}: high-impact news or excessive volatility detected (Rule-based)")
                    continue
                
                # 2. AI-based Sentiment Filter
                if Config.AI_PROVIDER and Config.OPENAI_API_KEY:
                    headlines = [n.headline for n in news]
                    sentiment_score = self.ai.analyze_trade_sentiment(symbol, headlines)
                    log.info(f"AI Sentiment for {symbol}: {sentiment_score:.2f}")
                    if sentiment_score < -0.3: # Bearish threshold
                        log.info(f"Skipping {symbol}: AI detected bearish sentiment ({sentiment_score:.2f})")
                        continue

            should_buy, buy_reason, buy_strength = self.strategy.should_buy(bars, self.dynamic_config)
            should_short, short_reason, short_strength = self.strategy.should_short(bars, self.dynamic_config)
            
            action = None
            reason = None
            strength = 0.0
            if should_buy:
                action = "buy"
                reason = buy_reason
                strength = buy_strength
            elif should_short:
                action = "short"
                reason = short_reason
                strength = short_strength
            
            if not action:
                continue

            # Minimum Signal Strength Threshold to avoid weak setups
            min_strength = 0.60 if action == "buy" else 0.65 # Lowered from 0.75/0.8 for more activity
            if strength < min_strength:
                log.info(f"Skipping {symbol}: {action} signal strength {strength} is below threshold {min_strength}")
                continue

            # 3. AI Signal Verification (Final Check)
            if Config.ENABLE_AI_TRADE_FILTER:
                # Prepare indicators for AI analysis
                df = self.strategy._calculate_indicators(bars)
                last_indicators = df.iloc[-1].to_dict() if df is not None else {}
                if not self.ai.verify_trade_signal(symbol, reason, last_indicators):
                    log.info(f"Skipping {symbol}: AI rejected the {reason} signal")
                    continue

            latest_price = self.data.get_latest_mid_price(symbol)
            if not latest_price or latest_price <= 0:
                continue

            qty = self._calc_qty(latest_price, symbol, signal_strength=strength)
            if qty <= 0:
                continue

            account_ok, account_reason = self._account_allows_new_position(latest_price, qty)
            if not account_ok:
                log.info(f"Skipping {symbol}: {account_reason}")
                continue

            try:
                limit_price = None
                if Config.USE_LIMIT_ORDERS:
                    offset = Config.LIMIT_OFFSET_PCT / 100.0
                    limit_price = latest_price * (1 + offset) if action == "buy" else latest_price * (1 - offset)

                if action == "buy":
                    order = self.broker.buy(symbol, qty, limit_price=limit_price)
                else:
                    order = self.broker.short(symbol, qty, limit_price=limit_price)

                oid = str(getattr(order, "id", None))
                self.state["pending_orders"][oid] = {
                    "symbol": symbol,
                    "side": action,
                    "submitted_at": self._now_ts()
                }
                self.state.setdefault("last_order_statuses", {})[oid] = self._normalize_order_status(getattr(order, "status", None))
                self._save_state()

                self.trade_journal.record(
                    f"{action}_submitted",
                    {
                        "symbol": symbol,
                        "qty": qty,
                        "entry_est": latest_price,
                        "limit_price": limit_price,
                        "reason": reason,
                        "order_id": oid,
                    },
                )
                self._bump_summary("buys_submitted" if action == "buy" else "sells_submitted")
                msg = f"{action.upper()} submitted | symbol={symbol} qty={qty} order_id={oid}"
                log.info(msg)
                send_notification(msg, title=f"Trade Bot {action.upper()}")
                return # only one entry per loop
            except Exception as e:
                self._record_failure(f"{action.capitalize()} failed for {symbol}", e)

    def try_exit(self):
        if not self.positions:
            return

        if not self._market_is_open():
            return

        for symbol, pos_info in list(self.positions.items()):
            # Check if there is already a pending exit order for this symbol
            if any(info.get("symbol") == symbol and info.get("side") in {"sell", "cover"} 
                   for info in self.pending_orders.values()):
                continue

            qty = self.broker.get_position_qty(symbol)
            if qty == 0:
                self._clear_position_state(symbol)
                continue

            bars = self.data.get_recent_bars(symbol, minutes=10)
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
            if pnl_dollars >= Config.PARTIAL_TP2_DOLLARS:
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
                should_exit, exit_reason = self.strategy.should_sell(
                    entry_price, 
                    latest_price, 
                    bars, 
                    high_since_entry=pos_info["high_since_entry"],
                    side=side,
                    dynamic_config=self.dynamic_config,
                    is_manual=is_manual
                )
                exit_qty = qty

            is_partial = (exit_qty < qty)

            if not should_exit:
                continue

            try:
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

                self.trade_journal.record(
                    f"{action}_submitted",
                    {
                        "symbol": symbol,
                        "exit_est": latest_price,
                        "reason": exit_reason,
                        "order_id": oid,
                    },
                )
                self._bump_summary("sells_submitted" if action == "sell" else "buys_submitted")
                msg = f"{action.upper()} submitted | symbol={symbol} order_id={oid} reason={exit_reason}"
                log.info(msg)
                send_notification(msg, title=f"Trade Bot {action.upper()}")
            except Exception as e:
                self._record_failure(f"Exit failed for {symbol}", e)
                if is_partial:
                    pos_info["sold_half"] = False
                self._save_state()

    def run(self, single_cycle: bool = False):
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
        last_log_submission = time.time() # Initial timestamp

        while True:
            try:
                # Check global enable switch
                try:
                    state_raw = self.state_store.load()
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
                self.try_entry(current_hhmm=current_hhmm)
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

                if self._should_shutdown_for_day():
                    summary = self.risk.get_daily_summary()
                    pnl = summary.get("daily_pnl", 0.0)
                    trades = summary.get("trades_count", 0)
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
                updater.check_for_updates()
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
                    updater.check_for_updates()
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