from broker_alpaca import AlpacaBroker
from config import Config

def check_connection():
    print(f"Checking connection for Alpaca (Paper: {Config.ALPACA_PAPER})...")
    try:
        broker = AlpacaBroker()
        account = broker.get_account()
        print(f"Successfully connected to Alpaca!")
        print(f"Account Number: {account.account_number}")
        print(f"Status: {account.status}")
        print(f"Equity: ${account.equity}")
        print(f"Buying Power: ${account.buying_power}")
        
        clock = broker.get_clock()
        if clock:
            print(f"Market Clock: {clock.timestamp}")
            print(f"Is Open: {clock.is_open}")
        else:
            print("Could not retrieve market clock.")
            
    except Exception as e:
        print(f"Failed to connect to Alpaca: {e}")

if __name__ == "__main__":
    check_connection()
