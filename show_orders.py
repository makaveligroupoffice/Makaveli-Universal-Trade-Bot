from __future__ import annotations

from market_data import MarketDataClient


class Scanner:
    def __init__(self):
        self.data = MarketDataClient()
        self.watchlist = [
            "SNDL",
            "SOFI",
            "PLTR",
            "F",
            "AAL",
            "AMC",
            "RIOT",
            "MARA",
        ]
        self.min_price = 1.00
        self.max_price = 25.00
        self.min_total_volume = 100_000

    def get_candidates(self) -> list[str]:
        scored: list[tuple[str, float]] = []

        for symbol in self.watchlist:
            try:
                bars = self.data.get_recent_bars(symbol, minutes=20)
                if len(bars) < 10:
                    continue

                first_close = float(bars[0].close)
                last_close = float(bars[-1].close)
                total_volume = sum(float(bar.volume) for bar in bars)

                if first_close <= 0:
                    continue

                if not (self.min_price <= last_close <= self.max_price):
                    continue

                if total_volume < self.min_total_volume:
                    continue

                momentum = (last_close - first_close) / first_close
                scored.append((symbol, momentum))
            except (ValueError, TypeError, AttributeError):
                continue

        scored.sort(key=lambda x: x[1], reverse=True)
        return [symbol for symbol, _score in scored[:5]]