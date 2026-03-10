from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime

from bot_state import BotStateStore
from broker_alpaca import AlpacaBroker
from config import Config
from market_data import MarketDataClient
from risk import RiskManager
from scanner import Scanner
from strategy import Strategy
from performance import PerformanceAnalyzer
from trade_journal import TradeJournal
from notifications import send_notification

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


class AutoTrader:
    def __init__(self):
        self._validate_launch_mode()

        self.broker = AlpacaBroker()
        self.risk = RiskManager()
        self.scanner = Scanner()
        self.strategy = Strategy()
        self.data = MarketDataClient()
        self.state_store = BotStateStore(Config.BOT_STATE_FILE)
        self.trade_journal = TradeJournal(Config.TRADE_JOURNAL_FILE)
        self.analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
        self.state = self.state_store.load()
        self.consecutive_failures = 0
        self.safe_mode = False
        self.summary_date = datetime.now().strftime("%Y-%m-%d")
        self.daily_summary = self._default_daily_summary()

    @staticmethod
    def _validate_launch_mode():
        if not Config.ALPACA_PAPER:
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
        # Periodically analyze and adjust dynamic config
        if int(time.time()) % 3600 < 60: # once an hour roughly
             self.state["dynamic_config"] = self.analyzer.get_suggested_config(self.dynamic_config)
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

    @staticmethod
    def _now_ts() -> float:
        return time.time()

    @staticmethod
    def _elapsed_seconds(start_ts: float | None) -> float:
        if not start_ts:
            return 0.0
        return time.time() - float(start_ts)

    def _calc_qty(self, price: float) -> int:
        if price <= 0:
            return 0

        sl_pct = (self.dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT)) / 100.0
        risk_per_share = price * sl_pct
        if risk_per_share <= 0:
            return 0

        risk_amount = Config.RISK_PER_TRADE_DOLLARS
        if Config.USE_PERCENTAGE_RISK:
            acct = self.broker.get_account()
            equity = float(acct.equity)
            risk_amount = equity * (Config.RISK_PCT_PER_TRADE / 100.0)

        qty = int(risk_amount / risk_per_share)
        
        # Determine dynamic max position value
        max_pos_value = Config.MAX_POSITION_VALUE_DOLLARS
        if Config.USE_PERCENTAGE_RISK:
            acct = self.broker.get_account()
            equity = float(acct.equity)
            # If compounding, allow position value up to 2x the normal cap or 25% of equity, whichever is higher
            max_pos_value = max(Config.MAX_POSITION_VALUE_DOLLARS, equity * 0.25)

        max_by_position_value = int(max_pos_value / price)
        qty = min(qty, max_by_position_value) if max_by_position_value > 0 else 0
        return max(qty, 1) if qty > 0 else 0

    def _account_allows_new_position(self, price: float, qty: int) -> tuple[bool, str]:
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
            return

        for pos in broker_positions:
            symbol = pos.symbol
            if symbol not in self.positions:
                self.state["positions"][symbol] = {
                    "entry_price": float(pos.avg_entry_price),
                    "high_since_entry": float(pos.avg_entry_price),
                    "side": "buy" if float(pos.qty) > 0 else "short"
                }
                log.info(f"Adopted existing position | symbol={symbol} side={self.state['positions'][symbol]['side']}")

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
                filled_qty = getattr(order, "filled_qty", None)

                if side_info in {"buy", "short"}: # Entries
                    self.state["positions"][symbol] = {
                        "entry_price": filled_avg_price,
                        "high_since_entry": filled_avg_price,
                        "side": side_info
                    }
                    msg = f"{side_info.upper()} filled | {symbol} | Price: ${filled_avg_price:.2f} | Qty: {filled_qty}"
                    log.info(msg)
                    send_notification(msg, title=f"Trade {side_info.upper()} Filled")
                    self.trade_journal.record(
                        f"{side_info}_filled",
                        {
                            "symbol": symbol,
                            "order_id": oid,
                            "filled_avg_price": filled_avg_price,
                            "filled_qty": filled_qty,
                        },
                    )
                    self._bump_summary("buys_filled" if side_info == "buy" else "sells_filled")
                    self.risk.record_trade(0.0)
                else: # Exits (sell/cover)
                    pos_info = self.positions.get(symbol, {})
                    entry_price = pos_info.get("entry_price", 0.0)
                    if side_info == "sell":
                        pnl = (filled_avg_price - entry_price) * float(filled_qty or 0)
                    else: # cover
                        pnl = (entry_price - filled_avg_price) * float(filled_qty or 0)

                    msg = f"{side_info.upper()} filled | {symbol} | Price: ${filled_avg_price:.2f} | Qty: {filled_qty} | PnL: ${pnl:.2f}"
                    log.info(msg)
                    send_notification(msg, title=f"Trade {side_info.upper()} Filled")
                    self.trade_journal.record(
                        f"{side_info}_filled",
                        {
                            "symbol": symbol,
                            "order_id": oid,
                            "filled_avg_price": filled_avg_price,
                            "filled_qty": filled_qty,
                            "pnl": pnl,
                        },
                    )
                    self._bump_summary("sells_filled" if side_info == "sell" else "buys_filled")
                    self.risk.record_trade(pnl)
                    if symbol in self.state["positions"]:
                        del self.state["positions"][symbol]

                self._clear_pending_order(oid)
            
            elif status in {"canceled", "expired", "rejected", "stopped", "suspended"}:
                log.warning(f"Pending order {oid} failed with status: {status}")
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

        if self._minutes_to_close() <= 10:
            log.info("Skipping entries: too close to end of trading window")
            return

        open_positions_count = self.broker.get_open_positions_count()
        if open_positions_count >= Config.MAX_OPEN_POSITIONS:
            log.info(f"Max open positions reached ({open_positions_count})")
            return

        ranked_candidates = self.scanner.get_ranked_candidates()
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

            allowed, live_reason = self._symbol_allowed_for_live(symbol)
            if not allowed:
                continue

            spread_pct = self.data.get_spread_pct(symbol)
            max_spread = self.dynamic_config.get("max_spread_pct", Config.MAX_SPREAD_PCT)
            if spread_pct is None or spread_pct > max_spread:
                continue

            bars = self.data.get_recent_bars(symbol, minutes=30)
            should_buy, buy_reason = self.strategy.should_buy(bars)
            should_short, short_reason = self.strategy.should_short(bars)
            
            action = None
            reason = None
            if should_buy:
                action = "buy"
                reason = buy_reason
            elif should_short:
                action = "short"
                reason = short_reason
            
            if not action:
                continue

            latest_price = self.data.get_latest_mid_price(symbol)
            if not latest_price or latest_price <= 0:
                continue

            qty = self._calc_qty(latest_price)
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

            should_exit, exit_reason = self.strategy.should_sell(
                pos_info["entry_price"], 
                latest_price, 
                bars, 
                high_since_entry=pos_info["high_since_entry"],
                side=side,
                dynamic_config=self.dynamic_config
            )

            if not should_exit:
                continue

            try:
                limit_price = None
                if Config.USE_LIMIT_ORDERS:
                    offset = Config.LIMIT_OFFSET_PCT / 100.0
                    limit_price = latest_price * (1 - offset) if side == "buy" else latest_price * (1 + offset)

                action = "sell" if side == "buy" else "cover"
                order = self.broker.sell_all(symbol, limit_price=limit_price)
                
                oid = str(getattr(order, "id", None))
                self.state["pending_orders"][oid] = {
                    "symbol": symbol,
                    "side": action,
                    "submitted_at": self._now_ts()
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

    def run(self):
        msg = "AutoTrader started"
        log.info(msg)
        send_notification(msg)
        log.info(
            f"Mode={'PAPER' if Config.ALPACA_PAPER else 'LIVE'} | "
            f"new_entries_enabled={Config.ENABLE_NEW_ENTRIES} | "
            f"max_spread_pct={Config.MAX_SPREAD_PCT} | "
            f"order_timeout_seconds={Config.ORDER_TIMEOUT_SECONDS} | "
            f"max_consecutive_failures={Config.MAX_CONSECUTIVE_FAILURES} | "
            f"auto_shutdown_after_close={Config.AUTO_SHUTDOWN_AFTER_CLOSE}"
        )
        self._log_startup_reconciliation()

        while True:
            try:
                self.sync_state()

                # Market clock for risk checks
                clock = self.broker.get_clock()
                current_hhmm = None
                if clock:
                    current_hhmm = int(clock.timestamp.strftime("%H%M"))

                self.try_exit()
                self.try_entry(current_hhmm=current_hhmm)
                self._reset_failures()

                if self._should_shutdown_for_day():
                    summary = self.risk.get_daily_summary()
                    pnl = summary.get("daily_pnl", 0.0)
                    trades = summary.get("trades_count", 0)
                    msg = f"Trading day complete. Final Daily PnL: ${pnl:.2f} | Trades: {trades}. Shutting down."
                    log.info(msg)
                    send_notification(msg, title="Bot Shutdown")
                    break

            except Exception as e:
                self._record_failure("Main loop error", e)

            time.sleep(20)


if __name__ == "__main__":
    AutoTrader().run()