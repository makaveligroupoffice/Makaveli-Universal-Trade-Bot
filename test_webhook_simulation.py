import requests
import json
import time
from config import Config

# --- CONFIGURATION ---
BASE_URL = f"http://localhost:{Config.PORT}/webhook"
SECRET = Config.WEBHOOK_SECRET

def send_alert(action: str, symbol: str, qty: int, alert_id: str = None):
    payload = {
        "secret": SECRET,
        "action": action,
        "symbol": symbol,
        "qty": qty,
        "alert_id": alert_id or f"test-{int(time.time())}"
    }
    
    headers = {"Content-Type": "application/json"}
    
    print(f"\n--- Testing: {action.upper()} {qty} shares of {symbol} ---")
    try:
        response = requests.post(BASE_URL, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error sending alert: {e}")

if __name__ == "__main__":
    print(f"Starting Webhook Simulation against {BASE_URL}")
    print("Ensure 'webhook_server.py' is running before starting.")

    # 1. Test Buy SOFI (Small quantity to avoid high cost in paper)
    send_alert("buy", "SOFI", 1)

    # 2. Test Duplicate Alert (Should be blocked by risk rules or alert_id tracking)
    # Note: Our webhook_server.py marks alert as seen AFTER order is placed.
    # To test duplicate, we'd need to send same ID.
    shared_id = "test-duplicate-123"
    print("\n--- Testing Duplicate Alert ID ---")
    send_alert("buy", "F", 1, alert_id=shared_id)
    time.sleep(1)
    send_alert("buy", "F", 1, alert_id=shared_id)

    # 3. Test Unauthorized Request
    print("\n--- Testing Unauthorized Request (Wrong Secret) ---")
    bad_payload = {"secret": "wrong_secret", "action": "buy", "symbol": "AAPL", "qty": 1}
    try:
        r = requests.post(BASE_URL, json=bad_payload)
        print(f"Status Code: {r.status_code} (Expected: 401)")
    except Exception as e:
        print(f"Error: {e}")

    # 4. Test Health Check
    print("\n--- Testing Health Check ---")
    try:
        r = requests.get(f"http://localhost:{Config.PORT}/health")
        print(f"Health Check Status: {r.status_code} | Body: {r.json()}")
    except Exception as e:
        print(f"Error: {e}")

    print("\nSimulation complete. Check 'logs/tradebot.log' for detailed output.")
