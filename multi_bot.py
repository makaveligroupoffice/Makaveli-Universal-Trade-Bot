import time
import logging
from bot_runner import AutoTrader
from config import Config
from risk import RiskManager
from notifications import send_notification

from intelligence import SelfAdaptingStrategySystem, ConfidenceEngine
log = logging.getLogger("multi_bot")

class MultiBotManager:
    """
    Master Controller that manages multiple specialized trading bots.
    Bot 1 = Scalper
    Bot 2 = Swing Trader
    Bot 3 = Trend Follower
    """
    def __init__(self, broker):
        self.broker = broker
        self.risk_manager = RiskManager()
        self.bots = {}
        self._setup_bots()

    def _setup_bots(self):
        # Bot 1: Scalper (1m bars, aggressive)
        self.bots["scalper"] = AutoTrader(
            self.broker, 
            timeframe="1Min", 
            strategy_active=["SCALPING"],
            risk_pct=0.5 # Low risk per trade for high frequency
        )
        
        # Bot 2: Swing Trader (15m or Hourly, conservative)
        self.bots["swing"] = AutoTrader(
            self.broker,
            timeframe="15Min",
            strategy_active=["TREND_SNIPER", "CONFLUENCE"],
            risk_pct=2.0
        )
        
        # Bot 3: Trend Follower (5m, moderate)
        self.bots["trend_follower"] = AutoTrader(
            self.broker,
            timeframe="5Min",
            strategy_active=["TREND_SNIPER"],
            risk_pct=1.0
        )

    def run_cycle(self):
        """Runs one loop of all bots with master risk oversight."""
        if not Config.MASTER_RISK_CONTROL_ENABLED:
            for name, bot in self.bots.items():
                bot.run(single_cycle=True)
            return

        # 0. OPPORTUNITY SCANNER: Rank bot types/asset sectors in real-time
        system = SelfAdaptingStrategySystem()
        perf = system.update_performance() or {}
        
        # 0.1 CAPITAL ROTATION: Move focus to the strongest performing timeframe/family
        prioritize, disable = system.get_priority_strategies()
        
        # Master Risk Oversight
        current_equity = self.broker.get_equity()
        if not self.risk_manager.can_trade(current_equity=current_equity):
            log.warning("MASTER RISK CONTROL: Trading disabled for all bots.")
            # Still run cycles for exits (implicit in AutoTrader logic when entries disabled)
            for name, bot in self.bots.items():
                 bot.run(single_cycle=True)
            return

        for name, bot in self.bots.items():
            # 0.2 "DO NOTHING" INTELLIGENCE: Skip bot if its target strategies are in decay
            if any(strat in disable for strat in (bot.strategy_active or [])):
                log.info(f"Bot '{name}' strategy disabled due to performance decay.")
                continue

            # 0.3 SYSTEM HEALTH SCORE (0-100)
            health = 100
            if bot.last_run < (time.time() - 600): health -= 20
            if float(self.risk_manager.state.get("daily_pnl", 0)) < 0: health -= 10
            log.info(f"Bot '{name}' Health Score: {health}")

            log.info(f"Running cycle for Bot: {name}")
            bot.run(single_cycle=True)

    def heartbeat(self):
        """Sends a heartbeat signal to verify all bots are alive."""
        status = {name: ("Alive" if bot.last_run > (time.time() - 300) else "Stale") 
                  for name, bot in self.bots.items()}
        send_notification(f"Multi-Bot Heartbeat: {status}", title="Heartbeat Monitoring")

if __name__ == "__main__":
    from broker_alpaca import AlpacaBroker
    broker = AlpacaBroker()
    manager = MultiBotManager(broker)
    while True:
        try:
            manager.run_cycle()
            time.sleep(60)
        except Exception as e:
            log.error(f"Multi-Bot Manager Error: {e}")
            time.sleep(10)
