from broker_alpaca import AlpacaBroker
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Rebalancer")

class PortfolioRebalancer:
    def __init__(self, target_weights=None):
        self.broker = AlpacaBroker()
        # Default weights: 40% Stocks, 30% Crypto, 30% Bonds
        self.target_weights = target_weights or {
            "STOCKS": 0.40,
            "CRYPTO": 0.30,
            "BONDS": 0.30
        }

    def rebalance(self):
        logger.info("Starting portfolio rebalancing...")
        account = self.broker.get_account()
        total_equity = float(account.equity)
        positions = self.broker.get_positions()
        
        current_allocations = {"STOCKS": 0, "CRYPTO": 0, "BONDS": 0}
        
        for pos in positions:
            symbol = pos.symbol
            val = float(pos.market_value)
            
            if '/' in symbol:
                current_allocations["CRYPTO"] += val
            elif symbol in ["TLT", "BND", "AGG", "IEF", "SHY", "LQD", "HYG", "JNK", "TIP"]:
                current_allocations["BONDS"] += val
            else:
                current_allocations["STOCKS"] += val

        logger.info(f"Current Allocations: {current_allocations}")
        
        for asset_class, target_pct in self.target_weights.items():
            target_val = total_equity * target_pct
            current_val = current_allocations[asset_class]
            diff = target_val - current_val
            
            if abs(diff) > total_equity * 0.05: # Rebalance if > 5% deviation
                logger.info(f"Rebalancing {asset_class}: Diff is {diff:.2f}")
                # Implementation: Would sell overweight and buy underweight
                # For safety, we just log and provide suggestions in this version
                # In a full version, we'd execute orders here.
                if diff > 0:
                    logger.info(f"Suggestion: Increase {asset_class} exposure by {diff:.2f}")
                else:
                    logger.info(f"Suggestion: Decrease {asset_class} exposure by {abs(diff):.2f}")

if __name__ == "__main__":
    rebalancer = PortfolioRebalancer()
    rebalancer.rebalance()
