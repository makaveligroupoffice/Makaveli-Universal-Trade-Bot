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
            symbol = pos.symbol
            qty = pos.qty
            try:
                order = broker.sell_all(symbol)
                print(f"Closed {symbol} qty={qty} | order_id={getattr(order, 'id', None)}")
            except (APIError, ValueError) as e:
                print(f"Failed to close {symbol}: {e}")