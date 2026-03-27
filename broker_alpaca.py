from __future__ import annotations

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce, PositionSide, PositionIntent, OrderType, OrderClass
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest, LimitOrderRequest, OrderRequest, OptionLegRequest, TakeProfitRequest, StopLossRequest, StopOrderRequest, StopLimitOrderRequest

from config import Config
from broker_base import BrokerBase


class AlpacaBroker(BrokerBase):
    def __init__(self, key=None, secret=None, paper=None):
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient
        
        self.client = TradingClient(
            key or Config.get_alpaca_key(),
            secret or Config.get_alpaca_secret(),
            paper=paper if paper is not None else Config.ALPACA_PAPER,
        )
        self.alpaca_paper = paper if paper is not None else Config.ALPACA_PAPER
        self.alpaca_key = key or Config.get_alpaca_key()
        self.alpaca_secret = secret or Config.get_alpaca_secret()
        self.data_client = StockHistoricalDataClient(
            key or Config.get_alpaca_key(),
            secret or Config.get_alpaca_secret()
        )

    def get_latest_quote(self, symbol: str):
        try:
            from alpaca.data.requests import StockLatestQuoteRequest
            req = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=Config.ALPACA_DATA_FEED)
            return self.data_client.get_stock_latest_quote(req)[symbol]
        except Exception as e:
            print(f"Error fetching latest quote for {symbol}: {e}")
            return None

    def get_latest_mid_price(self, symbol: str) -> float | None:
        quote = self.get_latest_quote(symbol)
        if quote:
            return (quote.ask_price + quote.bid_price) / 2
        return None

    def get_historical_bars(self, symbol: str, start: str, end: str, timeframe: str = "1Min"):
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        
        tf_map = {
            "1Min": TimeFrame(1, TimeFrameUnit.Minute),
            "5Min": TimeFrame(5, TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
            "1Day": TimeFrame(1, TimeFrameUnit.Day)
        }
        
        tf = tf_map.get(timeframe, TimeFrame(1, TimeFrameUnit.Minute))
        
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
            feed=Config.ALPACA_DATA_FEED
        )
        return self.data_client.get_stock_bars(req).df

    def buy(self, symbol: str, qty: float, limit_price: float | None = None, stop_price: float | None = None, stop_limit_price: float | None = None, stop_loss_price: float | None = None, take_profit_price: float | None = None, trailing_stop_pct: float | None = None, extended_hours: bool = False):
        if Config.ENABLE_OMNISCIENT_EXECUTION and not limit_price and not stop_price:
            # Use mid-price limit for market orders to avoid slippage
            mid = self.get_latest_mid_price(symbol)
            if mid:
                limit_price = mid * 1.0005 # Slight offset to ensure fill but prevent slippage
                print(f"OMNISCIENT: Using mid-price limit {limit_price} for {symbol}")

        is_crypto = "/" in symbol or any(c in symbol for c in ["BTC", "ETH", "SOL", "LTC"])
        tif = TimeInForce.GTC if is_crypto else TimeInForce.DAY
        
        # Determine order class
        order_class = OrderClass.SIMPLE
        tp_req = None
        sl_req = None
        
        if take_profit_price:
            tp_req = TakeProfitRequest(limit_price=round(take_profit_price, 2))
            order_class = OrderClass.BRACKET
            
        if stop_loss_price:
            sl_req = StopLossRequest(stop_price=round(stop_loss_price, 2))
            order_class = OrderClass.BRACKET if tp_req else OrderClass.OTO
            
        # Determine order request type
        if stop_limit_price and stop_price:
            order = StopLimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=tif,
                limit_price=round(stop_limit_price, 2) if not is_crypto else stop_limit_price,
                stop_price=round(stop_price, 2) if not is_crypto else stop_price,
                extended_hours=extended_hours if not is_crypto else False,
                order_class=order_class,
                take_profit=tp_req,
                stop_loss=sl_req
            )
        elif stop_price:
            order = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=tif,
                stop_price=round(stop_price, 2) if not is_crypto else stop_price,
                extended_hours=extended_hours if not is_crypto else False,
                order_class=order_class,
                take_profit=tp_req,
                stop_loss=sl_req
            )
        elif limit_price:
            order = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=tif,
                limit_price=round(limit_price, 2) if not is_crypto else limit_price,
                extended_hours=extended_hours if not is_crypto else False,
                order_class=order_class,
                take_profit=tp_req,
                stop_loss=sl_req
            )
        else:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=tif,
                order_class=order_class,
                take_profit=tp_req,
                stop_loss=sl_req
            )
        return self.client.submit_order(order_data=order)

    def sell(self, symbol: str, qty: float, limit_price: float | None = None, stop_price: float | None = None, stop_limit_price: float | None = None, extended_hours: bool = False):
        is_crypto = "/" in symbol or any(c in symbol for c in ["BTC", "ETH", "SOL", "LTC"])
        tif = TimeInForce.GTC if is_crypto else TimeInForce.DAY
        
        if stop_limit_price and stop_price:
            order = StopLimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=tif,
                limit_price=round(stop_limit_price, 2) if not is_crypto else stop_limit_price,
                stop_price=round(stop_price, 2) if not is_crypto else stop_price,
                extended_hours=extended_hours if not is_crypto else False
            )
        elif stop_price:
            order = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=tif,
                stop_price=round(stop_price, 2) if not is_crypto else stop_price,
                extended_hours=extended_hours if not is_crypto else False
            )
        elif limit_price:
            order = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=tif,
                limit_price=round(limit_price, 2) if not is_crypto else limit_price,
                extended_hours=extended_hours if not is_crypto else False
            )
        else:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=tif,
            )
        return self.client.submit_order(order_data=order)

    def short(self, symbol: str, qty: float, limit_price: float | None = None, stop_price: float | None = None, stop_limit_price: float | None = None, stop_loss_price: float | None = None, take_profit_price: float | None = None, extended_hours: bool = False):
        tif = TimeInForce.DAY
        
        # Determine order class
        order_class = OrderClass.SIMPLE
        tp_req = None
        sl_req = None
        
        if take_profit_price:
            tp_req = TakeProfitRequest(limit_price=round(take_profit_price, 2))
            order_class = OrderClass.BRACKET
            
        if stop_loss_price:
            sl_req = StopLossRequest(stop_price=round(stop_loss_price, 2))
            order_class = OrderClass.BRACKET if tp_req else OrderClass.OTO

        if stop_limit_price and stop_price:
            order = StopLimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=tif,
                limit_price=round(stop_limit_price, 2),
                stop_price=round(stop_price, 2),
                extended_hours=extended_hours,
                order_class=order_class,
                take_profit=tp_req,
                stop_loss=sl_req
            )
        elif stop_price:
            order = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=tif,
                stop_price=round(stop_price, 2),
                extended_hours=extended_hours,
                order_class=order_class,
                take_profit=tp_req,
                stop_loss=sl_req
            )
        elif limit_price:
            order = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=tif,
                limit_price=round(limit_price, 2),
                extended_hours=extended_hours,
                order_class=order_class,
                take_profit=tp_req,
                stop_loss=sl_req
            )
        else:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=tif,
                order_class=order_class,
                take_profit=tp_req,
                stop_loss=sl_req
            )
        return self.client.submit_order(order_data=order)

    def cover(self, symbol: str, qty: float, limit_price: float | None = None, stop_price: float | None = None, stop_limit_price: float | None = None, extended_hours: bool = False):
        if stop_limit_price and stop_price:
            order = StopLimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=round(stop_limit_price, 2),
                stop_price=round(stop_price, 2),
                extended_hours=extended_hours
            )
        elif stop_price:
            order = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                stop_price=round(stop_price, 2),
                extended_hours=extended_hours
            )
        elif limit_price:
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
        qty = abs(float(pos.qty))
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

    def get_news(self, symbol: str, days: int = 1):
        from market_data import MarketDataClient
        return MarketDataClient().get_news(symbol, days=days)

    def get_calendar(self, start_date: str, end_date: str):
        """
        Fetch economic calendar (high impact events).
        Alpaca doesn't have a direct economic calendar API in the SDK, 
        so we'll use their general market news or potentially a scraper/other API 
        in the news_engine. For now, this is a placeholder that can be extended.
        """
        try:
            # We can use the clock as a basic check if we want, 
            # but real calendar needs external source.
            return []
        except Exception:
            return []

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

    def withdraw_to_bank(self, amount: float, bank_account_id: str):
        """
        Initiate an ACH withdrawal to a linked bank account via REST API.
        The Python SDK (Alpaca-py) doesn't have a direct method for transfers yet, 
        so we use the standard Requests library to hit the /v2/transfers endpoint.
        """
        import requests
        
        endpoint = f"{Config.get_alpaca_base_url().replace('paper-api', 'api')}/v2/transfers"
        
        headers = {
            "APCA-API-KEY-ID": self.client._api_key,
            "APCA-API-SECRET-KEY": self.client._secret_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "relationship_id": bank_account_id,
            "amount": str(round(amount, 2)),
            "direction": "OUTGOING"
        }
        
        response = requests.post(endpoint, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Withdrawal failed: {response.text}")
            
        return response.json()