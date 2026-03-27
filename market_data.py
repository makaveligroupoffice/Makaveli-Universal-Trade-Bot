from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional, Any

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient, OptionHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest, StockLatestQuoteRequest, 
    OptionChainRequest, OptionLatestQuoteRequest, OptionSnapshotRequest,
    CryptoBarsRequest, CryptoLatestQuoteRequest
)
from alpaca.data.timeframe import TimeFrame

from config import Config

log = logging.getLogger("tradebot")

class MarketDataClient:
    def __init__(self):
        self.client = StockHistoricalDataClient(
            Config.get_alpaca_key(),
            Config.get_alpaca_secret(),
        )
        self.option_client = OptionHistoricalDataClient(
            Config.get_alpaca_key(),
            Config.get_alpaca_secret(),
        )
        self.crypto_client = CryptoHistoricalDataClient(
            Config.get_alpaca_key(),
            Config.get_alpaca_secret(),
        )
        self._cache = {}

    async def async_get_recent_bars(self, symbol: str, minutes: int = 30):
        """Asynchronous wrapper for get_recent_bars."""
        return await asyncio.to_thread(self.get_recent_bars, symbol, minutes)

    async def async_get_latest_mid_price(self, symbol: str) -> float | None:
        """Asynchronous wrapper for get_latest_mid_price."""
        return await asyncio.to_thread(self.get_latest_mid_price, symbol)

    async def async_get_multi_bars(self, symbols: List[str], minutes: int = 30) -> Dict[str, Any]:
        """Fetch bars for multiple symbols in parallel."""
        tasks = [self.async_get_recent_bars(s, minutes) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {s: r for s, r in zip(symbols, results) if not isinstance(r, Exception)}

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

    def get_market_regime(self, symbol: str = "SPY") -> tuple[str, float]:
        """
        Check overall market trend (Bullish/Bearish/Neutral) 
        and return (regime, 30_min_return_pct).
        """
        bars = self.get_recent_bars(symbol, minutes=200)
        if not bars:
            return "UNKNOWN", 0.0
        
        import pandas as pd
        df = pd.DataFrame([{"close": float(b.close)} for b in bars])
        if len(df) < 50:
            return "UNKNOWN", 0.0
        
        sma20 = df['close'].rolling(20).mean().iloc[-1]
        sma50 = df['close'].rolling(50).mean().iloc[-1]
        last_close = df['close'].iloc[-1]
        
        # 30-min return calculation
        prev_30_close = df['close'].iloc[-31] if len(df) >= 31 else df['close'].iloc[0]
        change_30m = ((last_close - prev_30_close) / prev_30_close) * 100.0

        if last_close > sma20 and last_close > sma50:
            regime = "BULLISH"
        elif last_close < sma20 and last_close < sma50:
            regime = "BEARISH"
        else:
            regime = "NEUTRAL"
            
        return regime, change_30m

    def get_historical_bars(self, symbol: str, minutes: int = 100, timeframe: str = "1Min"):
        """Fetches historical bars for a symbol."""
        from datetime import datetime, timedelta, timezone
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)
        
        # Use broker if available
        from broker_alpaca import AlpacaBroker
        broker = AlpacaBroker()
        df = broker.get_historical_bars(symbol, start.isoformat(), end.isoformat(), timeframe)
        
        if df.empty:
            return None
            
        # Convert df to bar list (simulating Alpaca bar objects)
        from dataclasses import dataclass
        @dataclass
        class Bar:
            open: float
            high: float
            low: float
            close: float
            volume: float
            timestamp: datetime
            
        bars = []
        for index, row in df.iterrows():
            bars.append(Bar(
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume'],
                timestamp=index.to_pydatetime() if hasattr(index, 'to_pydatetime') else index
            ))
        return bars

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
        from datetime import datetime, timedelta, timezone
        
        client = NewsClient(Config.get_alpaca_key(), Config.get_alpaca_secret())
        
        start = datetime.now(timezone.utc) - timedelta(days=days)
        request = NewsRequest(
            symbols=symbol,
            start=start,
            limit=10
        )
        
        try:
            response = client.get_news(request)
            news = []
            if hasattr(response, 'news'):
                news = response.news
            else:
                news = response
            
            # Ensure it's a list and not a nested object/tuple if that's what's happening
            if isinstance(news, tuple):
                news = list(news)
            
            # If the objects are somehow not what we expect, let's wrap them or check them
            return news
        except Exception as e:
            print(f"Error fetching news: {e}")
            return []