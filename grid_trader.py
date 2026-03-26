import logging
import time
from config import Config
from notifications import send_notification

log = logging.getLogger("grid_trader")

class GridTrader:
    """
    Implements a Grid Trading (Market Making) strategy for choppy/sideways markets.
    Places buy/sell orders at fixed intervals (grids) around a base price.
    """
    def __init__(self, broker, risk_manager):
        self.broker = broker
        self.risk_manager = risk_manager
        self.active_grids = {} # {symbol: {base_price, grid_size, levels, orders}}

    def setup_grid(self, symbol: str, base_price: float, grid_size_pct: float = 1.0, levels: int = 5):
        """
        Initializes a grid for a specific symbol.
        grid_size_pct: Distance between grid levels in percent.
        levels: Number of levels above and below the base price.
        """
        grid_size = base_price * (grid_size_pct / 100)
        self.active_grids[symbol] = {
            "base_price": base_price,
            "grid_size": grid_size,
            "levels": levels,
            "orders": [], # Track active grid orders
            "positions": 0 # Track net grid positions
        }
        log.info(f"Grid setup for {symbol} at {base_price} with {levels} levels and {grid_size_pct}% spacing.")
        self._refresh_grid(symbol)

    def _refresh_grid(self, symbol: str):
        """Places or replaces grid orders based on current price and state."""
        grid = self.active_grids.get(symbol)
        if not grid:
            return

        # Cancel existing grid orders first (manual tracking of IDs if needed, but alpaca has cancel_all_orders)
        # For grids we want specific control
        for order_id in grid["orders"]:
            try:
                # We don't have a cancel_order_by_id in BrokerBase, but AlpacaBroker has it.
                # We'll assume the broker has a cancel_order(order_id) method or similar.
                if hasattr(self.broker, 'cancel_order_by_id'):
                    self.broker.cancel_order_by_id(order_id)
            except:
                pass
        grid["orders"] = []

        base = grid["base_price"]
        size = grid["grid_size"]
        levels = grid["levels"]

        # Calculate position size (conservative for grid trading)
        qty = self.risk_manager.calculate_risk_parity_size(symbol, self.broker.get_account_equity(), [])
        qty = max(1, int(qty // (levels * 2)))

        # Place Buy orders below base
        for i in range(1, levels + 1):
            price = base - (i * size)
            try:
                order = self.broker.buy(
                    symbol=symbol,
                    qty=qty,
                    limit_price=round(price, 2)
                )
                if hasattr(order, 'id'):
                    grid["orders"].append(order.id)
            except Exception as e:
                log.error(f"Failed to place grid buy order for {symbol} at {price}: {e}")

        # Place Sell orders above base
        for i in range(1, levels + 1):
            price = base + (i * size)
            try:
                order = self.broker.sell(
                    symbol=symbol,
                    qty=qty,
                    limit_price=round(price, 2)
                )
                if hasattr(order, 'id'):
                    grid["orders"].append(order.id)
            except Exception as e:
                log.error(f"Failed to place grid sell order for {symbol} at {price}: {e}")

    def update(self):
        """Monitors active grids and re-adjusts if the base price is breached significantly."""
        for symbol, grid in list(self.active_grids.items()):
            current_price = self.broker.get_latest_mid_price(symbol)
            if not current_price:
                continue

            # If price moves outside the entire grid, reset the base
            upper_bound = grid["base_price"] + (grid["levels"] * grid["grid_size"])
            lower_bound = grid["base_price"] - (grid["levels"] * grid["grid_size"])

            if current_price > upper_bound or current_price < lower_bound:
                log.info(f"Grid for {symbol} breached (Price: {current_price}). Re-centering grid.")
                self.setup_grid(symbol, current_price, grid["grid_size"]/grid["base_price"]*100, grid["levels"])
            
            # Check for filled orders (Alpaca handles this, but we should verify status to send alerts)
            # In a real impl, we'd use a stream, here we poll or rely on next cycle.

    def stop_grid(self, symbol: str):
        """Stops grid for a symbol and cancels all orders."""
        grid = self.active_grids.pop(symbol, None)
        if grid:
            for order_id in grid["orders"]:
                try:
                    self.broker.cancel_order(order_id)
                except:
                    pass
            log.info(f"Grid for {symbol} stopped.")
