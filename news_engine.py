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
        Fetches upcoming economic events from Trading Economics or similar.
        In this enhanced version, we'll try to use a more structured approach
        or scraping logic if possible.
        """
        events = []
        try:
            # We use an open RSS feed from Trading Economics if possible, or scrape it.
            # For simplicity, we'll simulate the response but with a more realistic structure.
            # Real URL: https://tradingeconomics.com/calendar
            
            # Simulation of fetched high-impact events for the current week:
            # In a real implementation, we'd use requests.get() here.
            # For now, let's keep the logic of 'finding' them in news but expand it.
            pass
        except Exception as e:
            log.error(f"Failed to fetch economic events: {e}")
        
        return events

    @staticmethod
    def check_high_impact_schedule():
        """
        New method to explicitly check a hardcoded or fetched list of 
        known high-impact release times (CPI, FOMC).
        """
        # Hardcoded critical dates for demonstration (would be fetched in 'ultimate' bot)
        # format: (YYYY-MM-DD HH:MM, Event Name)
        critical_events = [
            ("2026-03-26 08:30", "CPI"),
            ("2026-04-03 08:30", "Non-Farm Payroll"),
            ("2026-04-10 14:00", "FOMC Minutes")
        ]
        
        now = datetime.now()
        for event_time_str, event_name in critical_events:
            event_time = datetime.fromisoformat(event_time_str)
            time_diff = (event_time - now).total_seconds() / 60
            
            buffer = Config.ECONOMIC_CALENDAR_BUFFER_MINUTES
            if -buffer < time_diff < buffer:
                return False, f"CRITICAL: {event_name} is scheduled at {event_time_str} ({int(time_diff)}m from now)"
        
        return True, "No scheduled critical events in the immediate buffer"

    @staticmethod
    def is_market_safe(symbol: str = None, broker=None):
        """
        Final check if it's safe to trade based on the economic calendar.
        Blocks 15-30 mins BEFORE and AFTER high-impact events.
        """
        if not Config.ECONOMIC_CALENDAR_FILTER:
            return True, "Calendar filter disabled"

        # 1. Check scheduled calendar events
        is_scheduled_safe, reason = NewsEngine.check_high_impact_schedule()
        if not is_scheduled_safe:
            return False, reason

        # 2. Check for major keywords in recent news (as proxy for calendar if no direct feed)
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
