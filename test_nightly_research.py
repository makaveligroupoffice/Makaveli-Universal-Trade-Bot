import logging
import json
from learning import MarketResearcher

logging.basicConfig(level=logging.INFO)

def test_research():
    print("Initializing Market Researcher...")
    dummy_config = {
        "stop_loss_pct": 1.0,
        "take_profit_pct": 2.5,
        "min_rvol": 1.8
    }
    
    # We only test on 2 symbols for speed
    from universe import DEFAULT_UNIVERSE
    test_universe = DEFAULT_UNIVERSE[:2]
    
    import universe
    universe.DEFAULT_UNIVERSE = test_universe
    
    researcher = MarketResearcher(dummy_config)
    print(f"Running research on {test_universe}...")
    updates = researcher.perform_nightly_research()
    
    print("\nResearch Results:")
    print(json.dumps(updates, indent=4))
    
    if updates:
        print("\nSUCCESS: Researcher found parameter optimizations.")
    else:
        print("\nCOMPLETED: No critical parameter changes recommended for these samples.")

if __name__ == "__main__":
    test_research()
