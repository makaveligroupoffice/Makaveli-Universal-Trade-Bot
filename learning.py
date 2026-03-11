import json
import logging
import os
from datetime import datetime, timedelta
from config import Config
from notifications import send_notification
from market_data import MarketDataClient
from strategy import Strategy
from universe import DEFAULT_UNIVERSE

log = logging.getLogger("autobot")

class MarketResearcher:
    def __init__(self, dynamic_config: dict):
        self.md = MarketDataClient()
        self.dynamic_config = dynamic_config

    def perform_nightly_research(self):
        """Analyze recent market data for the entire universe and find optimal parameters."""
        log.info("Starting nightly market research...")
        
        results = []
        for symbol in DEFAULT_UNIVERSE:
            bars = self.md.get_bars_for_research(symbol, days=2)
            if len(bars) < 50:
                continue
            
            # Simulate strategy on these bars
            win_count = 0
            loss_count = 0
            pnl_total = 0
            
            # Very simple backtest simulation
            for i in range(20, len(bars) - 20):
                window = bars[i-20:i]
                should_buy, _ = Strategy.should_buy(window, self.dynamic_config)
                
                if should_buy:
                    entry_price = float(bars[i].open)
                    # Look ahead for outcome
                    max_future = 0
                    min_future = 999999
                    exit_price = entry_price
                    
                    for j in range(i+1, min(i+60, len(bars))):
                        future_price = float(bars[j].close)
                        max_future = max(max_future, float(bars[j].high))
                        min_future = min(min_future, float(bars[j].low))
                        
                        # Check exit logic
                        should_sell, _ = Strategy.should_sell(entry_price, future_price, bars[j-20:j], max_future, "buy", self.dynamic_config)
                        if should_sell:
                            exit_price = future_price
                            break
                    
                    pnl = exit_price - entry_price
                    pnl_total += pnl
                    if pnl > 0: win_count += 1
                    else: loss_count += 1

            results.append({
                "symbol": symbol,
                "win_rate": win_count / (win_count + loss_count) if (win_count + loss_count) > 0 else 0,
                "total_pnl": pnl_total
            })

        # Update dynamic config based on global performance
        overall_win_rate = sum(r["win_rate"] for r in results) / len(results) if results else 0
        
        updates = {}
        if overall_win_rate < 0.50:
            updates["min_rvol"] = min(self.dynamic_config.get("min_rvol", 1.8) + 0.1, 2.5)
            log.info(f"Nightly Research: Win rate {overall_win_rate:.2f} was low, increasing min_rvol to {updates['min_rvol']}")
        elif overall_win_rate > 0.70:
            updates["min_rvol"] = max(self.dynamic_config.get("min_rvol", 1.8) - 0.05, 1.2)
            log.info(f"Nightly Research: Win rate {overall_win_rate:.2f} was high, slightly lowering min_rvol to {updates['min_rvol']}")

        if updates:
            send_notification(f"🌙 Nightly Research Complete: Analyzed {len(results)} stocks. Strategy evolved based on broader market patterns.")
            return updates
        
        return {}

class LearningEngine:
    def __init__(self, journal_path: str, model_path: str = "logs/learned_model.json"):
        self.journal_path = journal_path
        self.model_path = model_path
        self.state = self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, "r") as f:
                    return json.load(f)
            except:
                pass
        return {
            "stop_loss_pct": Config.STOP_LOSS_PCT,
            "take_profit_pct": Config.TAKE_PROFIT_PCT,
            "min_rvol": 1.8,
            "symbol_performance": {},
            "last_optimized": None
        }

    def _save_model(self):
        try:
            with open(self.model_path, "w") as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save learned model: {e}")

    def evolve(self):
        """Analyze history and update internal parameters."""
        if not os.path.exists(self.journal_path):
            return

        trades = []
        try:
            with open(self.journal_path, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("event_type") == "sell_filled":
                        trades.append(entry)
        except:
            return

        if len(trades) < 5:
            return # Not enough data to evolve yet

        # 1. Symbol Evolution: Identify winners and losers
        perf = {}
        for t in trades:
            sym = t["symbol"]
            pnl = t.get("pnl", 0)
            if sym not in perf:
                perf[sym] = {"count": 0, "pnl": 0}
            perf[sym]["count"] += 1
            perf[sym]["pnl"] += pnl
        
        self.state["symbol_performance"] = perf

        # 2. Threshold Evolution: Optimize SL/TP
        win_rate = sum(1 for t in trades[-20:] if t.get("pnl", 0) > 0) / min(len(trades), 20)
        
        old_sl = self.state["stop_loss_pct"]
        if win_rate < 0.45:
            # Too many losses, maybe stop is too tight or strategy is weak
            # Let's try widening slightly to give breathing room
            self.state["stop_loss_pct"] = min(self.state["stop_loss_pct"] * 1.05, 3.0)
        elif win_rate > 0.65:
            # Doing well, can afford to tighten stop to protect capital
            self.state["stop_loss_pct"] = max(self.state["stop_loss_pct"] * 0.95, 0.5)

        # 3. Quality Control Evolution: RVOL tuning
        # If we have many small losses, increase RVOL requirement
        avg_pnl = sum(t.get("pnl", 0) for t in trades[-10:]) / 10
        if avg_pnl < 0:
            self.state["min_rvol"] = min(self.state["min_rvol"] + 0.1, 3.0)
        elif avg_pnl > 5: # Arbitrary high profit
            self.state["min_rvol"] = max(self.state["min_rvol"] - 0.05, 1.2)

        self.state["last_optimized"] = datetime.now().isoformat()
        self._save_model()

        if abs(old_sl - self.state["stop_loss_pct"]) > 0.01:
            send_notification(f"🤖 Bot Evolved: Stop Loss adjusted to {self.state['stop_loss_pct']:.2f}% based on recent performance analysis.")

    def get_dynamic_config(self):
        return {
            "stop_loss_pct": self.state["stop_loss_pct"],
            "take_profit_pct": self.state["take_profit_pct"],
            "min_rvol": self.state["min_rvol"]
        }
