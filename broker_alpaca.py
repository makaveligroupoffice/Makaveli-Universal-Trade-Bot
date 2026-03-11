from __future__ import annotations

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce, PositionSide, PositionIntent, OrderType, OrderClass
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest, LimitOrderRequest, OrderRequest, OptionLegRequest

from config import Config


class AlpacaBroker:
    def __init__(self):
        self.client = TradingClient(
            Config.ALPACA_KEY,
            Config.ALPACA_SECRET,
            paper=Config.ALPACA_PAPER,
        )

    def buy(self, symbol: str, qty: int, limit_price: float | None = None, extended_hours: bool = False):
        if limit_price and (Config.USE_LIMIT_ORDERS or extended_hours):
            order = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_price, 2),
                extended_hours=extended_hours
            )
        else:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
        return self.client.submit_order(order_data=order)

    def sell(self, symbol: str, qty: int, limit_price: float | None = None, extended_hours: bool = False):
        if limit_price and (Config.USE_LIMIT_ORDERS or extended_hours):
            order = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_price, 2),
                extended_hours=extended_hours
            )
        else:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
        return self.client.submit_order(order_data=order)

    def short(self, symbol: str, qty: int, limit_price: float | None = None, extended_hours: bool = False):
        if limit_price and (Config.USE_LIMIT_ORDERS or extended_hours):
            order = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_price, 2),
                extended_hours=extended_hours
            )
        else:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
        return self.client.submit_order(order_data=order)

    def cover(self, symbol: str, qty: int, limit_price: float | None = None, extended_hours: bool = False):
        if limit_price and (Config.USE_LIMIT_ORDERS or extended_hours):
            order = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_price, 2),
                extended_hours=extended_hours
            )
        else:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
        return self.client.submit_order(order_data=order)

    def submit_option_order(
        self,
        symbol: str | None = None,
        qty: float | None = None,
        side: OrderSide | None = None,
        position_intent: PositionIntent | None = None,
        limit_price: float | None = None,
        legs: list[dict] | None = None
    ):
        """
        Submits an option order (single or multi-legged).
        If legs are provided, 'symbol', 'qty', 'side' are ignored for the top-level request
        (Alpaca multi-legged orders use the 'legs' list).
        """
        if legs:
            # Multi-legged order
            option_legs = []
            for leg in legs:
                option_legs.append(OptionLegRequest(
                    symbol=leg["symbol"].upper(),
                    ratio_qty=float(leg["ratio_qty"]),
                    side=OrderSide.BUY if leg["side"].lower() in ["buy", "long"] else OrderSide.SELL,
                    position_intent=PositionIntent(leg["position_intent"].lower())
                ))
            
            # For multi-leg, symbol is usually the underlying? 
            # Actually Alpaca Multi-leg API uses 'symbol' as the underlying symbol.
            # And qty as the number of units of the strategy.
            order = OrderRequest(
                symbol=symbol.upper() if symbol else "",
                qty=float(qty) if qty else 1.0,
                side=side or OrderSide.BUY,
                type=OrderType.LIMIT if limit_price else OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
                legs=option_legs,
                limit_price=round(limit_price, 2) if limit_price else None
            )
        else:
            # Single leg option order
            order = OrderRequest(
                symbol=symbol.upper(),
                qty=float(qty),
                side=side,
                type=OrderType.LIMIT if limit_price else OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
                position_intent=position_intent,
                limit_price=round(limit_price, 2) if limit_price else None
            )
        
        return self.client.submit_order(order_data=order)

    def get_position_qty(self, symbol: str) -> int:
        try:
            pos = self.client.get_open_position(symbol)
            return int(float(pos.qty))
        except (APIError, ValueError, TypeError):
            return 0

    def get_position(self, symbol: str):
        try:
            return self.client.get_open_position(symbol)
        except APIError:
            return None

    def get_all_positions(self):
        try:
            return self.client.get_all_positions()
        except APIError:
            return []

    def sell_all(self, symbol: str, limit_price: float | None = None, extended_hours: bool = False):
        pos = self.get_position(symbol)
        if not pos:
            raise ValueError(f"No position to close for {symbol}")
        qty = abs(int(float(pos.qty)))
        side = pos.side
        if side == PositionSide.LONG:
            return self.sell(symbol, qty, limit_price=limit_price, extended_hours=extended_hours)
        else:
            return self.cover(symbol, qty, limit_price=limit_price, extended_hours=extended_hours)

    def get_open_positions_count(self) -> int:
        return len(self.get_all_positions())

    def get_account_equity(self) -> float:
        acct = self.client.get_account()
        return float(acct.equity)

    def get_account(self):
        return self.client.get_account()

    def get_open_positions(self):
        try:
            return self.client.get_all_positions()
        except APIError:
            return []

    def get_orders(self, status: str = "all", limit: int = 20):
        try:
            status_enum = QueryOrderStatus(status)
        except ValueError:
            status_enum = QueryOrderStatus.ALL

        try:
            request = GetOrdersRequest(status=status_enum, limit=limit)
            return self.client.get_orders(filter=request)
        except APIError:
            return []

    def get_order_by_id(self, order_id: str):
        try:
            return self.client.get_order_by_id(order_id)
        except APIError:
            return None

    def cancel_all_orders(self):
        try:
            return self.client.cancel_orders()
        except APIError:
            return None

    def get_clock(self):
        try:
            return self.client.get_clock()
        except APIError:
            return None

    def get_latest_mid_price(self, symbol: str) -> float | None:
        """
        Helper for webhook_server to get price for limit orders
        using the data client logic but through the broker interface.
        """
        from market_data import MarketDataClient
        return MarketDataClient().get_latest_mid_price(symbol)