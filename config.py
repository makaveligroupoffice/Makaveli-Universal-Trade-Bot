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
    MAX_OPEN_POSITIONS: int = int(os.getenv("MAX_OPEN_POSITIONS", "1"))
    MAX_POSITION_VALUE_DOLLARS: float = float(os.getenv("MAX_POSITION_VALUE_DOLLARS", "100.00"))
    MAX_ACCOUNT_DEPLOYMENT_PCT: float = float(os.getenv("MAX_ACCOUNT_DEPLOYMENT_PCT", "25.0"))

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

    # Strategy controls
    ENABLE_NEW_ENTRIES: bool = os.getenv("ENABLE_NEW_ENTRIES", "true").lower() == "true"
    USE_LIMIT_ORDERS: bool = os.getenv("USE_LIMIT_ORDERS", "false").lower() == "true"
    LIMIT_OFFSET_PCT: float = float(os.getenv("LIMIT_OFFSET_PCT", "0.05"))
    MAX_SPREAD_PCT: float = float(os.getenv("MAX_SPREAD_PCT", "0.50"))
    ORDER_TIMEOUT_SECONDS: int = int(os.getenv("ORDER_TIMEOUT_SECONDS", "180"))
    MAX_CONSECUTIVE_FAILURES: int = int(os.getenv("MAX_CONSECUTIVE_FAILURES", "5"))
    AUTO_SHUTDOWN_AFTER_CLOSE: bool = os.getenv("AUTO_SHUTDOWN_AFTER_CLOSE", "true").lower() == "true"
    LIVE_MODE_WHITELIST_ONLY: bool = os.getenv("LIVE_MODE_WHITELIST_ONLY", "true").lower() == "true"
    LIVE_WHITELIST: tuple[str, ...] = tuple(
        s.strip().upper()
        for s in os.getenv("LIVE_WHITELIST", "SOFI,PLTR,F").split(",")
        if s.strip()
    )

    STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "1.0"))
    TAKE_PROFIT_PCT: float = float(os.getenv("TAKE_PROFIT_PCT", "2.0"))
    TRAILING_STOP_PCT: float = float(os.getenv("TRAILING_STOP_PCT", "0.0")) # 0.0 to disable

    # Flask
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Notifications (Discord Webhook or Pushover)
    DISCORD_WEBHOOK_URL: str | None = os.getenv("DISCORD_WEBHOOK_URL")
    PUSHOVER_USER_KEY: str | None = os.getenv("PUSHOVER_USER_KEY")
    PUSHOVER_APP_TOKEN: str | None = os.getenv("PUSHOVER_APP_TOKEN")