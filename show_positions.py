from alpaca.common.exceptions import APIError

from broker_alpaca import AlpacaBroker


broker = AlpacaBroker()


if __name__ == "__main__":
    try:
        positions = broker.client.get_all_positions()
    except APIError as e:
        print("Failed to load positions:", e)
        raise

    if not positions:
        print("No open positions.")
    else:
        for pos in positions:
            print(
                f"Symbol: {pos.symbol} | Qty: {pos.qty} | "
                f"Avg Entry: {pos.avg_entry_price} | Market Value: {pos.market_value}"
            )