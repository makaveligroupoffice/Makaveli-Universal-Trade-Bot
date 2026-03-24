import json
import logging
import os
import requests
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
        
        strategy_performance = {}
        asset_performance = {}
        scores_90_plus = []
        scores_75_89 = []
        scores_below_75 = []
        
        try:
            with open(self.journal_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry["timestamp"])
                    if ts > cutoff and entry["event_type"] in ["sell_filled", "cover_filled"]:
                        trades.append(entry)
                        
                        # Strategy breakdown
                        reason = entry.get("reason", "Unknown")
                        if not reason: reason = "Unknown"
                        strat = "Unknown"
                        for s in Config.ACTIVE_STRATEGIES:
                            if s in reason.upper():
                                strat = s
                                break
                        strategy_performance[strat] = strategy_performance.get(strat, 0.0) + entry.get("pnl", 0.0)
                        
                        # Asset breakdown
                        symbol = entry.get("symbol", "N/A")
                        asset_performance[symbol] = asset_performance.get(symbol, 0.0) + entry.get("pnl", 0.0)
                        
                        # Score breakdown
                        score = entry.get("context", {}).get("score", 0)
                        if score >= 90:
                            scores_90_plus.append(entry.get("pnl", 0.0))
                        elif score >= 75:
                            scores_75_89.append(entry.get("pnl", 0.0))
                        else:
                            scores_below_75.append(entry.get("pnl", 0.0))

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
        
        # Best/Worst trade
        best_trade = max(t.get("pnl", 0) for t in trades)
        worst_trade = min(t.get("pnl", 0) for t in trades)

        # Best/Worst Strategy
        best_strategy = max(strategy_performance, key=strategy_performance.get) if strategy_performance else "N/A"
        worst_strategy = min(strategy_performance, key=strategy_performance.get) if strategy_performance else "N/A"

        # Best/Worst Asset
        best_asset = max(asset_performance, key=asset_performance.get) if asset_performance else "N/A"
        worst_asset = min(asset_performance, key=asset_performance.get) if asset_performance else "N/A"

        # Quality stats
        all_scores = [t.get("context", {}).get("score", 0) for t in trades]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        count_above_threshold = sum(1 for s in all_scores if s >= Config.MIN_TRADE_QUALITY_SCORE)
        count_below_threshold = sum(1 for s in all_scores if s < Config.MIN_TRADE_QUALITY_SCORE)

        # Simplified drawdown %
        max_dd_pct = 0
        peak = Config.STARTING_EQUITY
        current = Config.STARTING_EQUITY
        for t in trades:
            current += t.get("pnl", 0)
            if current > peak: peak = current
            dd = (peak - current) / peak * 100
            if dd > max_dd_pct: max_dd_pct = dd

        # Calculate Sharpe Ratio (simplified)
        returns = [t.get("pnl", 0) / Config.MAX_POSITION_VALUE_DOLLARS for t in trades]
        import numpy as np
        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        # Calculate Drawdown (simplified)
        equity_curve = [0]
        current_eq = 0
        for t in trades:
            current_eq += t.get("pnl", 0)
            equity_curve.append(current_eq)
        
        peak_val = -999999
        max_dd = 0
        for val in equity_curve:
            if val > peak_val: peak_val = val
            dd = peak_val - val
            if dd > max_dd: max_dd = dd

        analysis = {
            "win_rate": win_rate,
            "win_count": win_count,
            "loss_count": loss_count,
            "total_pnl": total_pnl,
            "total_trades": len(trades),
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd_pct,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "best_strategy": best_strategy,
            "worst_strategy": worst_strategy,
            "best_asset": best_asset,
            "worst_asset": worst_asset,
            "strategy_performance": strategy_performance,
            "avg_score": avg_score,
            "count_above_threshold": count_above_threshold,
            "count_below_threshold": count_below_threshold,
            "pnl_90_plus": sum(scores_90_plus),
            "pnl_75_89": sum(scores_75_89),
            "pnl_below_75": sum(scores_below_75),
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

    def submit_logs_to_central_server(self, bot_id: str):
        if not Config.ENABLE_LOG_SUBMISSION or not Config.CENTRAL_LOG_SERVER_URL:
            return False

        if not os.path.exists(self.journal_path):
            return False

        try:
            # Read all logs from journal
            all_logs = []
            with open(self.journal_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        # We only send filled trades and account events
                        if entry.get("event_type") in ["buy_filled", "sell_filled", "short_filled", "cover_filled", "reconciliation"]:
                             all_logs.append(entry)
                    except:
                        continue

            if not all_logs:
                return True

            # Submit to central server
            url = f"{Config.CENTRAL_LOG_SERVER_URL}/submit_logs"
            payload = {
                "bot_id": bot_id,
                "secret": Config.WEBHOOK_SECRET, # Use webhook secret for simple auth if not using JWT
                "logs": all_logs
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                log.info(f"Successfully submitted {len(all_logs)} logs to central server.")
                return True
            else:
                log.error(f"Failed to submit logs: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            log.error(f"Error submitting logs to central server: {e}")
            return False

    def analyze_central_logs(self):
        # New method to analyze aggregated logs from central_logs directory
        central_logs_dir = os.path.join(Config.LOG_DIR, "central_logs")
        if not os.path.exists(central_logs_dir):
            return "No central logs directory found."

        summary = []
        for filename in os.listdir(central_logs_dir):
            if filename.endswith("_trades.jsonl"):
                bot_id = filename.replace("_trades.jsonl", "")
                path = os.path.join(central_logs_dir, filename)
                
                # Analyze each bot's performance individually
                bot_analyzer = PerformanceAnalyzer(path)
                analysis = bot_analyzer.analyze_recent_trades(days=30)
                if analysis:
                    summary.append({
                        "bot_id": bot_id,
                        "win_rate": analysis["win_rate"],
                        "total_trades": analysis["total_trades"],
                        "total_pnl": analysis["total_pnl"]
                    })
        
        if not summary:
            return "No trading data found in central logs."

        # Aggregate report
        avg_win_rate = sum(s["win_rate"] for s in summary) / len(summary)
        total_pnl = sum(s["total_pnl"] for s in summary)
        total_trades = sum(s["total_trades"] for s in summary)

        report = [
            f"🌐 Centralized Network Performance Report",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"• Bots Contributing:  {len(summary)}",
            f"• Total Network Trades: {total_trades}",
            f"• Avg Win Rate:       {avg_win_rate*100:.1f}%",
            f"• Net Network PnL:    ${total_pnl:.2f}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "Individual Bot Standings:"
        ]
        
        for s in sorted(summary, key=lambda x: x["total_pnl"], reverse=True):
            report.append(f"  - {s['bot_id']}: WR {s['win_rate']*100:.1f}% | PnL ${s['total_pnl']:.2f}")

        return "\n".join(report)

    def generate_report(self, days: int = 1, account_info: dict = None, market_condition: str = "Unknown") -> str:
        analysis = self.analyze_recent_trades(days=days)
        if not analysis:
            return f"DAILY TRADING REPORT\n\nDate: {datetime.now().strftime('%Y-%m-%d')}\n\nNo trading data available for today."

        balance = account_info.get('equity', 0.0) if account_info else 0.0
        starting_balance = Config.STARTING_EQUITY
        pnl = analysis['total_pnl']
        percent_change = (pnl / starting_balance * 100) if starting_balance > 0 else 0

        # Strategies used breakdown
        strategy_breakdown = ""
        # We need to extract strategy performance from trades
        # analysis['strategy_performance'] can be added to analyze_recent_trades
        if 'strategy_performance' in analysis:
            for strat, spnl in analysis['strategy_performance'].items():
                strategy_breakdown += f"- {strat}: ${spnl:.2f}\n"

        report = [
            "DAILY TRADING REPORT",
            "",
            f"Date: {datetime.now().strftime('%Y-%m-%d')}",
            "",
            f"Account Balance: ${balance:,.2f}",
            f"Starting Balance: ${starting_balance:,.2f}",
            "",
            f"Net P/L: ${pnl:.2f} ({percent_change:+.2f}%)",
            "",
            f"Trades Taken: {analysis['total_trades']}",
            f"Wins: {analysis['win_count']}",
            f"Losses: {analysis['loss_count']}",
            f"Win Rate: {analysis['win_rate']*100:.2f}%",
            "",
            f"Avg Win: ${analysis['avg_win']:.2f}",
            f"Avg Loss: ${analysis['avg_loss']:.2f}",
            "",
            f"Best Trade: ${analysis.get('best_trade', 0):.2f}",
            f"Worst Trade: ${analysis.get('worst_trade', 0):.2f}",
            "",
            f"Max Drawdown Today: {analysis.get('max_drawdown_pct', 0):.2f}%",
            "",
            "Strategies Used:",
            strategy_breakdown.strip() if strategy_breakdown else "- N/A",
            "",
            "Market Condition:",
            f"- {market_condition}",
            "",
            "Notes:",
            f"- {analysis.get('recommendations', ['No specific insights for today.'])[0]}"
        ]
        
        return "\n".join(report)

    def generate_weekly_report(self) -> str:
        analysis = self.analyze_recent_trades(days=7)
        if not analysis:
            return "WEEKLY REPORT\n\nNo trading data available for this week."

        report = [
            "WEEKLY REPORT",
            "",
            f"Total Profit: ${analysis['total_pnl']:.2f}",
            f"Win Rate: {analysis['win_rate']*100:.2f}%",
            "",
            f"Best Strategy: {analysis.get('best_strategy', 'N/A')}",
            f"Worst Strategy: {analysis.get('worst_strategy', 'N/A')}",
            "",
            f"Best Asset: {analysis.get('best_asset', 'N/A')}",
            f"Worst Asset: {analysis.get('worst_asset', 'N/A')}",
            "",
            f"Max Drawdown: {analysis.get('max_drawdown_pct', 0):.2f}%",
            "",
            f"Total Trades: {analysis['total_trades']}",
            "",
            "Insights:",
            f"- {analysis.get('recommendations', ['Maintain discipline and follow the strategy.'])[0]}"
        ]
        return "\n".join(report)

    def generate_quality_analysis(self) -> str:
        analysis = self.analyze_recent_trades(days=30)
        if not analysis:
            return "TRADE QUALITY ANALYSIS\n\nNo recent data for quality analysis."

        report = [
            "TRADE QUALITY ANALYSIS",
            "",
            f"Average Trade Score: {analysis.get('avg_score', 0):.1f}",
            "",
            f"Trades Above Threshold: {analysis.get('count_above_threshold', 0)}",
            f"Trades Below Threshold: {analysis.get('count_below_threshold', 0)}",
            "",
            "Performance by Score:",
            f"- 90+ score → ${analysis.get('pnl_90_plus', 0):.2f}",
            f"- 75–89 → ${analysis.get('pnl_75_89', 0):.2f}",
            f"- Below 75 → ${analysis.get('pnl_below_75', 0):.2f}",
            "",
            "Insight:",
            "- Low score trades are underperforming" if analysis.get('pnl_below_75', 0) < 0 else "- Strategy is performing consistently across scores."
        ]
        return "\n".join(report)

    def generate_fast_audit_report(self, days: int = 7) -> str:
        analysis = self.analyze_recent_trades(days=days)
        
        # Performance metrics
        win_rate = "N/A"
        avg_win = "N/A"
        avg_loss = "N/A"
        profit_factor = "N/A"
        max_drawdown = "N/A"

        if analysis:
            win_rate = f"{analysis['win_rate']*100:.1f}%"
            avg_win = f"${analysis['avg_win']:.2f}"
            avg_loss = f"${analysis['avg_loss']:.2f}"
            profit_factor = f"{analysis['profit_factor']:.2f}"
            max_drawdown = f"{analysis['max_drawdown_pct']:.2f}%"

        # Protection status (from bot_state if available, or just from Config)
        kill_switch = "no"
        from bot_state import BotStateStore
        store = BotStateStore(os.path.join(Config.LOG_DIR, "bot_state.json"))
        state = store.load()
        if state.get("kill_switch_active"): kill_switch = "YES"

        report = [
            "Fast audit result",
            "",
            "Risk",
            "",
            f"Risk per trade: {Config.RISK_PCT_PER_TRADE}%",
            f"Max daily loss: {Config.MAX_DAILY_LOSS_PCT}%",
            f"Max weekly loss: {Config.MAX_WEEKLY_LOSS_PCT}%",
            f"Max open positions: {Config.MAX_OPEN_POSITIONS}",
            "",
            "Entries",
            "",
            f"Strategies used: {', '.join(Config.ACTIVE_STRATEGIES)}",
            f"Trade score threshold: {Config.MIN_TRADE_QUALITY_SCORE}",
            f"Regime filter: {'yes' if Config.ENABLE_REGIME_FILTER else 'no'}",
            f"News filter: {'yes' if Config.ENABLE_NEWS_FILTER else 'no'}",
            "",
            "Exits",
            "",
            f"Stop loss method: {Config.STOP_LOSS_METHOD}",
            f"Take profit method: {Config.TAKE_PROFIT_METHOD}",
            f"Break-even: {'yes' if Config.ENABLE_BREAK_EVEN_STOP else 'no'}",
            f"Trailing stop: {'yes' if Config.ENABLE_TRAILING_STOP else 'no'}",
            "",
            "Performance",
            "",
            f"Win rate: {win_rate}",
            f"Avg win: {avg_win}",
            f"Avg loss: {avg_loss}",
            f"Profit factor: {profit_factor}",
            f"Max drawdown: {max_drawdown}",
            "",
            "Protection",
            "",
            f"Kill switch: {kill_switch}",
            f"Loss streak pause: {'yes' if Config.ENABLE_LOSS_STREAK_PAUSE else 'no'}",
            f"Drawdown size reduction: {'yes' if Config.ENABLE_DRAWDOWN_SIZE_REDUCTION else 'no'}",
            f"Profit withdrawal alert: {'yes' if Config.ENABLE_WITHDRAWAL_ALERTS else 'no'}"
        ]
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
