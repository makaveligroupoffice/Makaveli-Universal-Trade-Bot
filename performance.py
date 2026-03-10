import json
import logging
import os
from datetime import datetime, timedelta
from config import Config

log = logging.getLogger("autobot")

class PerformanceAnalyzer:
    def __init__(self, journal_path: str):
        self.journal_path = journal_path

    def analyze_recent_trades(self, days: int = 7):
        if not os.path.exists(self.journal_path):
            return None

        trades = []
        cutoff = datetime.now() - timedelta(days=days)
        
        try:
            with open(self.journal_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry["timestamp"])
                    if ts > cutoff and entry["event_type"] == "sell_filled":
                        trades.append(entry)
        except Exception as e:
            log.error(f"Error reading journal: {e}")
            return None

        if not trades:
            return None

        win_count = sum(1 for t in trades if t.get("pnl", 0) > 0)
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        avg_pnl = total_pnl / len(trades)
        win_rate = win_count / len(trades)

        # Identify "Mistakes"
        # 1. High Slippage: filled_avg_price significantly different from exit_est (if we had it)
        # 2. Too many losses in a row
        # 3. Stop loss being hit too often (SL may be too tight)
        
        analysis = {
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "total_trades": len(trades),
            "recommendations": []
        }

        if win_rate < 0.4:
            analysis["recommendations"].append("WIDEN_STOP_LOSS")
        elif win_rate > 0.7:
             analysis["recommendations"].append("TIGHTEN_STOP_LOSS")
             
        if avg_pnl < 0:
            analysis["recommendations"].append("REDUCE_RISK_PER_TRADE")

        return analysis

    def get_suggested_config(self, current_dynamic_config: dict):
        analysis = self.analyze_recent_trades()
        if not analysis:
            return current_dynamic_config

        new_config = current_dynamic_config.copy()
        
        for rec in analysis["recommendations"]:
            if rec == "WIDEN_STOP_LOSS":
                new_config["stop_loss_pct"] = min(new_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) * 1.1, 5.0)
            if rec == "TIGHTEN_STOP_LOSS":
                new_config["stop_loss_pct"] = max(new_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) * 0.9, 0.5)
            if rec == "REDUCE_RISK_PER_TRADE":
                # Scale down risk_pct_per_trade if we have it, or suggest it
                pass

        return new_config
