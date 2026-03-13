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
                    if ts > cutoff and entry["event_type"] in ["sell_filled", "cover_filled"]:
                        trades.append(entry)
        except Exception as e:
            log.error(f"Error reading journal: {e}")
            return None

        if not trades:
            return None

        win_count = sum(1 for t in trades if t.get("pnl", 0) > 0)
        loss_count = sum(1 for t in trades if t.get("pnl", 0) <= 0)
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        avg_win = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0) / win_count if win_count > 0 else 0
        avg_loss = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) <= 0) / loss_count) if loss_count > 0 else 1
        
        win_rate = win_count / len(trades)
        profit_factor = (win_count * avg_win) / (loss_count * avg_loss) if (loss_count * avg_loss) > 0 else 999
        
        # Calculate Drawdown (simplified)
        equity_curve = [0]
        current_eq = 0
        for t in trades:
            current_eq += t.get("pnl", 0)
            equity_curve.append(current_eq)
        
        peak = -999999
        max_dd = 0
        for val in equity_curve:
            if val > peak: peak = val
            dd = peak - val
            if dd > max_dd: max_dd = dd

        analysis = {
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_trades": len(trades),
            "profit_factor": profit_factor,
            "max_drawdown": max_dd,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "win_loss_ratio": avg_win / avg_loss if avg_loss > 0 else 0,
            "recommendations": []
        }

        if win_rate < 0.4:
            analysis["recommendations"].append("WIDEN_STOP_LOSS")
        elif win_rate > 0.7:
             analysis["recommendations"].append("TIGHTEN_STOP_LOSS")
             
        if total_pnl < 0:
            analysis["recommendations"].append("REDUCE_RISK_PER_TRADE")

        return analysis

    def generate_report(self, days: int = 30) -> str:
        analysis = self.analyze_recent_trades(days=days)
        if not analysis:
            return "No trading data available for the period."

        report = [
            f"📊 Performance Report (Last {days} Days)",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"• Total Trades:   {analysis['total_trades']}",
            f"• Win Rate:       {analysis['win_rate']*100:.1f}%",
            f"• Total PnL:      ${analysis['total_pnl']:.2f}",
            f"• Profit Factor:  {analysis['profit_factor']:.2f}",
            f"• Max Drawdown:   ${analysis['max_drawdown']:.2f}",
            f"• Avg Win:        ${analysis['avg_win']:.2f}",
            f"• Avg Loss:       ${analysis['avg_loss']:.2f}",
            f"• W/L Ratio:      {analysis['win_loss_ratio']:.2f}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        if analysis["recommendations"]:
            report.append("💡 Recommendations:")
            for rec in analysis["recommendations"]:
                report.append(f"  - {rec}")
                
        return "\n".join(report)

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
