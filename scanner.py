from __future__ import annotations

from market_data import MarketDataClient
from universe import DEFAULT_UNIVERSE


class Scanner:
    def __init__(self):
        self.data = MarketDataClient()
        self.universe = DEFAULT_UNIVERSE
        self.min_price = 1.00
        self.max_price = 30.00
        self.min_total_volume = 100_000

    def get_ranked_candidates(self) -> list[tuple[str, float]]:
        scored: list[tuple[str, float]] = []

        for symbol in self.universe:
            momentum = self._get_symbol_momentum(symbol)
            if momentum is None:
                continue
            scored.append((symbol, momentum))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:10]

    def _get_symbol_momentum(self, symbol: str) -> float | None:
        try:
            bars = self.data.get_recent_bars(symbol, minutes=20)
            if len(bars) < 10:
                return None

            first_close = float(bars[0].close)
            last_close = float(bars[-1].close)
            total_volume = sum(float(bar.volume) for bar in bars)

            if first_close <= 0:
                return None

            if not (self.min_price <= last_close <= self.max_price):
                return None

            if total_volume < self.min_total_volume:
                return None

            return (last_close - first_close) / first_close
        except (ValueError, TypeError, AttributeError):
            return None

    def get_candidates(self) -> list[str]:
        return [symbol for symbol, _score in self.get_ranked_candidates()]

    def get_recommendation_report(self) -> str:
        """
        Generates a human-readable list of top momentum stocks found in the universe.
        """
        candidates = self.get_ranked_candidates()
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