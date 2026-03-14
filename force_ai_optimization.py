import logging
import sys
from research import ResearchEngine
from config import Config

# Set up logging to stdout to see the results
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
log = logging.getLogger("autobot")

def main():
    if not Config.OPENAI_API_KEY or "YOUR_OPENAI" in Config.OPENAI_API_KEY:
        print("ERROR: Valid OPENAI_API_KEY required for AI-driven expert review.")
        return

    print("🚀 Starting AI-Driven Expert Strategy Review...")
    re = ResearchEngine()
    
    # 1. Perform research with new goal-oriented prompts
    summary = re.perform_internet_research()
    if not summary:
        print("❌ Research failed or returned no summary.")
        # Try fallback explicitly for the force script
        summary = re._fallback_research_synthesis([])
        
    print(f"\n--- RESEARCH SUMMARY ---\n{summary}\n---------------------------\n")
    
    # 2. Apply findings to strategy code
    print("🧠 Evolving strategy DNA using AI findings...")
    re.apply_research_to_strategy(summary)
    print("✅ Strategy Evolution cycle complete.")

if __name__ == "__main__":
    main()
