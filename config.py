from dotenv import load_dotenv
import os
from dataclasses import dataclass

load_dotenv()


@dataclass(frozen=True)
class Config:
    # Security
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "change_me")

    # Broker
    BROKER: str = os.getenv("BROKER", "ALPACA")
    ALPACA_KEY: str = os.getenv("ALPACA_KEY", "")
    ALPACA_SECRET: str = os.getenv("ALPACA_SECRET", "")
    ALPACA_BASE_URL: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    ALPACA_PAPER: bool = os.getenv("ALPACA_PAPER", "true").lower() == "true"
    LIVE_TRADING_ACKNOWLEDGED: str = os.getenv("LIVE_TRADING_ACKNOWLEDGED", "")

    # Risk / account controls
    STARTING_EQUITY: float = float(os.getenv("STARTING_EQUITY", "500"))
    RISK_PER_TRADE_DOLLARS: float = float(os.getenv("RISK_PER_TRADE_DOLLARS", "1.50"))
    MAX_DAILY_LOSS_DOLLARS: float = float(os.getenv("MAX_DAILY_LOSS_DOLLARS", "7.50"))
    RISK_PCT_PER_TRADE: float = float(os.getenv("RISK_PCT_PER_TRADE", "1.0")) # 1% of equity
    MAX_DAILY_LOSS_PCT: float = float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0")) # 5% of equity
    USE_PERCENTAGE_RISK: bool = os.getenv("USE_PERCENTAGE_RISK", "false").lower() == "true"
    MAX_TRADES_PER_DAY: int = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
    MAX_OPEN_POSITIONS: int = int(os.getenv("MAX_OPEN_POSITIONS", "5"))
    MAX_POSITION_VALUE_DOLLARS: float = float(os.getenv("MAX_POSITION_VALUE_DOLLARS", "100.00"))
    MAX_ACCOUNT_DEPLOYMENT_PCT: float = float(os.getenv("MAX_ACCOUNT_DEPLOYMENT_PCT", "25.0"))
    
    # Portfolio Diversification
    MAX_POSITIONS_PER_SECTOR: int = int(os.getenv("MAX_POSITIONS_PER_SECTOR", "2"))
    MAX_EQUITY_DRAWDOWN_PCT: float = float(os.getenv("MAX_EQUITY_DRAWDOWN_PCT", "15.0")) # Circuit breaker at 15% drawdown
    
    # Backups
    ENABLE_AUTO_BACKUP: bool = os.getenv("ENABLE_AUTO_BACKUP", "true").lower() == "true"
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", "backups")

    # Trading window (local machine time)
    ALLOWED_START_HHMM: str = os.getenv("ALLOWED_START_HHMM", "0935")
    ALLOWED_END_HHMM: str = os.getenv("ALLOWED_END_HHMM", "1530")

    # Logs / state
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    RISK_STATE_FILE: str = os.getenv("RISK_STATE_FILE", "logs/risk_state.json")
    BOT_STATE_FILE: str = os.getenv("BOT_STATE_FILE", "logs/bot_state.json")
    TRADE_JOURNAL_FILE: str = os.getenv("TRADE_JOURNAL_FILE", "logs/trade_journal.jsonl")
    DAILY_SUMMARY_FILE: str = os.getenv("DAILY_SUMMARY_FILE", "logs/daily_summary.jsonl")

    # Market Data
    ALPACA_DATA_FEED: str = os.getenv("ALPACA_DATA_FEED", "iex")  # 'iex' or 'sip'

    # TradingView Screener
    USE_TV_SCREENER: bool = os.getenv("USE_TV_SCREENER", "true").lower() == "true"
    TV_SCREENER_PRICE_MIN: float = float(os.getenv("TV_SCREENER_PRICE_MIN", "1.0"))
    TV_SCREENER_PRICE_MAX: float = float(os.getenv("TV_SCREENER_PRICE_MAX", "30.0"))
    TV_SCREENER_VOLUME_MIN: float = float(os.getenv("TV_SCREENER_VOLUME_MIN", "100000"))
    TV_SCREENER_LIMIT: int = int(os.getenv("TV_SCREENER_LIMIT", "20"))

    # Strategy controls
    ENABLE_EXTENDED_HOURS: bool = os.getenv("ENABLE_EXTENDED_HOURS", "false").lower() == "true"
    ENABLE_INTERNET_RESEARCH: bool = os.getenv("ENABLE_INTERNET_RESEARCH", "true").lower() == "true"
    RESEARCH_INTERVAL_SECONDS: int = int(os.getenv("RESEARCH_INTERVAL_SECONDS", "86400")) # 24 hours
    ENABLE_NEW_ENTRIES: bool = os.getenv("ENABLE_NEW_ENTRIES", "true").lower() == "true"
    USE_LIMIT_ORDERS: bool = os.getenv("USE_LIMIT_ORDERS", "false").lower() == "true"
    LIMIT_OFFSET_PCT: float = float(os.getenv("LIMIT_OFFSET_PCT", "0.05"))
    MAX_SPREAD_PCT: float = float(os.getenv("MAX_SPREAD_PCT", "0.20")) # Tightened from 0.50
    ORDER_TIMEOUT_SECONDS: int = int(os.getenv("ORDER_TIMEOUT_SECONDS", "180"))
    MAX_CONSECUTIVE_FAILURES: int = int(os.getenv("MAX_CONSECUTIVE_FAILURES", "5"))
    AUTO_SHUTDOWN_AFTER_CLOSE: bool = os.getenv("AUTO_SHUTDOWN_AFTER_CLOSE", "true").lower() == "true"
    LIVE_MODE_WHITELIST_ONLY: bool = os.getenv("LIVE_MODE_WHITELIST_ONLY", "true").lower() == "true"
    LIVE_WHITELIST: tuple[str, ...] = tuple(
        s.strip().upper()
        for s in os.getenv("LIVE_WHITELIST", "SOFI,PLTR,F").split(",")
        if s.strip()
    )

    STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "0.75"))
    TAKE_PROFIT_PCT: float = float(os.getenv("TAKE_PROFIT_PCT", "3.0")) # Increased from 2.5
    TRAILING_STOP_PCT: float = float(os.getenv("TRAILING_STOP_PCT", "0.5")) # Enabled by default

    # Partial Take Profit Controls (Dollar based)
    PARTIAL_TP1_DOLLARS: float = float(os.getenv("PARTIAL_TP1_DOLLARS", "10.00"))
    PARTIAL_TP2_DOLLARS: float = float(os.getenv("PARTIAL_TP2_DOLLARS", "15.00"))

    # Advanced Portfolio Management
    KELLY_FRACTION: float = float(os.getenv("KELLY_FRACTION", "0.5"))
    ENABLE_NEWS_FILTER: bool = os.getenv("ENABLE_NEWS_FILTER", "true").lower() == "true"
    
    # Multi-Strategy Selection
    # Supported: TREND, RSI, BOLLINGER, MACD, BREAKOUT, BARUPDN, BOLLINGER_DIRECTED, CONSECUTIVE, 
    # GREEDY, INSIDE_BAR, KELTNER, MOMENTUM, MA_2LINE_CROSS, MA_CROSS, OUTSIDE_BAR, PIVOT_REVERSAL, 
    # PRICE_CHANNEL, ROB_BOOKER_ADX, STOCHASTIC, SUPERTREND, TECHNICAL_RATINGS, VOLTY_EXPAN_CLOSE, AGGRESSIVE, PATTERNS, CHART, AUTO_TREND
    ACTIVE_STRATEGIES: tuple[str, ...] = tuple(
        s.strip().upper()
        for s in os.getenv("ACTIVE_STRATEGIES", "TREND,RSI,BOLLINGER,MACD,BREAKOUT,MA_CROSS,STOCHASTIC,PATTERNS,CHART,AUTO_TREND").split(",")
        if s.strip()
    )

    # Flask
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # AI Configuration
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "OPENAI") # OPENAI, ANTHROPIC, etc.
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    ENABLE_AI_EVOLUTION: bool = os.getenv("ENABLE_AI_EVOLUTION", "true").lower() == "true"
    ENABLE_AI_TRADE_FILTER: bool = os.getenv("ENABLE_AI_TRADE_FILTER", "false").lower() == "true"

    # Distributed Auto-Updates
    ENABLE_AUTO_UPDATE: bool = os.getenv("ENABLE_AUTO_UPDATE", "true").lower() == "true"
    AUTO_UPDATE_BRANCH: str = os.getenv("AUTO_UPDATE_BRANCH", "main")
    AUTO_UPDATE_REMOTE: str = os.getenv("AUTO_UPDATE_REMOTE", "origin")

    # User Authentication
    SQLALCHEMY_DATABASE_URI: str = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///users.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-me")
    ALLOW_REGISTRATION: bool = os.getenv("ALLOW_REGISTRATION", "true").lower() == "true"

    # Multi-Account Log Centralization
    CENTRAL_LOG_SERVER_URL: str | None = os.getenv("CENTRAL_LOG_SERVER_URL") # e.g., http://your-ip:5000
    ENABLE_LOG_SUBMISSION: bool = os.getenv("ENABLE_LOG_SUBMISSION", "false").lower() == "true"
    SUBMIT_LOGS_EVERY_SECONDS: int = int(os.getenv("SUBMIT_LOGS_EVERY_SECONDS", "3600")) # 1 hour

    # Notifications (Discord Webhook or Pushover)
    DISCORD_WEBHOOK_URL: str | None = os.getenv("DISCORD_WEBHOOK_URL")
    PUSHOVER_USER_KEY: str | None = os.getenv("PUSHOVER_USER_KEY")
    PUSHOVER_APP_TOKEN: str | None = os.getenv("PUSHOVER_APP_TOKEN")