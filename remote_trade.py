import requests
import json
import argparse
from config import Config

# --- CONFIGURATION ---
# Replace with your ngrok URL if using remotely
DEFAULT_URL = f"http://localhost:{Config.PORT}/webhook"
SECRET = Config.WEBHOOK_SECRET

def send_manual_trade(action: str, symbol: str, qty: int, url: str):
    payload = {
        "secret": SECRET,
        "action": action.lower(),
        "symbol": symbol.upper(),
        "qty": int(qty),
        "alert_id": f"manual-{symbol.upper()}-{int(requests.utils.time.time())}" if hasattr(requests.utils, 'time') else f"manual-{symbol.upper()}-{int(__import__('time').time())}"
    }
    
    headers = {"Content-Type": "application/json"}
    
    print(f"\n🚀 Sending {action.upper()} order for {qty} shares of {symbol}...")
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 200:
            print("\n✅ Success! Check your phone for a notification.")
        else:
            print("\n❌ Failed. Check 'logs/tradebot.log' on your server for details.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send manual trade signals to your TradeBot.")
    parser.add_argument("action", choices=["buy", "sell"], help="Action to perform (buy or sell)")
    parser.add_argument("symbol", help="Ticker symbol (e.g., AAPL)")
    parser.add_argument("qty", type=int, help="Quantity to trade")
    parser.add_argument("--url", default=DEFAULT_URL, help="The Webhook URL (e.g., your ngrok address)")

    args = parser.parse_args()
    send_manual_trade(args.action, args.symbol, args.qty, args.url)
