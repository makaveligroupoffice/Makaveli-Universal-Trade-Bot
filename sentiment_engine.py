import logging
import requests
import re
from config import Config
from ai_engine import AIEngine

log = logging.getLogger("sentiment_engine")

class SentimentEngine:
    """
    Scrapes and analyzes market sentiment from social sources and news to provide 
    'Fear & Greed' filters for the trading bot.
    """
    def __init__(self):
        self.ai = AIEngine()
        self.sentiment_cache = {} # {symbol: {score, timestamp}}

    def get_market_sentiment(self, symbol: str = "SPY") -> float:
        """
        Returns a sentiment score from -1.0 (Extreme Fear) to 1.0 (Extreme Greed).
        """
        # 1. Fetch recent headlines/social mentions (Simulated/Scraped)
        headlines = self._fetch_headlines(symbol)
        if not headlines:
            return 0.0 # Neutral

        # 2. Use AI to analyze sentiment of headlines
        try:
            sentiment_report = self.ai.analyze_trade_sentiment(symbol, headlines)
            # Extract numeric score from report if possible, or use a heuristic
            score = self._parse_sentiment_score(sentiment_report)
            log.info(f"Sentiment for {symbol}: {score} ({sentiment_report[:50]}...)")
            return score
        except Exception as e:
            log.error(f"Sentiment analysis failed for {symbol}: {e}")
            return 0.0

    def _fetch_headlines(self, symbol: str) -> list[str]:
        """
        Simulates fetching headlines from news APIs or social scraping.
        In a full implementation, this would use Tweepy, BeautifulSoup, or NewsAPI.
        """
        # Placeholder for real scraping logic
        # For now, we'll try to fetch from Alpaca if possible (already in Broker/MarketData)
        from market_data import MarketDataClient
        md = MarketDataClient()
        news = md.get_news(symbol, days=1)
        return [n.headline for n in news] if news else []

    def _parse_sentiment_score(self, report: str) -> float:
        """Heuristic to convert AI text report to a float score."""
        report_lower = report.lower()
        score = 0.0
        if "bullish" in report_lower or "greed" in report_lower: score += 0.5
        if "very bullish" in report_lower or "extreme greed" in report_lower: score += 0.4
        if "bearish" in report_lower or "fear" in report_lower: score -= 0.5
        if "very bearish" in report_lower or "extreme fear" in report_lower: score -= 0.4
        
        # Clamp between -1 and 1
        return max(-1.0, min(1.0, score))

    def is_market_stable(self) -> bool:
        """Returns True if the general market sentiment is not in 'Extreme Fear'."""
        overall_sentiment = self.get_market_sentiment("SPY")
        return overall_sentiment > -0.7
