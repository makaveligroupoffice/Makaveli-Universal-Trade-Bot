from dotenv import load_dotenv
import os
from dataclasses import dataclass

load_dotenv()
load_dotenv("logs/auth.env")


@dataclass(frozen=True)
class Config:
    # Security
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "change_me")
    AUTH_TOKEN: str = os.getenv("AUTH_TOKEN", "admin-token-12345")
    SHARING_ACTIVATION_KEY: str = os.getenv("SHARING_ACTIVATION_KEY", "MAKA-VALI-PRIME-2026") # The hardcoded master key for SHARING authorization
    LICENSE_URL: str = os.getenv("LICENSE_URL", "https://raw.githubusercontent.com/makaveligroupoffice/license_server/main/status.json")
    LICENSE_ID: str = os.getenv("LICENSE_ID", "trial_user_001")
    LICENSE_CHECK_INTERVAL_SECONDS: int = int(os.getenv("LICENSE_CHECK_INTERVAL_SECONDS", "3600"))
    API_KEY_ENCRYPTION_KEY: str = os.getenv("API_KEY_ENCRYPTION_KEY", "secure-encryption-key-12345")
    IP_WHITELIST: tuple[str, ...] = tuple(s.strip() for s in os.getenv("IP_WHITELIST", "127.0.0.1").split(",") if s.strip())

    # Broker
    BROKER: str = os.getenv("BROKER", "ALPACA")
    
    # Paper Credentials (for testing)
    ALPACA_PAPER_KEY: str = os.getenv("ALPACA_PAPER_KEY", "")
    ALPACA_PAPER_SECRET: str = os.getenv("ALPACA_PAPER_SECRET", "")
    
    # Live Credentials (for real money)
    ALPACA_LIVE_KEY: str = os.getenv("ALPACA_LIVE_KEY", "")
    ALPACA_LIVE_SECRET: str = os.getenv("ALPACA_LIVE_SECRET", "")

    # Mode Selector
    ALPACA_PAPER: bool = os.getenv("ALPACA_PAPER", "true").lower() == "true"
    
    # Master Safety Toggles
    LIVE_MODE_ENABLED: bool = os.getenv("LIVE_MODE_ENABLED", "false").lower() == "true"
    LIVE_TRADING_ACKNOWLEDGED: str = os.getenv("LIVE_TRADING_ACKNOWLEDGED", "")

    # Active Key Selection (Dynamic Methods)
    @classmethod
    def get_alpaca_key(cls) -> str:
        return cls.ALPACA_PAPER_KEY if cls.ALPACA_PAPER else cls.ALPACA_LIVE_KEY

    @classmethod
    def get_alpaca_secret(cls) -> str:
        return cls.ALPACA_PAPER_SECRET if cls.ALPACA_PAPER else cls.ALPACA_LIVE_SECRET

    @classmethod
    def get_alpaca_base_url(cls) -> str:
        return "https://paper-api.alpaca.markets" if cls.ALPACA_PAPER else "https://api.alpaca.markets"

    # CRISIS MODE
    AUTO_HEDGE_ENABLED: bool = os.getenv("AUTO_HEDGE_ENABLED", "true").lower() == "true"
    STARTING_EQUITY: float = float(os.getenv("STARTING_EQUITY", "500"))
    RISK_PER_TRADE_DOLLARS: float = float(os.getenv("RISK_PER_TRADE_DOLLARS", "1.50"))
    MAX_DAILY_LOSS_DOLLARS: float = float(os.getenv("MAX_DAILY_LOSS_DOLLARS", "7.50"))
    MAX_WEEKLY_LOSS_DOLLARS: float = float(os.getenv("MAX_WEEKLY_LOSS_DOLLARS", "25.00"))
    RISK_PCT_PER_TRADE: float = float(os.getenv("RISK_PCT_PER_TRADE", "0.5")) # 0.5-1% per trade MAX
    MAX_DAILY_LOSS_PCT: float = float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0")) # 2-3% daily loss MAX
    MAX_WEEKLY_LOSS_PCT: float = float(os.getenv("MAX_WEEKLY_LOSS_PCT", "6.0")) # 5-6% weekly loss MAX
    MIN_RISK_REWARD_RATIO: float = float(os.getenv("MIN_RISK_REWARD_RATIO", "2.0")) # 1:2 minimum
    MAX_CORRELATION_THRESHOLD: float = float(os.getenv("MAX_CORRELATION_THRESHOLD", "0.7"))
    USE_PERCENTAGE_RISK: bool = os.getenv("USE_PERCENTAGE_RISK", "false").lower() == "true"
    MAX_TRADES_PER_DAY: int = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
    MAX_OPEN_POSITIONS: int = int(os.getenv("MAX_OPEN_POSITIONS", "5"))
    MAX_POSITION_VALUE_DOLLARS: float = float(os.getenv("MAX_POSITION_VALUE_DOLLARS", "100.00"))
    
    # Volatility and Dynamic Risk Settings
    ATR_MULTIPLIER: float = float(os.getenv("ATR_MULTIPLIER", "2.0"))
    VOL_SCALING_ENABLED: bool = os.getenv("VOL_SCALING_ENABLED", "True").lower() == "true"
    VOL_SCALING_FACTOR: float = float(os.getenv("VOL_SCALING_FACTOR", "1.0")) # 1.0 = normal, < 1.0 = more conservative
    KELLY_FRACTION: float = float(os.getenv("KELLY_FRACTION", "0.5"))
    MAX_ACCOUNT_DEPLOYMENT_PCT: float = float(os.getenv("MAX_ACCOUNT_DEPLOYMENT_PCT", "25.0"))
    
    # Portfolio Diversification
    MAX_POSITIONS_PER_SECTOR: int = int(os.getenv("MAX_POSITIONS_PER_SECTOR", "2"))
    MAX_EQUITY_DRAWDOWN_PCT: float = float(os.getenv("MAX_EQUITY_DRAWDOWN_PCT", "15.0")) # Circuit breaker at 15% drawdown
    
    # Backups
    ENABLE_AUTO_BACKUP: bool = os.getenv("ENABLE_AUTO_BACKUP", "true").lower() == "true"
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", "backups")

    # Trading window (local machine time)
    ALLOWED_START_HHMM: str = os.getenv("ALLOWED_START_HHMM", "0930")
    ALLOWED_END_HHMM: str = os.getenv("ALLOWED_END_HHMM", "2000")

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
    ENABLE_EXTENDED_HOURS: bool = os.getenv("ENABLE_EXTENDED_HOURS", "true").lower() == "true"
    TRADE_COOLDOWN_MINUTES: int = int(os.getenv("TRADE_COOLDOWN_MINUTES", "30")) # Cooldown after exit
    ENABLE_INTERNET_RESEARCH: bool = os.getenv("ENABLE_INTERNET_RESEARCH", "true").lower() == "true"
    RESEARCH_INTERVAL_SECONDS: int = int(os.getenv("RESEARCH_INTERVAL_SECONDS", "86400")) # 24 hours
    ENABLE_NEW_ENTRIES: bool = os.getenv("ENABLE_NEW_ENTRIES", "true").lower() == "true"
    USE_LIMIT_ORDERS: bool = os.getenv("USE_LIMIT_ORDERS", "true").lower() == "true"
    LIMIT_OFFSET_PCT: float = float(os.getenv("LIMIT_OFFSET_PCT", "0.01"))
    
    # Ultimate Bot - Self Optimization
    ENABLE_STRATEGY_OPTIMIZATION: bool = os.getenv("ENABLE_STRATEGY_OPTIMIZATION", "true").lower() == "true"
    OPTIMIZATION_INTERVAL_DAYS: int = int(os.getenv("OPTIMIZATION_INTERVAL_DAYS", "7"))
    OPTIMIZED_PARAMS_FILE: str = "logs/optimized_params.json"
    MAX_SPREAD_PCT: float = float(os.getenv("MAX_SPREAD_PCT", "0.15")) # Tightened from 0.20
    ORDER_TIMEOUT_SECONDS: int = int(os.getenv("ORDER_TIMEOUT_SECONDS", "120"))
    MAX_CONSECUTIVE_FAILURES: int = int(os.getenv("MAX_CONSECUTIVE_FAILURES", "5"))
    AUTO_SHUTDOWN_AFTER_CLOSE: bool = os.getenv("AUTO_SHUTDOWN_AFTER_CLOSE", "true").lower() == "true"
    LIVE_MODE_WHITELIST_ONLY: bool = os.getenv("LIVE_MODE_WHITELIST_ONLY", "true").lower() == "true"
    LIVE_WHITELIST: tuple[str, ...] = tuple(
        s.strip().upper()
        for s in os.getenv("LIVE_WHITELIST", "SOFI,PLTR,F").split(",")
        if s.strip()
    )

    # Consistency Loop & Trade Score
    MIN_TRADE_SCORE_THRESHOLD: float = float(os.getenv("MIN_TRADE_SCORE_THRESHOLD", "75.0"))
    MAX_SCALPING_TRADES_PER_DAY: int = int(os.getenv("MAX_SCALPING_TRADES_PER_DAY", "10"))
    MAX_SWING_TRADES_PER_DAY: int = int(os.getenv("MAX_SWING_TRADES_PER_DAY", "5"))
    ENABLE_REENTRY_LOGIC: bool = os.getenv("ENABLE_REENTRY_LOGIC", "true").lower() == "true"
    REENTRY_PULLBACK_PCT: float = float(os.getenv("REENTRY_PULLBACK_PCT", "0.5"))
    EXIT_LADDER_ENABLED: bool = os.getenv("EXIT_LADDER_ENABLED", "true").lower() == "true"
    SIGNAL_DELAY_FILTER_SECONDS: int = int(os.getenv("SIGNAL_DELAY_FILTER_SECONDS", "30"))
    
    # Liquidity & Order Flow
    LIQUIDITY_POOL_LOOKBACK: int = int(os.getenv("LIQUIDITY_POOL_LOOKBACK", "50"))
    VOLUME_DELTA_EMA_PERIOD: int = int(os.getenv("VOLUME_DELTA_EMA_PERIOD", "14"))
    ATR_SL_MULTIPLIER: float = float(os.getenv("ATR_SL_MULTIPLIER", "1.0"))
    ATR_TP_MULTIPLIER: float = float(os.getenv("ATR_TP_MULTIPLIER", "3.0"))
    BREAK_EVEN_PROFIT_PCT: float = float(os.getenv("BREAK_EVEN_PROFIT_PCT", "0.75")) # Move SL to entry at 0.75% profit
    ENABLE_DYNAMIC_ATR_EXITS: bool = os.getenv("ENABLE_DYNAMIC_ATR_EXITS", "true").lower() == "true"
    TIME_BASED_EXIT_MINUTES: int = int(os.getenv("TIME_BASED_EXIT_MINUTES", "0")) # 0 = disabled
    PROFIT_LOCK_PCT: float = float(os.getenv("PROFIT_LOCK_PCT", "2.5")) # Lock in profit at 2.5%
    PROFIT_LOCK_RETAIN_PCT: float = float(os.getenv("PROFIT_LOCK_RETAIN_PCT", "80.0")) # Keep 80% of peak profit
    
    # Capital Growth & Withdraw
    PROFIT_WITHDRAWAL_THRESHOLD_DOLLARS: float = float(os.getenv("PROFIT_WITHDRAWAL_THRESHOLD_DOLLARS", "100.00"))
    PROFIT_SPLIT_TRADING_PCT: float = float(os.getenv("PROFIT_SPLIT_TRADING_PCT", "70.0")) # 70% stays in trading
    PROFIT_SPLIT_COLD_STORAGE_PCT: float = float(os.getenv("PROFIT_SPLIT_COLD_STORAGE_PCT", "30.0")) # 30% to cold storage
    AUTO_REINVEST_PROFITS: bool = os.getenv("AUTO_REINVEST_PROFITS", "true").lower() == "true"
    VAULT_TRANSFER_NOTIFICATION_ONLY: bool = os.getenv("VAULT_TRANSFER_NOTIFICATION_ONLY", "true").lower() == "true"

    # Market Regime Intelligence
    CHOP_ADX_THRESHOLD: float = float(os.getenv("CHOP_ADX_THRESHOLD", "20.0")) # Below 20 is chop
    SESSION_AWARE_TRADING: bool = os.getenv("SESSION_AWARE_TRADING", "true").lower() == "true"
    
    # Multi-Bot Scaling
    ENABLE_MULTI_BOT_MODE: bool = os.getenv("ENABLE_MULTI_BOT_MODE", "false").lower() == "true"
    MASTER_RISK_CONTROL_ENABLED: bool = os.getenv("MASTER_RISK_CONTROL_ENABLED", "true").lower() == "true"

    # Trade Quality Filter
    MIN_TRADE_QUALITY_SCORE: float = float(os.getenv("MIN_TRADE_QUALITY_SCORE", "75.0"))
    
    # CRISIS MODE
    AUTO_HEDGE_ENABLED: bool = os.getenv("AUTO_HEDGE_ENABLED", "true").lower() == "true"
    FLASH_CRASH_PROTECTION_PCT: float = float(os.getenv("FLASH_CRASH_PROTECTION_PCT", "5.0")) # 5% drop in 1 min triggers shutdown
    VOLATILITY_SPIKE_KILL_SWITCH: bool = os.getenv("VOLATILITY_SPIKE_KILL_SWITCH", "true").lower() == "true"
    
    # --- Number One Bot - Omniscient Execution ---
    ENABLE_OMNISCIENT_EXECUTION: bool = os.getenv("ENABLE_OMNISCIENT_EXECUTION", "true").lower() == "true"
    OMNISCIENT_MID_PRICE_LIMIT: bool = os.getenv("OMNISCIENT_MID_PRICE_LIMIT", "true").lower() == "true"
    OMNISCIENT_MAX_RETRIES: int = int(os.getenv("OMNISCIENT_MAX_RETRIES", "3"))
    OMNISCIENT_RETRY_DELAY_SECONDS: int = int(os.getenv("OMNISCIENT_RETRY_DELAY_SECONDS", "5"))
    
    # --- Number One Bot - Fractal Multi-Timeframe ---
    ENABLE_FRACTAL_MTF: bool = os.getenv("ENABLE_FRACTAL_MTF", "true").lower() == "true"
    MTF_TIMEFRAMES: tuple[str, ...] = ("1Min", "5Min", "15Min")
    
    # --- Number One Bot - Liquidity Mapping ---
    ENABLE_LIQUIDITY_MAPPING: bool = os.getenv("ENABLE_LIQUIDITY_MAPPING", "true").lower() == "true"
    LIQUIDITY_VOL_THRESHOLD: float = float(os.getenv("LIQUIDITY_VOL_THRESHOLD", "2.5"))
    
    NEWS_SHOCK_PAUSE_MINUTES: int = int(os.getenv("NEWS_SHOCK_PAUSE_MINUTES", "30"))
    ECONOMIC_CALENDAR_FILTER: bool = os.getenv("ECONOMIC_CALENDAR_FILTER", "true").lower() == "true" # CPI, FOMC
    ECONOMIC_CALENDAR_BUFFER_MINUTES: int = int(os.getenv("ECONOMIC_CALENDAR_BUFFER_MINUTES", "30")) # Block 30m before/after
    NEWS_SOURCE_RANKING: tuple[str, ...] = tuple(s.strip() for s in os.getenv("NEWS_SOURCE_RANKING", "FOREX_FACTORY,TRADING_ECONOMICS,INVESTING_COM").split(",") if s.strip())
    KILL_SWITCH_CONSECUTIVE_LOSSES: int = int(os.getenv("KILL_SWITCH_CONSECUTIVE_LOSSES", "3"))

    # AI Layer
    AI_JOURNALING_ENABLED: bool = os.getenv("AI_JOURNALING_ENABLED", "true").lower() == "true"
    AI_EVALUATOR_ENABLED: bool = os.getenv("AI_EVALUATOR_ENABLED", "true").lower() == "true"

    STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "2.0")) # Loosened from 1.5 to handle volatility
    TAKE_PROFIT_PCT: float = float(os.getenv("TAKE_PROFIT_PCT", "4.0")) # Increased to capture more profit on runners
    TRAILING_STOP_PCT: float = float(os.getenv("TRAILING_STOP_PCT", "1.0")) # Loosened from 0.75
    TRAILING_STOP_ACTIVATION_PCT: float = float(os.getenv("TRAILING_STOP_ACTIVATION_PCT", "1.0")) # Start trailing later (at 1% profit)

    # Intraday Liquidation
    INTRA_DAY_MODE_ONLY: bool = os.getenv("INTRA_DAY_MODE_ONLY", "true").lower() == "true"
    MARKET_CLOSE_LIQUIDATION_WINDOW_MINS: int = int(os.getenv("MARKET_CLOSE_LIQUIDATION_WINDOW_MINS", "15"))

    # Partial Take Profit Controls (Dollar based)
    ENABLE_PARTIAL_ENTRIES: bool = os.getenv("ENABLE_PARTIAL_ENTRIES", "true").lower() == "true"
    PARTIAL_ENTRY_PCT: float = float(os.getenv("PARTIAL_ENTRY_PCT", "50.0")) # Buy 50% now, 50% later on trend confirmation
    PARTIAL_TP1_DOLLARS: float = float(os.getenv("PARTIAL_TP1_DOLLARS", "10.00"))
    PARTIAL_TP2_DOLLARS: float = float(os.getenv("PARTIAL_TP2_DOLLARS", "15.00"))
    SHORT_EXIT_PROFIT_DOLLARS: float = float(os.getenv("SHORT_EXIT_PROFIT_DOLLARS", "5.00"))

    # Advanced Portfolio Management
    KELLY_FRACTION: float = float(os.getenv("KELLY_FRACTION", "0.5"))
    ENABLE_NEWS_FILTER: bool = os.getenv("ENABLE_NEWS_FILTER", "true").lower() == "true"
    NEWS_SPIKE_ATR_THRESHOLD: float = float(os.getenv("NEWS_SPIKE_ATR_THRESHOLD", "3.0")) # 3x ATR spike triggers news filter
    NEWS_SPIKE_VOLUME_THRESHOLD: float = float(os.getenv("NEWS_SPIKE_VOLUME_THRESHOLD", "4.0")) # 4x RVOL triggers news filter
    NEWS_FILTER_LOOKBACK: int = int(os.getenv("NEWS_FILTER_LOOKBACK", "10")) # Bars to look back for recent spikes
    
    # Multi-Strategy Selection
    # Supported: TREND, RSI, BOLLINGER, MACD, BREAKOUT, BARUPDN, BOLLINGER_DIRECTED, CONSECUTIVE, 
    # GREEDY, INSIDE_BAR, KELTNER, MOMENTUM, MA_2LINE_CROSS, MA_CROSS, OUTSIDE_BAR, PIVOT_REVERSAL, 
    # PRICE_CHANNEL, ROB_BOOKER_ADX, STOCHASTIC, SUPERTREND, TECHNICAL_RATINGS, VOLTY_EXPAN_CLOSE, AGGRESSIVE, PATTERNS, CHART, AUTO_TREND, SCALPING
    ACTIVE_STRATEGIES: tuple[str, ...] = tuple(
        s.strip().upper()
        for s in os.getenv("ACTIVE_STRATEGIES", "TREND,RSI,BOLLINGER,MACD,BREAKOUT,MA_CROSS,STOCHASTIC,PATTERNS,CHART,AUTO_TREND,SCALPING").split(",")
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
    ENABLE_REGIME_FILTER: bool = os.getenv("ENABLE_REGIME_FILTER", "true").lower() == "true"
    ENABLE_WITHDRAWAL_ALERTS: bool = os.getenv("ENABLE_WITHDRAWAL_ALERTS", "true").lower() == "true"
    ENABLE_LOSS_STREAK_PAUSE: bool = os.getenv("ENABLE_LOSS_STREAK_PAUSE", "true").lower() == "true"
    ENABLE_DRAWDOWN_SIZE_REDUCTION: bool = os.getenv("ENABLE_DRAWDOWN_SIZE_REDUCTION", "true").lower() == "true"
    
    STOP_LOSS_METHOD: str = os.getenv("STOP_LOSS_METHOD", "ATR")
    TAKE_PROFIT_METHOD: str = os.getenv("TAKE_PROFIT_METHOD", "ATR")
    ENABLE_BREAK_EVEN_STOP: bool = os.getenv("ENABLE_BREAK_EVEN_STOP", "true").lower() == "true"
    ENABLE_TRAILING_STOP: bool = os.getenv("ENABLE_TRAILING_STOP", "true").lower() == "true"
    ENABLE_REGIME_FILTER_FOR_FAST_AUDIT: bool = True # Flag to ensure availability

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

    # Crypto Long-Term Investment
    CRYPTO_INVEST_EQUITY_PCT: float = float(os.getenv("CRYPTO_INVEST_EQUITY_PCT", "1.0")) # 1% of total equity for crypto long-term
    CRYPTO_WHITELIST: tuple[str, ...] = tuple(
        s.strip().upper()
        for s in os.getenv("CRYPTO_WHITELIST", "BTC/USD,ETH/USD,SOL/USD").split(",")
        if s.strip()
    )

    # 31-50 META-RISK & ADVANCED INTELLIGENCE
    GLOBAL_RISK_CAP_PCT: float = float(os.getenv("GLOBAL_RISK_CAP_PCT", "20.0")) # Max 20% total portfolio risk
    RISK_PARITY_ENABLED: bool = os.getenv("RISK_PARITY_ENABLED", "true").lower() == "true"
    EDGE_DECAY_WINDOW: int = int(os.getenv("EDGE_DECAY_WINDOW", "50")) # Rolling 50 trades
    EDGE_DECAY_THRESHOLD_WR: float = float(os.getenv("EDGE_DECAY_THRESHOLD_WR", "45.0")) # Disable if WR < 45%
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "70.0")) # 0-100 score
    ENTRY_DELAY_SECONDS: int = int(os.getenv("ENTRY_DELAY_SECONDS", "0")) # Wait X seconds before execution
    ADAPTIVE_TP_ENABLED: bool = os.getenv("ADAPTIVE_TP_ENABLED", "true").lower() == "true"
    EARLY_EXIT_MOMENTUM_LOSS: bool = os.getenv("EARLY_EXIT_MOMENTUM_LOSS", "true").lower() == "true"
    CASHFLOW_WEEKLY_TARGET_PCT: float = float(os.getenv("CASHFLOW_WEEKLY_TARGET_PCT", "2.0")) # 2% weekly goal
    MANUAL_APPROVAL_MODE: bool = os.getenv("MANUAL_APPROVAL_MODE", "false").lower() == "true"
    DECISION_DELAY_MINS: int = int(os.getenv("DECISION_DELAY_MINS", "1")) # 1 min delay for confirmation
    ADAPTIVE_FREQUENCY_CONTROL: bool = os.getenv("ADAPTIVE_FREQUENCY_CONTROL", "true").lower() == "true"
    MARKET_STRESS_THRESHOLD: float = float(os.getenv("MARKET_STRESS_THRESHOLD", "2.0")) # Z-score for vol/corr spikes
    EXPERIMENTAL_STRATEGIES: tuple[str, ...] = tuple(
        s.strip().upper()
        for s in os.getenv("EXPERIMENTAL_STRATEGIES", "").split(",")
        if s.strip()
    )

    # Notifications (Discord Webhook or Pushover)
    DISCORD_WEBHOOK_URL: str | None = os.getenv("DISCORD_WEBHOOK_URL")
    PUSHOVER_USER_KEY: str | None = os.getenv("PUSHOVER_USER_KEY")
    PUSHOVER_APP_TOKEN: str | None = os.getenv("PUSHOVER_APP_TOKEN")
    TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: str | None = os.getenv("TELEGRAM_CHAT_ID")
    EMAIL_SMTP_SERVER: str | None = os.getenv("EMAIL_SMTP_SERVER")
    EMAIL_SMTP_PORT: int = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    EMAIL_USER: str | None = os.getenv("EMAIL_USER")
    EMAIL_PASS: str | None = os.getenv("EMAIL_PASS")
    EMAIL_RECEIVER: str | None = os.getenv("EMAIL_RECEIVER")
    SMS_TWILIO_SID: str | None = os.getenv("SMS_TWILIO_SID")
    SMS_TWILIO_TOKEN: str | None = os.getenv("SMS_TWILIO_TOKEN")
    SMS_TWILIO_NUMBER: str | None = os.getenv("SMS_TWILIO_NUMBER")
    SMS_RECEIVER: str | None = os.getenv("SMS_RECEIVER")

    # 71-80 WEEKLY CASHFLOW & BANK WITHDRAWAL
    BANK_WITHDRAWAL_ENABLED: bool = os.getenv("BANK_WITHDRAWAL_ENABLED", "false").lower() == "true"
    BANK_ACCOUNT_ID: str | None = os.getenv("BANK_ACCOUNT_ID") # Alpaca ACH relationship ID
    MIN_CAPITAL_RESERVE: float = float(os.getenv("MIN_CAPITAL_RESERVE", "100000.0")) # Never withdraw below this
    WITHDRAWAL_DAY_OF_WEEK: int = int(os.getenv("WITHDRAWAL_DAY_OF_WEEK", "4")) # 4 = Friday
    WITHDRAWAL_TIME_HHMM: str = os.getenv("WITHDRAWAL_TIME_HHMM", "1630") # 4:30 PM (after market close)
    AUTO_WITHDRAW_PROFITS: bool = os.getenv("AUTO_WITHDRAW_PROFITS", "false").lower() == "true"