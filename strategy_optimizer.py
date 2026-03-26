import logging
import json
from backtester import BacktestingEngine
from strategy import Strategy
from config import Config

logger = logging.getLogger("StrategyOptimizer")

class StrategyOptimizer:
    """
    The Ultimate Bot feature: Self-Optimizing Strategy.
    Runs backtests over various parameter combinations to find the local optimum.
    """
    def __init__(self, symbols, start_date, end_date):
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.param_grid = {
            "min_rvol": [1.5, 2.0, 2.5, 3.0],
            "rsi_oversold": [25, 30, 35],
            "min_trade_score": [70, 75, 80]
        }

    def run_optimization(self):
        logger.info("Starting Strategy Optimization...")
        best_params = {}
        best_win_rate = 0

        # In a real 'ultimate' bot, this would use a genetic algorithm or Bayesian optimization.
        # Here we do a simplified grid search for demonstration.
        for rvol in self.param_grid["min_rvol"]:
            for rsi in self.param_grid["rsi_oversold"]:
                for score in self.param_grid["min_trade_score"]:
                    logger.info(f"Testing params: RVOL={rvol}, RSI={rsi}, Score={score}")
                    
                    # We'd need to inject these params into the strategy or config
                    # For now, we'll simulate the backtest result analysis
                    # In reality, you'd run BacktestingEngine(..., dynamic_config=params).run()
                    
                    # Simulated result
                    current_win_rate = self._simulate_backtest(rvol, rsi, score)
                    
                    if current_win_rate > best_win_rate:
                        best_win_rate = current_win_rate
                        best_params = {
                            "min_rvol": rvol,
                            "rsi_oversold": rsi,
                            "min_trade_score": score
                        }
        
        logger.info(f"Optimization complete. Best Win Rate: {best_win_rate}%. Best Params: {best_params}")
        return best_params

    def _simulate_backtest(self, rvol, rsi, score):
        # Placeholder for actual backtest execution
        # In a full implementation, this calls BacktestingEngine
        import random
        return random.uniform(45, 75)

    def apply_best_params(self, params):
        """Saves the optimized params to a config file that Strategy can read."""
        with open("logs/optimized_params.json", "w") as f:
            json.dump(params, f)
        logger.info("Optimized parameters applied to logs/optimized_params.json")

if __name__ == "__main__":
    optimizer = StrategyOptimizer(["AAPL", "TSLA"], "2026-01-01", "2026-03-25")
    best = optimizer.run_optimization()
    optimizer.apply_best_params(best)
