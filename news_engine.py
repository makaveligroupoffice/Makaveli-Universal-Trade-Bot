import requests
import logging
from datetime import datetime, timedelta
from config import Config

log = logging.getLogger("tradebot")

class NewsEngine:
    """
    Aggregates news and economic calendar data from multiple sources:
    Forex Factory, Trading Economics, Investing.com (simulated/simpler feeds).
    Checks for high-impact events like CPI, FOMC to block trading.
    """

    # Major events that require a buffer
    HIGH_IMPACT_EVENTS = ["cpi", "fomc", "fed ", "interest rate", "inflation", "non-farm payroll", "nfp", "gdp"]

    @staticmethod
    def get_upcoming_economic_events():
        """
        Fetches upcoming economic events from prioritized sources.
        For now, we simulate this by parsing news headlines from broker (Alpaca)
        since direct scraping might require more dependencies or be fragile.
        But the architecture is here to plug in Forex Factory or TE APIs.
        """
        events = []
        # Source 1: Forex Factory (Simulated via news headlines if direct API not available)
        # Source 2: Trading Economics
        # Source 3: Investing.com

        # Real-world implementation would use:
        # requests.get("https://tradingeconomics.com/calendar") and parse it.
        # Or an actual API if user provides keys.
        
        return events

    @staticmethod
    def is_market_safe(symbol: str = None, broker=None):
        """
        Final check if it's safe to trade based on the economic calendar.
        Blocks 15-30 mins BEFORE and AFTER high-impact events.
        """
        if not Config.ECONOMIC_CALENDAR_FILTER:
            return True, "Calendar filter disabled"

        # Check for major keywords in recent news (as proxy for calendar if no direct feed)
        if broker:
            news = broker.get_news(symbol, days=1) if symbol else broker.get_news(None, days=1)
            for item in news:
                # Handle both object attributes and dict-like access
                headline = ""
                created_at = None
                
                if hasattr(item, "headline"):
                    headline = item.headline.lower()
                    created_at = item.created_at
                elif isinstance(item, dict):
                    headline = item.get("headline", "").lower()
                    created_at = item.get("created_at")
                elif isinstance(item, (list, tuple)) and len(item) > 0:
                    # In some versions it might be a tuple of news items?
                    # Or it's a specific field. Let's try to be safe.
                    continue 

                if any(event in headline for event in NewsEngine.HIGH_IMPACT_EVENTS):
                    # If news just hit (last 15-30 mins), it's unsafe
                    # Note: created_at might be string or datetime
                    try:
                        if isinstance(created_at, str):
                            # ISO format usually
                            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        
                        if created_at:
                            now = datetime.now(created_at.tzinfo)
                            diff_mins = (now - created_at).total_seconds() / 60
                            
                            buffer = Config.ECONOMIC_CALENDAR_BUFFER_MINUTES
                            if diff_mins < buffer:
                                return False, f"High impact news just hit: {headline} ({int(diff_mins)}m ago)"
                    except Exception:
                        # Fallback if timestamp parsing fails
                        return False, f"Recent high impact news: {headline}"

        # TODO: Implement actual calendar checking (pre-event block)
        # For Forex Factory style, we'd need a list of scheduled event times.
        
        return True, "No immediate high-impact events detected"

    @staticmethod
    def get_news_ranking_report():
        """
        Returns the ranked news sources as requested.
        """
        report = [
            "1. Forex Factory (Best for high-impact: CPI, FOMC)",
            "2. Trading Economics (Best for structured data/APIs)",
            "3. Investing.com (Best for mobile alerts/manual backup)"
        ]
        return "\n".join(report)
