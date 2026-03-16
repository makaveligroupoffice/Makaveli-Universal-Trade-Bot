# Universal Trade Bot 🚀

A professional-grade, automated day trading and investment bot for the Alpaca markets. Built with multi-strategy engines, multi-asset support, and advanced risk management to grow your portfolio consistently.

## Key Features

- **Multi-Platform Design (PWA)**: The bot now includes a **Cyber-HUD Web Interface** that works on **Desktop and Mobile**. You can "download" the interface to your iOS or Android home screen for one-tap access to your trading dashboard.
- **Universal Strategy Execution**: Can handle **Long/Short Stocks**, **Bonds** (via ETFs like TLT, BND, AGG), **Options** (Calls, Puts, Spreads, Multi-legged), and **Cryptocurrencies**.
- **Sniper & Aggressive Modes**: Multi-tier entry logic that targets a **75%+ success rate** on high-conviction "Slam Dunk" trades while taking calculated chances for rapid growth.
- **Multi-Strategy Engine**: Simultaneous execution of 6 core strategy families:
    - **Trend Following (Sniper)**: Multi-SMA alignment.
    - **RSI Mean Reversion**: Oversold/Overbought reversals.
    - **Bollinger Band Bounces**: Volatility-based entries.
    - **MACD Divergence**: Momentum crossovers.
    - **Range Breakouts**: 20-bar highs with volume confirmation.
    - **Aggressive Momentum**: High-frequency plays for growth.
- **Autonomous Evolution**: The bot analyzes its own performance and **autonomously upgrades its own code** and risk parameters to adapt to changing market conditions.
- **News & Sentiment Awareness**: Integrated news filter that scans for high-impact headlines (lawsuits, investigations, etc.) to avoid "landmine" trades.
- **Portfolio Optimization**:
    - **Kelly Criterion**: Dynamic position sizing based on win rate and reward/risk ratios.
    - **Multi-Timeframe Analysis**: Aligns 1-minute trades with 1-hour "Global Trend" filters.
- **Crypto & Fractional Support**: Full support for fractional shares and crypto precision (e.g., BTC/USD).
- **Bond Market Exposure**: Dedicated Bond ETF universe (TLT, IEF, SHY, BND, AGG, LQD, HYG, JNK, TIP) included for diversified income and hedging.
- **TradingView Integration**: Built-in support for **TradingView Screener** to find high-momentum stocks and ETFs automatically.
- **Real-Time Performance Reports**: 
    - Daily PnL, Win Rate, Profit Factor, and Drawdown analysis sent directly to your phone.
    - Morning Watchlist reports on startup.
- **Real-Time Notifications**: Receive alerts via **Pushover** or **Discord** for every trade and logic update.
- **Advanced Risk Management**:
    - Automatic Daily Loss Limits (Stops trading if you hit a max loss).
    - Kelly-based position sizing for optimal compounding.
    - ATR (Average True Range) Volatility Filter.
- **Flexible Execution**:
    - Support for Market and Limit Orders.
    - Trailing Stop-Loss and Take-Profit logic.
    - **Hot-Reloading**: Update your code while the bot is running—it will pick up changes instantly without stopping.
- **Advanced Portfolio Safeguards**:
    - **Sector Diversification**: Automatically prevents overexposure to any single industry (e.g., tech, crypto, bonds).
    - **Equity Curve Drawdown Protection**: A built-in circuit breaker that halts trading if the portfolio drops below a specified percentage from its all-time high.
    - **Manual Trade Monitoring**: The bot can adopt and manage trades you open manually on the Alpaca dashboard, applying its automated trailing stops to your own picks.
- **Intelligent AI Verification**:
    - **Market Context Filtering**: The AI now reviews every trade against broader market indicators like **VIX** and **SPY** trends.
    - **AI Reasoning Logs**: Every decision the AI makes is logged to `logs/ai_reasoning.log`, providing multi-step logical justifications for every entry.
- **Professional Investment Dashboard**:
    - A real-time console (`dashboard.py`) that displays PnL, Win Rate, Projected Monthly Growth, and active positions with color-coded profit status.
- **Autonomous 'DNA' Backups**: 
    - Automatically creates timestamped zip backups of your database, configuration, and strategy code during every nightly maintenance cycle.
- **Distributed Auto-Updates**: If you share the code or run it on multiple machines, the bot can **automatically pull code updates from your GitHub repository** and apply them live via hot-reloading. This ensures all your instances are always running the latest evolved "DNA".
- **User Authentication & Multi-User Support**: On new downloads, the bot now includes a **Login and Registration** system to protect each user's data and access. This includes JWT token authentication for APIs and Flask-Login for browser sessions.
- **Multi-Account Log Centralization**: You can now link multiple bot instances to a single "Master" bot to collect and analyze paper trading logs in one place. This allows you to track the combined success rate across a network of different accounts and settings.
- **Multi-Broker Account Integration**: Each registered user can now configure their own specific broker (Alpaca) and credentials (Key, Secret, Paper/Live) directly via the API. This enables a single bot instance to trade for multiple accounts simultaneously with isolated risk management and reporting.

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

#### Desktop & Mobile Usage

1.  **Start the Web Dashboard & Webhook Server:**
    ```bash
    python3 app.py
    ```
    *This runs the central API, authentication system, and the mobile-responsive Cyber-HUD.*

2.  **Start the Trading Engine (Brain):**
    ```bash
    python3 bot_runner.py
    ```
    *This processes the strategies and executes trades.*

3.  **Expose to Mobile (via ngrok):**
    ```bash
    ngrok http 5000
    ```
    *Open the resulting `https://...` URL on your phone's browser. You will be prompted to "Add to Home Screen" for a native app experience.*

#### Additional Tools
- **Dashboard (Console):** `python3 dashboard.py` for a high-performance terminal view.
- **Manual Trade (CLI):** `python3 remote_trade.py buy AAPL 10`

## Sending a Trade Signal
Once your ngrok tunnel is up, you can send a trade signal using the provided tool:
```bash
python3 remote_trade.py buy SOFI 10 --url https://your-ngrok-url.ngrok-free.dev/webhook
```

### Viewing Network Performance
If you have multiple bots submitting logs to your central instance, you can view the aggregated performance report by running:
```bash
python3 show_network_performance.py
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
