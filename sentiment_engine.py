import logging
import requests
import re
import json
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

    def get_market_sentiment(self, symbol: str = "SPY") -> dict:
        """
        Returns a detailed sentiment analysis including score, urgency, and trend.
        Score: -1.0 (Extreme Fear) to 1.0 (Extreme Greed)
        Urgency: 0.0 to 1.0
        """
        # 1. Fetch recent headlines/social mentions
        headlines = self._fetch_headlines(symbol)
        if not headlines:
            return {"score": 0.0, "urgency": 0.0, "trend": "neutral"}

        # 2. Use AI for deep sentiment analysis (Super Charged)
        try:
            prompt = f"""
            Analyze the market sentiment for {symbol} based on these headlines:
            {headlines[:10]}
            
            Provide a structured JSON response with:
            - score: float between -1.0 and 1.0
            - urgency: float between 0.0 and 1.0 (how fast is this news moving the market)
            - trend: string ('improving', 'deteriorating', 'stable')
            - logic: brief explanation
            """
            
            response = self.ai.client.chat.completions.create(
                model=self.ai.model,
                messages=[
                    {"role": "system", "content": "You are a real-time market sentiment quantifier."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            analysis = json.loads(response.choices[0].message.content)
            log.info(f"Super Charged Sentiment for {symbol}: {analysis}")
            return analysis
        except Exception as e:
            log.error(f"Sentiment analysis failed for {symbol}: {e}")
            return {"score": 0.0, "urgency": 0.0, "trend": "neutral"}

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
        
        headlines = []
        if news:
            for n in news:
                if hasattr(n, 'headline'):
                    headlines.append(n.headline)
                elif isinstance(n, dict) and 'headline' in n:
                    headlines.append(n['headline'])
                elif isinstance(n, (list, tuple)) and len(n) > 0:
                    # If it's a list/tuple of items, maybe the first one is the headline?
                    # Or maybe news is a list of tuples like (headline, date, etc)
                    headlines.append(str(n[0]))
                else:
                    headlines.append(str(n))
        return headlines

    def _parse_sentiment_score(self, report: str) -> float:
        """Enhanced heuristic to convert AI text report to a float score."""
        report_lower = report.lower()
        
        # Look for explicit numeric scores in AI output
        import re
        score_match = re.search(r"score:\s*(-?\d+\.?\d*)", report_lower)
        if score_match:
            return float(score_match.group(1))

        score = 0.0
        # Positive sentiment weights
        pos_terms = ["bullish", "greed", "optimism", "growth", "strong", "outperform", "buy", "upgraded"]
        for term in pos_terms:
            if term in report_lower: score += 0.2
            
        # Negative sentiment weights
        neg_terms = ["bearish", "fear", "pessimism", "decline", "weak", "underperform", "sell", "downgraded"]
        for term in neg_terms:
            if term in report_lower: score -= 0.2
            
        # Intensifiers
        if "very" in report_lower or "extreme" in report_lower:
            score *= 1.5
        
        # Clamp between -1 and 1
        return max(-1.0, min(1.0, score))

    def is_market_stable(self) -> bool:
        """Returns True if the general market sentiment is not in 'Extreme Fear'."""
        overall_sentiment = self.get_market_sentiment("SPY")
        return overall_sentiment.get("score", 0.0) > -0.7
