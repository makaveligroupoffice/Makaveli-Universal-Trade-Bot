from __future__ import annotations

from datetime import UTC, datetime, timedelta

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

from config import Config


class MarketDataClient:
    def __init__(self):
        self.client = StockHistoricalDataClient(
            Config.ALPACA_KEY,
            Config.ALPACA_SECRET,
        )

    def get_recent_bars(self, symbol: str, minutes: int = 30):
        end = datetime.now(UTC)
        start = end - timedelta(minutes=minutes + 5)

        feed = DataFeed.SIP if Config.ALPACA_DATA_FEED.lower() == "sip" else DataFeed.IEX

        # noinspection PyArgumentList
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            feed=feed,
        )

        bars = self.client.get_stock_bars(request)

        if symbol not in bars.data:
            return []

        return bars.data[symbol]

    def get_latest_quote(self, symbol: str):
        feed = DataFeed.SIP if Config.ALPACA_DATA_FEED.lower() == "sip" else DataFeed.IEX
        request = StockLatestQuoteRequest(
            symbol_or_symbols=symbol,
            feed=feed,
        )
        quotes = self.client.get_stock_latest_quote(request)
        return quotes.get(symbol)

    def get_latest_mid_price(self, symbol: str) -> float | None:
        quote = self.get_latest_quote(symbol)

        if not quote:
            return None

        bid = float(quote.bid_price or 0)
        ask = float(quote.ask_price or 0)

        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        if ask > 0:
            return ask
        if bid > 0:
            return bid

        return None

    def get_spread_pct(self, symbol: str) -> float | None:
        quote = self.get_latest_quote(symbol)

        if not quote:
            return None

        bid = float(quote.bid_price or 0)
        ask = float(quote.ask_price or 0)

        if bid <= 0 or ask <= 0 or ask < bid:
            return None

        mid = (bid + ask) / 2.0
        if mid <= 0:
            return None

        return ((ask - bid) / mid) * 100.0