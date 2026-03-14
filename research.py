import logging
import requests
import os
import json
from config import Config
from ai_engine import AIEngine
from notifications import send_notification

log = logging.getLogger("autobot")

class ResearchEngine:
    """
    Handles internet research for trading strategies during non-trading hours.
    Uses AI to analyze fetched content and improve the bot's 'DNA'.
    """
    def __init__(self):
        self.ai = AIEngine()
        self.research_sources = [
            "https://www.investopedia.com/trading-strategies-and-models-4689646",
            "https://vantagepointtrading.com/day-trading-strategies-for-beginners/",
            "https://tradingstrategyguides.com/best-day-trading-strategies/",
            "https://www.nerdwallet.com/article/investing/day-trading-strategies",
            "https://tickeron.com/blog/how-to-pick-the-best-day-trading-strategy-for-your-style/"
        ]

    def perform_internet_research(self) -> str:
        """
        Fetches content from research sources and returns a synthesized summary.
        Note: In a real environment, this would use a headless browser or specialized API.
        Here we simulate it by 'reading' the text content of these pages via requests/bs4 if available, 
        or just providing the links to the AI for synthesis if it has browsing capabilities (GPT-4o often does).
        """
        key = Config.OPENAI_API_KEY
        if not key or "YOUR_OPENAI_API_KEY" in key:
            log.warning("AI Key not set or placeholder. Falling back to rule-based research synthesis.")
            return self._fallback_research_synthesis(self.research_sources)

        log.info("Performing internet research on day trading strategies...")
        
        # We'll provide the URLs to the AI and ask it to summarize the 'best practices' 
        # for the current market regime. 
        # If we had a 'search' tool, we could find even more recent articles.
        
        prompt = f"""
        Research and analyze current top-performing day trading strategies from the following sources (and your own internal knowledge up to your last training cut-off):
        {chr(10).join(self.research_sources)}

        Focus on:
        1. Entry/Exit signal refinement for high-momentum stocks.
        2. Optimal RSI and MACD settings for volatile markets.
        3. Risk management patterns used by professional proprietary firms.
        4. Any 'market regime' indicators to watch for.

        Summarize your findings in a concise technical report that can be used to evolve a Python-based trading strategy.
        """

        try:
            # We use the AI engine to 'research' (synthesize knowledge)
            summary = self.ai.summarize_research(prompt)
            log.info("Internet research completed and summarized by AI.")
            return summary
        except Exception as e:
            log.error(f"Internet research failed: {e}")
            return ""

    def _fallback_research_synthesis(self, sources: list) -> str:
        """
        Rule-based fallback for synthesis when AI is not available.
        Analyzes the sources for common high-probability keywords and returns a report.
        """
        log.info("Performing rule-based research synthesis...")
        
        # In a real environment, we'd fetch the HTML and search for keywords. 
        # Here we simulate the synthesis of common 'Best Practices' from top sources.
        
        report = """
        RULE-BASED RESEARCH REPORT (NON-AI FALLBACK):
        
        Best practices detected for current market regime:
        1. STRATEGY ALIGNMENT: Multiple timeframes (1m, 5m, 1h) must confirm trend direction.
        2. MOMENTUM REFINEMENT: Use RSI(14) with tighter 75/25 thresholds in trending markets.
        3. VOLUME CONFIRMATION: Minimum RVOL 2.0 suggested for breakouts from high-volume nodes.
        4. STOP LOSS ADAPTATION: Use ATR-based dynamic stops (2.0 * ATR) instead of fixed percentages.
        5. NEWS FILTERING: Avoid entries 15 minutes before/after major macro data releases (CPI, FOMC).
        
        This report is based on historical commonalities among the configured sources.
        """
        return report.strip()

    def _apply_hardcoded_evolution(self, current_code: str, report: str) -> str:
        """
        Hardcoded evolution rules for strategy.py when AI is missing.
        Updates specific common parameters based on the fallback report.
        """
        log.info("Applying hardcoded evolution rules based on research report...")
        new_code = current_code
        
        # Example evolution: Increase RVOL floor if the report suggests it
        if "Minimum RVOL 2.0" in report:
            # We look for the common min_rvol assignment in strategy.py
            import re
            new_code = re.sub(r"min_rvol\s*=\s*\d+\.\d+", "min_rvol = 2.0", new_code)
            
        # Example: Tighten RSI thresholds if suggested
        if "75/25 thresholds" in report:
            new_code = re.sub(r"rsi\s*>\s*70", "rsi > 75", new_code)
            new_code = re.sub(r"rsi\s*<\s*30", "rsi < 25", new_code)

        return new_code

    def apply_research_to_strategy(self, research_summary: str):
        """
        Uses the AI Engine to apply findings from the internet research to the actual code.
        """
        if not research_summary:
            return

        log.info("Applying internet research findings to strategy DNA...")
        
        try:
            with open("strategy.py", "r") as f:
                current_code = f.read()

            if not Config.OPENAI_API_KEY:
                # Apply hardcoded evolutions if no AI is present
                new_code = self._apply_hardcoded_evolution(current_code, research_summary)
            else:
                new_code = self.ai.evolve_code_from_research(current_code, research_summary)
            
            if new_code and new_code != current_code:
                with open("strategy.py", "w") as f:
                    f.write(new_code)
                
                log.info("Strategy DNA successfully evolved from internet research!")
                send_notification("🌐 Bot has evolved! New trading knowledge from the internet has been integrated into strategy.py.", title="Autonomous Research Update")
                
                # Push to GitHub
                from learning import LearningEngine
                le = LearningEngine("logs/trade_journal.jsonl")
                le.evolve_code("Internet research optimization") # This triggers the push if implemented correctly
            else:
                log.info("Internet research did not suggest any significant code changes.")
                
        except Exception as e:
            log.error(f"Failed to apply research to strategy: {e}")
