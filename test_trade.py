from broker_alpaca import AlpacaBroker

broker = AlpacaBroker()

if __name__ == "__main__":
    acct = broker.get_account()
    print("Connected.")
    print("Status:", acct.status)
    print("Equity:", acct.equity)
    print("Buying Power:", acct.buying_power)

    symbol = "SNDL"
    qty = broker.get_position_qty(symbol)
    print(f"Current {symbol} qty:", qty)

    print("\nChoose a quick test:")
    print("1 = Buy 1 share of SNDL")
    print("2 = Sell all SNDL")
    print("3 = Show current SNDL position")

    choice = input("> ").strip()

    if choice == "1":
        order = broker.buy(symbol, 1)
        print("BUY order sent:", order)

    elif choice == "2":
        try:
            order = broker.sell_all(symbol)
            print("SELL ALL order sent:", order)
        except Exception as e:
            print("Sell failed:", e)

    elif choice == "3":
        print(f"{symbol} qty:", broker.get_position_qty(symbol))

    else:
        print("No action taken.")