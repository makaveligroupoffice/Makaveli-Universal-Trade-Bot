# Universal Trade Bot 🚀

A professional-grade, automated day trading bot for the Alpaca markets. Built with multi-stock support, real-time risk management, and mobile notifications to keep you informed of every trade.

## Key Features

- **Universal Strategy Execution**: Can handle **Long/Short Stocks**, **Bonds** (via ETFs like TLT, BND, AGG), **Options** (Calls, Puts, Spreads, Multi-legged), and **Cryptocurrencies**.
- **Crypto & Fractional Support**: Full support for fractional shares and crypto precision (e.g., BTC/USD).
- **Bond Market Exposure**: Dedicated Bond ETF universe (TLT, IEF, SHY, BND, AGG, LQD, HYG, JNK, TIP) included for diversified income and hedging.
- **TradingView Integration**: Built-in support for **TradingView Screener** to find high-momentum stocks and ETFs automatically.
- **Options Support**:
    - **Single-Leg**: Long/Short Calls and Puts.
    - **Multi-Legged**: Spreads (Bull Call, Bear Put, etc.), Straddles, Covered Calls, and Cash-Secured Puts.
    - **Advanced Data**: Fetches Option Chains and Greeks (Delta, Gamma, etc.) for informed trading.
- **Multi-Stock Support**: Capable of managing up to 5 concurrent positions at once.
- **Real-Time Notifications**: Receive alerts on your phone (via **Pushover** or **Discord**) for:
    - Bot Startup/Shutdown (synced with market hours).
    - Trade Execution (Buy/Sell/Short/Cover) with filled price and quantity.
    - Profit/Loss summaries for every closed trade.
    - Daily performance reports (Daily PnL).
    - Critical error alerts.
- **Advanced Risk Management**:
    - Automatic Daily Loss Limits (Stops trading if you hit a max loss).
    - Max Trades per Day caps.
    - Compounding Risk Model (Risk a percentage of your total equity).
    - ATR (Average True Range) Volatility Filter.
- **Flexible Execution**:
    - Support for Market and Limit Orders (with configurable offsets).
    - Trailing Stop-Loss and Take-Profit logic.
- **Remote Trading**: Use the included `remote_trade.py` tool to send trade signals from your phone or external scripts.
- **Self-Correction**: Periodic performance analysis to adjust stop-loss/take-profit settings automatically.

## Project Structure

- `bot_runner.py`: The "brain" of the bot. Manages positions and handles execution logic.
- `webhook_server.py`: Listens for incoming trade signals (from TradingView or `remote_trade.py`).
- `config.py`: Centralized configuration management.
- `risk.py`: Logic for daily loss limits and position sizing.
- `strategy.py`: Technical analysis and entry/exit strategy definitions.
- `broker_alpaca.py`: Integration with the Alpaca API.
- `notifications.py`: Handler for Pushover and Discord alerts.
- `remote_trade.py`: CLI tool for manual/remote trade execution.

## Getting Started

### 1. Prerequisites
- Python 3.10+
- Alpaca API Account (Paper or Live)
- ngrok (for receiving external signals)

### 2. Installation
```bash
git clone https://github.com/makaveligroupoffice/tradebot.git
cd tradebot
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the project root and add your keys (never share this file!):
```bash
# Alpaca Keys
ALPACA_KEY=your_key_here
ALPACA_SECRET=your_secret_here
ALPACA_PAPER=true

# Security
WEBHOOK_SECRET=your_bot_secret_here

# Notifications (Pushover)
PUSHOVER_USER_KEY=your_user_key
PUSHOVER_APP_TOKEN=your_app_token

# Risk Settings
USE_PERCENTAGE_RISK=true
RISK_PCT_PER_TRADE=1.5
MAX_DAILY_LOSS_PCT=5.0
```

### 4. Running the Bot
Open three separate terminals:

**Terminal 1 (Server):**
```bash
python3 webhook_server.py
```

**Terminal 2 (Runner):**
```bash
python3 bot_runner.py
```

**Terminal 3 (Tunnel):**
```bash
ngrok http 5000
```

## Sending a Trade Signal
Once your ngrok tunnel is up, you can send a trade signal using the provided tool:
```bash
python3 remote_trade.py buy SOFI 10 --url https://your-ngrok-url.ngrok-free.dev/webhook
```

### Options Webhook Format (JSON)
You can send complex option signals via the `/webhook` endpoint:
```json
{
  "action": "option",
  "symbol": "AAPL",
  "option_symbol": "AAPL260618C00200000",
  "side": "buy",
  "intent": "buy_to_open",
  "qty": 1,
  "secret": "your_bot_secret"
}
```
For multi-legged spreads:
```json
{
  "action": "option",
  "symbol": "AAPL",
  "legs": [
    {"symbol": "AAPL260618C00200000", "ratio_qty": 1, "side": "buy", "position_intent": "buy_to_open"},
    {"symbol": "AAPL260618C00210000", "ratio_qty": 1, "side": "sell", "position_intent": "sell_to_open"}
  ],
  "qty": 1,
  "secret": "your_bot_secret"
}
```

## Security Note
This bot includes a `.gitignore` file that prevents your `.env` and `logs/` from being uploaded to GitHub. Always double-check your repository before sharing.

## Disclaimer
Trading stocks involves significant risk. This bot is provided as-is for educational purposes. Always test in **Paper Trading** mode before using real capital.
