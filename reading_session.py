import os
import sys
import logging
from ai_engine import AIEngine
from learning import LearningEngine
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("ReadingSession")

BOOK_LIST = [
    "Reminiscences of a Stock Operator by Edwin Lefèvre",
    "Technical Analysis of the Financial Markets by John J. Murphy",
    "The Intelligent Investor by Benjamin Graham",
    "Market Wizards by Jack D. Schwager",
    "Trading for a Living by Alexander Elder",
    "The New Trading for a Living by Alexander Elder",
    "Encyclopedia of Chart Patterns by Thomas N. Bulkowski",
    "Trend Following by Michael Covel",
    "Way of the Turtle by Curtis Faith",
    "A Complete Guide to Volume Price Analysis by Anna Coulling",
    "The Daily Trading Coach by Brett N. Steenbarger",
    "One Good Trade by Mike Bellafiore",
    "High Probability Trading by Marcel Link",
    "Beyond Technical Analysis by Tushar S. Chande",
    "Option Volatility and Pricing by Sheldon Natenberg",
    "Intermarket Analysis by John J. Murphy",
    "Fooled by Randomness by Nassim Nicholas Taleb",
    "The Black Swan by Nassim Nicholas Taleb",
    "Thinking, Fast and Slow by Daniel Kahneman",
    "Atomic Habits by James Clear (for discipline)",
    "Flow by Mihaly Csikszentmihalyi (for psychological performance)",
    "Mastering the Trade by John F. Carter",
    "Secrets for Profiting in Bull and Bear Markets by Stan Weinstein",
    "How to Make Money in Stocks by William O'Neil (CAN SLIM method)",
    "Jesse Livermore's Methods by George S. Clason",
    "The Art of War by Sun Tzu (for strategy)",
    "Principles by Ray Dalio",
    "The Alchemist by Paulo Coelho (for visionary focus)"
]

def run_reading_session():
    logger.info("Starting 'Universal Reading Session'...")
    
    ai = AIEngine()
    learner = LearningEngine("logs/trade_journal.jsonl")
    
    logger.info(f"Synthesizing knowledge from {len(BOOK_LIST)} trading books...")
    knowledge_summary = ai.synthesize_universal_knowledge(BOOK_LIST)
    
    if not knowledge_summary:
        logger.error("Failed to synthesize knowledge. Check API keys.")
        return

    # Save the knowledge to lessons_learned.jsonl so the bot 'remembers' it
    from datetime import datetime
    import json
    
    lesson_entry = {
        "timestamp": datetime.now().isoformat(),
        "source": "Universal Reading Session",
        "lesson": "Synthesized core principles from 25+ trading classics.",
        "details": knowledge_summary
    }
    
    with open("logs/lessons_learned.jsonl", "a") as f:
        f.write(json.dumps(lesson_entry) + "\n")
    
    logger.info("Universal knowledge ingested. Triggering autonomous code evolution...")
    
    # Trigger code evolution based on this knowledge
    # We'll use the evolve_code_from_research path or general evolution
    # to rewrite strategy.py
    
    with open("strategy.py", "r") as f:
        current_code = f.read()
    
    logger.info("Evolving strategy.py with universal trading laws...")
    evolved_code = ai.evolve_code_from_research(current_code, knowledge_summary)
    
    if evolved_code and evolved_code != current_code:
        with open("strategy.py", "w") as f:
            f.write(evolved_code)
        logger.info("strategy.py has been updated with universal trading knowledge.")
    else:
        logger.warning("No significant strategy improvements suggested by AI.")

    # Also update config.py if needed
    # (Optional, but let's stick to strategy for now as it's the core)

    logger.info("Reading session complete. Bot is now smarter.")

if __name__ == "__main__":
    run_reading_session()
