import sys
from news_engine import NewsEngine
from config import Config
from broker_alpaca import AlpacaBroker

def test_news_engine():
    print("Testing News Engine...")
    print(f"Ranking: \n{NewsEngine.get_news_ranking_report()}")
    
    # Simulate a broker for checking news
    broker = AlpacaBroker()
    
    # Check current market safety
    safe, reason = NewsEngine.is_market_safe(None, broker)
    print(f"Global Market Safe: {safe} | Reason: {reason}")
    
    # Test specific high impact keywords
    test_headlines = [
        "CPI report shows inflation higher than expected",
        "FOMC meeting minutes released",
        "Apple releases new iPhone",
        "NFP data exceeds expectations"
    ]
    
    print("\nTesting specific headlines for HIGH IMPACT:")
    for headline in test_headlines:
        is_high_impact = any(event in headline.lower() for event in NewsEngine.HIGH_IMPACT_EVENTS)
        print(f"Headline: {headline} | High Impact: {is_high_impact}")

if __name__ == "__main__":
    test_news_engine()
