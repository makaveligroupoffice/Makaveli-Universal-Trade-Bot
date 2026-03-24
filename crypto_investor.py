import logging
import threading
import time
from datetime import datetime
from config import Config
from broker_alpaca import AlpacaBroker
from ai_engine import AIEngine
from notifications import send_notification
from market_data import MarketDataClient

log = logging.getLogger("tradebot")

class CryptoInvestor:
    """
    Automates scanning for long-term crypto investments and manages purchases.
    Integrates with Alpaca for execution and prepares notifications for cold storage transfers.
    """
    def __init__(self, broker=None):
        self.broker = broker or AlpacaBroker()
        self.ai = AIEngine()
        self.market_data = MarketDataClient()

    def scan_and_invest(self):
        """
        Main loop for crypto scanning and investment.
        """
        log.info("Starting long-term crypto investment scan...")
        
        # 1. Get current account equity
        try:
            equity = float(self.broker.get_account_equity())
            invest_amount = equity * (Config.CRYPTO_INVEST_EQUITY_PCT / 100.0)
        except Exception as e:
            log.error(f"Failed to get account equity for crypto investment: {e}")
            return

        # 2. Analyze whitelist via AI
        candidates = Config.CRYPTO_WHITELIST
        for symbol in candidates:
            try:
                if self._should_invest_long_term(symbol):
                    log.info(f"AI confirms {symbol} as a strong long-term investment. Buying ${invest_amount:.2f}...")
                    
                    if invest_amount >= 1.0:
                        self._execute_crypto_buy(symbol, invest_amount)
                    else:
                        # Recommend anyway if amount is too small
                        msg = f"💡 AI recommends {symbol} as a strong long-term investment candidate, but your current investment amount (${invest_amount:.2f}) is too small to execute automatically.\n"
                        msg += f"⚠️ **WITHDRAW TO TANGEM** alert: If you choose to buy this manually, please ensure you move it to cold storage once it settles."
                        send_notification(msg, title="Long-Term Crypto Recommendation")
            except Exception as e:
                log.error(f"Error processing crypto candidate {symbol}: {e}")

    def _should_invest_long_term(self, symbol: str) -> bool:
        """
        Uses AI to evaluate if a crypto asset is a good long-term investment.
        """
        # Fetch some daily bars for context
        try:
            # We'll use 30 days of daily data for long-term context
            # MarketDataClient.get_bars_for_research handles daily data
            bars = self.market_data.get_bars_for_research(symbol, days=30)
            if not bars:
                return False
                
            # Basic Trend Check: Is it above the 30-day average?
            closes = [float(b.close) for b in bars]
            avg_price = sum(closes) / len(closes)
            current_price = closes[-1]
            
            # Context for AI
            context = f"Asset: {symbol}\nCurrent Price: {current_price}\n30-Day Avg: {avg_price}\nRecent Volatility: {max(closes)-min(closes)}"
            
            # Ask AI for long-term sentiment
            prompt = f"""
            Analyze {symbol} for a long-term (HODL) investment strategy.
            Current data: {context}
            
            Based on your knowledge of crypto market cycles and this recent price action, 
            is this a good entry point for a long-term position? 
            Respond with a JSON object: {{"decision": "BUY" or "HOLD", "reasoning": "..."}}
            """
            
            # Using summarize_research as a proxy for general AI reasoning
            response_text = self.ai.summarize_research(prompt)
            
            # Minimal parsing
            if '"decision": "BUY"' in response_text or '"decision":"BUY"' in response_text:
                return True
                
        except Exception as e:
            log.error(f"AI analysis failed for {symbol}: {e}")
            
        return False

    def _execute_crypto_buy(self, symbol: str, amount_dollars: float):
        """
        Executes a crypto buy order on Alpaca.
        """
        try:
            price = self.market_data.get_latest_mid_price(symbol)
            if not price:
                log.error(f"Could not get price for {symbol}")
                return

            qty = amount_dollars / price
            
            # Alpaca crypto orders often require 10 digits or specific precision
            # For simplicity, we use the buy method which handles Alpaca's OrderRequest
            log.info(f"Submitting crypto buy order for {symbol}: {qty:.6f} units")
            self.broker.buy(symbol=symbol, qty=qty)
            
            # Notify user
            msg = f"🚀 Bot purchased ${amount_dollars:.2f} of {symbol} for long-term investment.\n"
            msg += f"⚠️ **WITHDRAW TO TANGEM** alert: Once these funds have settled (usually T+2), please manually move them to your cold storage."
                
            send_notification(msg, title="Withdraw to Tangem Alert")
            
        except Exception as e:
            log.error(f"Failed to execute crypto buy for {symbol}: {e}")

def run_crypto_investor():
    investor = CryptoInvestor()
    investor.scan_and_invest()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_crypto_investor()
