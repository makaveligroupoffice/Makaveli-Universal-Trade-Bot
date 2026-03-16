import logging
import os
import json
from datetime import datetime
from config import Config

log = logging.getLogger("autobot")

class AIEngine:
    """
    Unified interface for AI-powered features using LLMs (e.g., OpenAI).
    """
    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.api_key = Config.OPENAI_API_KEY
        self.model = Config.OPENAI_MODEL
        
        self.client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                log.error("OpenAI library not installed. Run 'pip install openai'")
            except Exception as e:
                log.error(f"Failed to initialize OpenAI client: {e}")

    def generate_code_evolution(self, current_code: str, performance_report: str) -> str:
        """
        Uses AI to rewrite strategy code based on performance analysis.
        """
        return self._ai_code_generation(current_code, f"Performance Report:\n{performance_report}")

    def summarize_research(self, prompt: str) -> str:
        """
        Uses AI to research and summarize information.
        """
        if not self.client:
            return ""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional research analyst specializing in financial markets."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"AI research summary failed: {e}")
            raise e

    def evolve_code_from_research(self, current_code: str, research_summary: str) -> str:
        """
        Uses AI to rewrite strategy code based on internet research findings.
        """
        return self._ai_code_generation(current_code, f"Internet Research Summary:\n{research_summary}")

    def _ai_code_generation(self, current_code: str, context: str) -> str:
        """
        Generic helper for AI code generation.
        """
        if not self.client:
            log.warning("AI client not available. Skipping AI code evolution.")
            return current_code

        # Add global market context if possible
        market_context = ""
        try:
            from market_data import MarketDataClient
            md = MarketDataClient()
            spy_bars = md.get_recent_bars("SPY", minutes=60)
            if spy_bars:
                spy_change = (float(spy_bars[-1].close) - float(spy_bars[0].close)) / float(spy_bars[0].close)
                market_context = f"\nGlobal Market Context: SPY 1-hour change is {spy_change:.2%}.\n"
        except:
            pass

        prompt = f"""
You are an expert algorithmic trading developer. 
Your primary goal is to optimize a trading strategy to achieve a 75% or higher win rate and 10x account growth.
Your task is to analyze external research or performance data and improve a trading strategy code in 'strategy.py'.
{market_context}
{context}

Current 'strategy.py' code:
```python
{current_code}
```

Instructions:
1. Identify logic weaknesses or opportunities for improvement.
2. Modify technical indicator thresholds, confirmation rules, or exit logic.
3. Focus on 'Sniper' (High-Probability) entries and 'Steady Cash Flow' scalps.
4. Prioritize risk-adjusted returns to hit the 10x growth goal.
5. Preserve all class and method signatures.
6. Respond ONLY with the complete, updated Python code for the 'Strategy' class. 
7. Do not include any explanations or markdown formatting outside the code block.
8. Ensure the code is syntactically correct and includes all necessary imports from the original file.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional quantitative developer specializing in strategy optimization."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            
            ai_code = response.choices[0].message.content.strip()
            # Clean up potential markdown formatting
            if "```python" in ai_code:
                ai_code = ai_code.split("```python")[1].split("```")[0].strip()
            elif "```" in ai_code:
                ai_code = ai_code.split("```")[1].split("```")[0].strip()
                
            return ai_code
        except Exception as e:
            log.error(f"AI code generation failed: {e}")
            return current_code

    def analyze_trade_sentiment(self, symbol: str, news_headlines: list) -> float:
        """
        Analyzes recent news sentiment for a symbol.
        Returns a score between -1.0 (very bearish) and 1.0 (very bullish).
        """
        if not self.client or not news_headlines:
            return 0.0

        headlines_text = "\n".join([f"- {h}" for h in news_headlines[:10]])
        prompt = f"Analyze the sentiment of the following news headlines for {symbol}:\n\n{headlines_text}\n\nReturn ONLY a single numeric score between -1.0 and 1.0, where -1.0 is critically negative and 1.0 is extremely positive."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial analyst specializing in news sentiment."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0.0
            )
            score_str = response.choices[0].message.content.strip()
            return float(score_str)
        except Exception as e:
            log.error(f"AI sentiment analysis failed for {symbol}: {e}")
            return 0.0

    def verify_trade_signal(self, symbol: str, strategy_name: str, indicators: dict) -> bool:
        """
        Uses AI to provide a second opinion on a technical trade signal.
        """
        if not self.client or not Config.ENABLE_AI_TRADE_FILTER:
            return True # Pass through if AI filter is disabled

        # Add market context for better decision making
        market_context = {}
        try:
            from market_data import MarketDataClient
            md = MarketDataClient()
            # Try to get VIX for volatility context
            vix_quote = md.get_latest_quote("VIX")
            if vix_quote:
                market_context["VIX"] = float(vix_quote.ask_price or 0)
            
            # SPY Trend
            spy_bars = md.get_recent_bars("SPY", minutes=30)
            if spy_bars:
                market_context["SPY_30m_trend"] = "UP" if float(spy_bars[-1].close) > float(spy_bars[0].close) else "DOWN"
        except:
            pass

        prompt = f"""
Should we enter a trade for {symbol} based on the {strategy_name} strategy?

Market Context:
{json.dumps(market_context, indent=2)}

Current Technical Indicators for {symbol}:
{json.dumps(indicators, indent=2)}

Answer with "YES" or "NO" and provide a detailed reason. 
Format: 
DECISION: [YES/NO]
REASONING: [Your detailed multi-step logical reasoning]
ADVICE: [Specific advice for this trade, e.g., 'Use tighter stop' or 'Wait for more volume']
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a conservative risk manager. Your goal is to avoid low-probability setups and ensure alignment with broader market trends."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250,
                temperature=0.0
            )
            decision_text = response.choices[0].message.content.strip()
            log.info(f"AI Review for {symbol}:\n{decision_text}")
            
            # Log the full reasoning to a dedicated file for the user
            self._log_ai_reasoning(symbol, decision_text)
            
            # Check for high confidence if possible, or just strict YES
            is_yes = "DECISION: YES" in decision_text.upper()
            
            # Expert Mode: If we are 'going backwards', be extra conservative
            # We can look for keywords like 'high confidence' or 'strong buy' if we want,
            # but for now, just making sure YES is explicit.
            return is_yes
        except Exception as e:
            log.error(f"AI signal verification failed for {symbol}: {e}")
            return False # Conservative fallback: don't trade if AI is down

    def _log_ai_reasoning(self, symbol: str, text: str):
        """Logs AI reasoning to a separate file for user transparency."""
        log_file = os.path.join(Config.LOG_DIR, "ai_reasoning.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} | {symbol} ---\n{text}\n\n")
