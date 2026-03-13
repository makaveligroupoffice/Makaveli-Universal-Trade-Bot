from __future__ import annotations

from datetime import UTC, datetime, timedelta

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient, OptionHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest, StockLatestQuoteRequest, 
    OptionChainRequest, OptionLatestQuoteRequest, OptionSnapshotRequest,
    CryptoBarsRequest, CryptoLatestQuoteRequest
)
from alpaca.data.timeframe import TimeFrame

from config import Config


class MarketDataClient:
    def __init__(self):
        self.client = StockHistoricalDataClient(
            Config.ALPACA_KEY,
            Config.ALPACA_SECRET,
        )
        self.option_client = OptionHistoricalDataClient(
            Config.ALPACA_KEY,
            Config.ALPACA_SECRET,
        )
        self.crypto_client = CryptoHistoricalDataClient(
            Config.ALPACA_KEY,
            Config.ALPACA_SECRET,
        )

    def get_bars_for_research(self, symbol: str, days: int = 3):
        """Fetch historical bars for research purposes."""
        end = datetime.now(UTC)
        start = end - timedelta(days=days)

        feed = DataFeed.SIP if Config.ALPACA_DATA_FEED.lower() == "sip" else DataFeed.IEX

        # noinspection PyArgumentList
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            feed=feed,
        )

        try:
            bars = self.client.get_stock_bars(request)
            if symbol not in bars.data:
                return []
            return bars.data[symbol]
        except Exception as e:
            print(f"Error fetching research bars for {symbol}: {e}")
            return []

    def get_recent_bars(self, symbol: str, minutes: int = 30):
        end = datetime.now(UTC)
        start = end - timedelta(minutes=minutes + 5)

        if "/" in symbol or any(c in symbol for c in ["BTC", "ETH", "SOL", "LTC"]):
            # Likely crypto
            request = CryptoBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=start,
                end=end
            )
            bars = self.crypto_client.get_crypto_bars(request)
            if symbol not in bars.data:
                return []
            return bars.data[symbol]

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
        if "/" in symbol or any(c in symbol for c in ["BTC", "ETH", "SOL", "LTC"]):
            # Likely crypto
            request = CryptoLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.crypto_client.get_crypto_latest_quote(request)
            return quotes.get(symbol)

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

    def get_option_latest_quote(self, symbol: str):
        """Fetch latest quote for an option symbol."""
        request = OptionLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = self.option_client.get_option_latest_quote(request)
        return quotes.get(symbol)

    def get_option_chain(self, underlying_symbol: str):
        """Fetch option chain for an underlying symbol."""
        request = OptionChainRequest(underlying_symbol=underlying_symbol)
        return self.option_client.get_option_chain(request)

    def get_option_snapshot(self, symbol: str):
        """Fetch snapshot for an option symbol (includes Greeks)."""
        request = OptionSnapshotRequest(symbol_or_symbols=symbol)
        snapshots = self.option_client.get_option_snapshot(request)
        return snapshots.get(symbol)

    def get_news(self, symbol: str | None = None, days: int = 1):
        """Fetch news for a symbol or general market news."""
        from alpaca.data.requests import NewsRequest
        from alpaca.data.historical import NewsClient
        
        client = NewsClient(Config.ALPACA_KEY, Config.ALPACA_SECRET)
        
        start = datetime.now(UTC) - timedelta(days=days)
        request = NewsRequest(
            symbols=[symbol] if symbol else None,
            start=start,
            limit=10
        )
        
        try:
            return client.get_news(request).news
        except Exception as e:
            print(f"Error fetching news: {e}")
            return []