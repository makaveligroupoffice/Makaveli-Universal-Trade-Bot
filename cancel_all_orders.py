from broker_alpaca import AlpacaBroker

broker = AlpacaBroker()

if __name__ == "__main__":
    try:
        result = broker.client.cancel_orders()
        print("Cancel request sent.")
        print(result)
    except Exception as e:
        print("Failed to cancel orders:", e)