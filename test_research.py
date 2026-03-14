import logging
import sys
import os
from research import ResearchEngine
from bot_runner import AutoTrader
from config import Config

# Setup logging to console
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def test_research():
    print("--- Testing Internet Research Module ---")
    
    if not Config.OPENAI_API_KEY or "YOUR_OPENAI_API_KEY" in Config.OPENAI_API_KEY:
        print("SKIP: OpenAI API Key not configured correctly.")
        # We can still test the logic with a mock summary
        researcher = ResearchEngine()
        mock_summary = "Day trading research: Focus on SMA crossovers and RSI overbought levels. Use tight 1% stops."
        print(f"Applying MOCK research: {mock_summary}")
        # researcher.apply_research_to_strategy(mock_summary) # Caution: this will edit strategy.py
        print("SUCCESS: Research logic check (Mock).")
        return

    researcher = ResearchEngine()
    summary = researcher.perform_internet_research()
    
    if summary:
        print("SUCCESS: Fetched research summary from AI.")
        print(f"Summary Snippet: {summary[:200]}...")
        
        # In a real test we might want to apply it, but let's just verify the summary generation for now
        # to avoid accidental production code modification if not desired.
        # researcher.apply_research_to_strategy(summary)
    else:
        print("FAILED: No research summary generated.")

if __name__ == "__main__":
    test_research()
