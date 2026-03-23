import json
import logging
import os
from datetime import datetime, timedelta
from config import Config
from notifications import send_notification
from market_data import MarketDataClient
from strategy import Strategy
from universe import DEFAULT_UNIVERSE
from ai_engine import AIEngine

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
                # Modified to handle new 4-tuple return from strategy
                signal_res = Strategy.should_buy(window, self.dynamic_config)
                should_buy = signal_res[0]
                
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
        self.ai = AIEngine()

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
        manual_trades = []
        try:
            with open(self.journal_path, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("event_type") in ["sell_filled", "cover_filled"]:
                        if entry.get("manual"):
                            manual_trades.append(entry)
                        trades.append(entry)
        except:
            return

        # Handle manual trade learning
        if manual_trades:
            self.learn_from_manual_trades(manual_trades)

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

        # Call code evolution based on performance
        analysis = {
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "recommendations": []
        }
        if win_rate < 0.45: analysis["recommendations"].append("WIDEN_STOP_LOSS")
        if avg_pnl < 0: analysis["recommendations"].append("REDUCE_RISK_PER_TRADE")
        
        if analysis["recommendations"]:
            self.evolve_code(str(analysis["recommendations"]))

        if abs(old_sl - self.state["stop_loss_pct"]) > 0.01:
            send_notification(f"🤖 Bot Evolved: Stop Loss adjusted to {self.state['stop_loss_pct']:.2f}% based on recent performance analysis.")

    def learn_from_manual_trades(self, manual_trades):
        """Analyze manual trades and extract lessons."""
        lessons_path = "logs/lessons_learned.jsonl"
        existing_ids = set()
        if os.path.exists(lessons_path):
            with open(lessons_path, "r") as f:
                for line in f:
                    try:
                        existing_ids.add(json.loads(line).get("id"))
                    except: pass

        new_lessons = []
        for trade in manual_trades:
            trade_id = trade.get("context", {}).get("order_id") if trade.get("context") else None
            if not trade_id:
                trade_id = f"{trade.get('symbol')}_{trade.get('timestamp')}"
            
            if trade_id in existing_ids:
                continue
            
            # Analyze why it was successful or failure
            pnl = trade.get("pnl", 0)
            context = trade.get("context", {})
            
            # Logic: If pnl is None, try to calculate it or just mark as 'informative'
            success = None
            if pnl is not None:
                success = pnl > 0
            
            lesson = {
                "id": trade_id,
                "timestamp": datetime.now().isoformat(),
                "symbol": trade.get("symbol"),
                "side": trade.get("side"),
                "pnl": pnl,
                "success": success,
                "reason": trade.get("reason"),
                "indicators_at_time": context.get("indicators"),
                "market_state": context.get("market_state")
            }
            new_lessons.append(lesson)
            
            with open(lessons_path, "a") as f:
                f.write(json.dumps(lesson) + "\n")

        if new_lessons:
            log.info(f"Learned {len(new_lessons)} new lessons from manual trades.")
        # Trigger code evolution with these lessons
        lessons_summary = "\n".join([
            f"Manual Trade on {l['symbol']}: PnL=${l['pnl'] if l['pnl'] is not None else 'N/A'}, Reason: {l['reason']}, Success: {l['success']}"
            for l in new_lessons
        ])
        
        # Add extra analysis: What would the bot have done?
        for l in new_lessons:
            log.info(f"Analyzing manual trade lesson for {l['symbol']}...")
            # We could add more logic here to compare with Strategy.should_buy
            pass

        self.evolve_code(f"MANUAL_TRADE_LESSONS:\n{lessons_summary}")

    def learn_from_youtube(self, url: str):
        """Extract strategy from a YouTube video and evolve code."""
        log.info(f"Learning Engine processing YouTube video: {url}")
        
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            import re

            # Extract video ID
            video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
            if not video_id_match:
                log.error(f"Could not extract video ID from URL: {url}")
                return False

            video_id = video_id_match.group(1)
            
            # Fetch transcript
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            full_text = " ".join([t['text'] for t in transcript_list])
            
            # Use AI to extract strategy
            strategy_summary = self.ai.extract_strategy_from_transcript(full_text)
            
            if strategy_summary:
                log.info(f"Successfully extracted strategy from YouTube video {video_id}")
                
                # Log lesson
                lessons_path = "logs/lessons_learned.jsonl"
                lesson = {
                    "id": f"youtube_{video_id}",
                    "timestamp": datetime.now().isoformat(),
                    "source": "youtube",
                    "url": url,
                    "lesson": strategy_summary
                }
                with open(lessons_path, "a") as f:
                    f.write(json.dumps(lesson) + "\n")
                
                # Evolve code
                self.evolve_code(f"YOUTUBE_TRADING_STRATEGY_LESSON:\n{strategy_summary}")
                return True
            else:
                log.error("Failed to extract strategy from transcript via AI.")
                return False

        except Exception as e:
            log.error(f"Error learning from YouTube: {e}")
            return False

    def evolve_code(self, analysis_report: str):
        """
        Uses AI to rewrite strategy code based on performance analysis.
        This uses an autonomous self-correction pattern.
        """
        if not Config.ENABLE_AI_EVOLUTION:
            log.info("AI evolution disabled. Skipping code evolution.")
            return

        log.info(f"Learning Engine evolving strategy logic via AI based on report: {analysis_report}")
        
        try:
            with open("strategy.py", "r") as f:
                current_code = f.read()
            
            # Use AI to generate the evolved code
            new_content = self.ai.generate_code_evolution(current_code, analysis_report)
            
            if new_content and new_content != current_code:
                # Basic sanity check: ensure 'class Strategy' is still present
                if "class Strategy" not in new_content:
                    log.error("AI-generated code missing 'Strategy' class. Rejecting.")
                    return

                with open("strategy.py", "w") as f:
                    f.write(new_content)
                log.info("Strategy code autonomously evolved by AI. Hot-reload will trigger.")
                
                # Automatically push the evolution to GitHub
                try:
                    import subprocess
                    subprocess.run(["git", "add", "strategy.py"], check=True)
                    commit_msg = f"chore(evolution): AI autonomously improved strategy logic: {analysis_report}"
                    commit_msg += "\n\nCo-authored-by: Junie <junie@jetbrains.com>"
                    subprocess.run(["git", "commit", "-m", commit_msg], check=True)
                    subprocess.run(["git", "push", "origin", "main"], check=True)
                    log.info("AI-driven code evolution pushed to GitHub.")
                except Exception as ge:
                    log.error(f"Failed to push AI evolution to GitHub: {ge}")

                send_notification("Bot has autonomously improved its own code using AI and pushed the update to GitHub.", title="AI Evolution")
            else:
                log.info("AI suggested no changes or failed to generate code.")
        except Exception as e:
            log.error(f"AI evolution process failed: {e}")

    def get_dynamic_config(self):
        return {
            "stop_loss_pct": self.state["stop_loss_pct"],
            "take_profit_pct": self.state["take_profit_pct"],
            "min_rvol": self.state["min_rvol"],
            "symbol_performance": self.state.get("symbol_performance", {})
        }
