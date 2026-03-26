import pandas as pd
import numpy as np
from broker_alpaca import AlpacaBroker
from strategy import Strategy
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backtester")

class BacktestingEngine:
    def __init__(self, symbols, start_date, end_date, timeframe="1Min"):
        self.broker = AlpacaBroker()
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.timeframe = timeframe
        self.strategy = Strategy()
        self.results = []

    def run(self):
        logger.info(f"Starting backtest for {self.symbols} from {self.start_date} to {self.end_date}")
        
        for symbol in self.symbols:
            logger.info(f"Processing {symbol}...")
            # Fetch historical bars
            bars = self.broker.get_historical_bars(symbol, self.start_date, self.end_date, self.timeframe)
            if bars.empty:
                logger.warning(f"No data found for {symbol}")
                continue
            
            # Simulate trades
            trades = []
            position = 0
            entry_price = 0
            
            # Strategy needs indicator history, so we iterate through time
            for i in range(50, len(bars)):
                window = bars.iloc[:i+1]
                current_price = bars.iloc[i]['close']
                timestamp = bars.index[i]
                
                # Check signals
                if position == 0:
                    should_buy, score, reason = self.strategy.should_buy(symbol, window)
                    if should_buy and score >= Config.MIN_TRADE_SCORE:
                        position = 1
                        entry_price = current_price
                        trades.append({'timestamp': timestamp, 'type': 'BUY', 'price': entry_price, 'score': score})
                        logger.info(f"BUY {symbol} at {entry_price} (Score: {score})")
                
                elif position == 1:
                    should_sell, reason = self.strategy.should_sell(symbol, current_price, entry_price, window)
                    if should_sell:
                        profit = (current_price - entry_price) / entry_price * 100
                        position = 0
                        trades.append({'timestamp': timestamp, 'type': 'SELL', 'price': current_price, 'profit_pct': profit, 'reason': reason})
                        logger.info(f"SELL {symbol} at {current_price} (Profit: {profit:.2f}%) - {reason}")

            self.results.append({'symbol': symbol, 'trades': trades})
        
        self.summarize()

    def summarize(self):
        logger.info("--- BACKTEST SUMMARY ---")
        total_pnl = 0
        total_trades = 0
        wins = 0
        
        for res in self.results:
            symbol = res['symbol']
            trades = res['trades']
            completed_trades = [t for t in trades if t['type'] == 'SELL']
            
            if not completed_trades:
                logger.info(f"{symbol}: No completed trades.")
                continue
            
            symbol_pnl = sum([t['profit_pct'] for t in completed_trades])
            symbol_wins = len([t for t in completed_trades if t['profit_pct'] > 0])
            
            logger.info(f"{symbol}: {len(completed_trades)} trades, PnL: {symbol_pnl:.2f}%, Win Rate: {symbol_wins/len(completed_trades)*100:.1f}%")
            
            total_pnl += symbol_pnl
            total_trades += len(completed_trades)
            wins += symbol_wins
            
        if total_trades > 0:
            logger.info(f"TOTAL: {total_trades} trades, Avg PnL: {total_pnl/total_trades:.2f}%, Total Win Rate: {wins/total_trades*100:.1f}%")

if __name__ == "__main__":
    import sys
    symbols = ["AAPL", "TSLA", "BTC/USD"]
    if len(sys.argv) > 1:
        symbols = sys.argv[1].split(",")
        
    engine = BacktestingEngine(symbols, "2026-01-01", "2026-03-25")
    engine.run()
