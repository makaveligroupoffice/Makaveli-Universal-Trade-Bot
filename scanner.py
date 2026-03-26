from __future__ import annotations
import logging
from tradingview_screener import Query, Column

from config import Config
from market_data import MarketDataClient
from universe import DEFAULT_UNIVERSE, BOND_UNIVERSE

log = logging.getLogger("tradebot")


class Scanner:
    def __init__(self):
        self.data = MarketDataClient()
        self.universe = DEFAULT_UNIVERSE + BOND_UNIVERSE
        self.min_price = Config.TV_SCREENER_PRICE_MIN
        self.max_price = Config.TV_SCREENER_PRICE_MAX
        self.min_total_volume = Config.TV_SCREENER_VOLUME_MIN

    def get_ranked_candidates(self, dynamic_config: dict | None = None) -> list[tuple[str, float]]:
        scored: list[tuple[str, float]] = []

        # Evolution: Prioritize symbols that have performed well historically
        symbol_performance = dynamic_config.get("symbol_performance", {}) if dynamic_config else {}
        
        # Decide the universe to scan
        if Config.USE_TV_SCREENER:
            universe = self.get_tv_candidates()
            # Always include bond universe for diversity if scanning custom
            universe = list(set(universe + BOND_UNIVERSE))
        else:
            universe = self.universe
        
        # Speed Optimization: Fetch momentum in parallel using asyncio
        import asyncio
        
        async def fetch_all_momentum(symbols):
            tasks = [asyncio.to_thread(self._get_symbol_momentum, s) for s in symbols]
            return await asyncio.gather(*tasks)

        try:
            # Use a new event loop if one isn't running, or use the existing one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we are already in an async context (like the new bot_runner might be)
                    # we should ideally await this, but Scanner is currently sync.
                    # For now, we'll use a thread to run the parallel fetch to not block.
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        momentums = executor.submit(lambda: asyncio.run(fetch_all_momentum(universe))).result()
                else:
                    momentums = loop.run_until_complete(fetch_all_momentum(universe))
            except RuntimeError:
                momentums = asyncio.run(fetch_all_momentum(universe))
        except Exception as e:
            log.error(f"Error in parallel momentum fetch: {e}")
            momentums = [self._get_symbol_momentum(s) for s in universe]

        for symbol, momentum in zip(universe, momentums):
            if momentum is None:
                continue
            
            # Boost score for symbols with positive historical PnL
            perf = symbol_performance.get(symbol, {"pnl": 0})
            pnl_boost = 0.01 if perf["pnl"] > 0 else 0
            
            scored.append((symbol, momentum + pnl_boost))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:50] # Increased from 10 to 50 to allow more trades throughout the day

    def get_tv_candidates(self) -> list[str]:
        """
        Fetch high-momentum candidates from TradingView Screener.
        """
        try:
            q = (Query()
                 .set_markets('america')
                 .where(
                     Column('type') == 'stock',
                     Column('subtype') == 'common',
                     Column('close').between(Config.TV_SCREENER_PRICE_MIN, Config.TV_SCREENER_PRICE_MAX),
                     Column('volume') >= Config.TV_SCREENER_VOLUME_MIN
                 )
                 .order_by('change', ascending=False)
                 .limit(Config.TV_SCREENER_LIMIT)
                 .select('name'))
            
            count, df = q.get_scanner_data()
            if count > 0 and not df.empty:
                tickers = df['name'].tolist()
                log.info(f"TV Screener found {len(tickers)} candidates.")
                return tickers
        except Exception as e:
            log.error(f"Failed to fetch TV Screener data: {e}")
        
        return self.universe # Fallback to default universe

    def _get_symbol_momentum(self, symbol: str) -> float | None:
        try:
            # Align with 30-min market regime return
            bars = self.data.get_recent_bars(symbol, minutes=30)
            if len(bars) < 15:
                return None

            first_close = float(bars[0].close)
            last_close = float(bars[-1].close)
            total_volume = sum(float(bar.volume) for bar in bars)

            if first_close <= 0:
                return None
            
            # 30-min momentum pct
            momentum_pct = (last_close - first_close) / first_close

            # Loosen price filters for Bonds (they can be > $30)
            is_bond = symbol in BOND_UNIVERSE
            effective_max_price = 250.00 if is_bond else self.max_price
            
            if not (self.min_price <= last_close <= effective_max_price):
                return None

            if total_volume < self.min_total_volume:
                return None

            return momentum_pct
        except (ValueError, TypeError, AttributeError):
            return None

    def get_candidates(self, dynamic_config: dict | None = None) -> list[str]:
        return [symbol for symbol, _score in self.get_ranked_candidates(dynamic_config)]

    def get_recommendation_report(self, dynamic_config: dict | None = None) -> str:
        """
        Generates a human-readable list of top momentum stocks found in the universe.
        """
        candidates = self.get_ranked_candidates(dynamic_config)
        if not candidates:
            return "No momentum stocks found matching criteria (Price $1-$30, Min Vol 100k)."

        lines = ["🚀 Top Momentum Picks:"]
        for symbol, score in candidates:
            pct = score * 100
            try:
                # Get current price for the report
                price = self.data.get_latest_mid_price(symbol)
                price_str = f"${price:.2f}" if price else "N/A"
                lines.append(f"• {symbol}: {price_str} (+{pct:.2f}% in 20m)")
            except:
                lines.append(f"• {symbol}: +{pct:.2f}% (20m)")

        return "\n".join(lines)