# Makaveli Universal Trade Bot 🚀

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
- **Deep Reading & YouTube Learning**: 
    - **YouTube Ingestion**: Feed the bot any trading video URL; it will analyze the transcript and implement the strategy into `strategy.py`.
    - **Universal Knowledge Synthesis**: Synthesizes actionable rules from 25+ trading classics (e.g., *Reminiscences of a Stock Operator*) to refine its core logic.
- **Advanced News Engine**: 
    - **Macro Filtering**: Automatically blocks trading 15-30 minutes before/after major events like **CPI, FOMC, and NFP**.
    - **Multi-Source Aggregation**: Pulls high-impact news from **Forex Factory, Trading Economics, and Investing.com**.
- **Portfolio Brain (Meta-Risk Engine)**: 
    - **Global Risk Cap**: Manages risk across all active bots and strategies (max 0.5% - 1% per trade).
    - **Market DNA Profiling**: Adapts behavior per asset (BTC = trend-driven, Altcoins = volatility-driven).
    - **Confidence Engine**: Only executes trades with a **75+ quality score** based on trend, volume, and liquidity alignment.
- **Liquidity & Trap Detection (SMC)**: 
    - **Smart Money Concepts**: Detects Liquidity Sweeps, Order Imbalance, and Fake Breakouts.
    - **Liquidity Pool Mapping**: Hunts for equal highs/lows and stop clusters.
- **Crypto Long-Term Investment**: 
    - **Scan & Invest**: AI-driven evaluation of BTC, ETH, and SOL for long-term holding.
    - **Withdrawal Alerts**: Automatically prompts "Withdraw to Tangem" when settled assets are ready for cold storage.
- **Multi-Bot Scaling**: 
    - Orchestrates specialized **Scalper, Swing, and Trend Follower** bots under a Master Risk Controller.
    - **Heartbeat Monitoring**: Ensures 24/7 uptime with automated failover and error recovery.
- **Advanced Licensing & Revocation**: 
    - **Remote Kill Switch**: Allows the owner to revoke access remotely via a centralized license server if needed.
    - **Master Auth Token**: Secured via `logs/auth.env` and required for all high-risk operations (Kill Switch, Authorization, Token Rotation).
- **Weekly Fast Audit Reports**: 
    - Generates a professional PDF/Text audit every Friday at market close.
    - Tracks Risk, Entries, Exits, Performance (Win Rate, Profit Factor), and Protection status.
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
    - A real-time console (`dashboard.py`) and **Cyber-HUD Web Interface** (`app.py`) that displays PnL, Win Rate, and active positions.
    - **Simple Download Feature**: Export your trade history to CSV or download the bot's source code as a ZIP directly from the web dashboard for easy deployment across devices.
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
- `intelligence.py`: Confidence engine and market DNA profiling.
- `multi_bot.py`: Multi-bot architecture and orchestrator.
- `news_engine.py`: Macro news aggregator and economic calendar.
- `strategy.py`: Technical analysis and entry/exit strategy definitions.
- `license_manager.py`: Remote revocation and license status checks.
- `crypto_investor.py`: Long-term crypto scanning and investment evaluation.
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
1. **Security Setup (Master Token)**: Run the following to generate your `logs/auth.env` file. This token is required for standard management operations (Kill Switch, AI Learning).
```bash
python3 generate_token.py
```
2. **Sharing Authorization**: On new machines, the bot will be locked. To authorize the bot for use, you must provide the **SHARING_ACTIVATION_KEY** (provided by the bot owner) via the Web HUD API.
3. **Environment Variables**: Create a `.env` file in the project root and add your keys (never share this file!):
```bash
# Alpaca Keys
ALPACA_KEY=your_key_here
ALPACA_SECRET=your_secret_here
ALPACA_PAPER=true

# Security
WEBHOOK_SECRET=your_bot_secret_here
AUTH_TOKEN=your_token_from_logs_auth_env  # Or leave to load automatically

# Licensing
LICENSE_ID=trial_user_001
LICENSE_URL=https://.../status.json
```

### 4. Running the Bot

#### Desktop & Mobile Usage

1.  **Mobile-Controllable Interface:** The Cyber-HUD now allows you to **Start and Stop the Trading Engine** directly from your phone. Simply toggle the "Bot Active" switch in the mobile web dashboard to pause or resume market scanning and execution.

2.  **Start the Web Dashboard & Webhook Server:**
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
