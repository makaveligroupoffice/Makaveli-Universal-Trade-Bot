import logging
import os
import json
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
        if not self.client:
            log.warning("AI client not available. Skipping AI code evolution.")
            return current_code

        prompt = f"""
You are an expert algorithmic trading developer. 
Your task is to analyze the performance of a trading bot and improve its strategy code in 'strategy.py'.

Current Performance Report:
{performance_report}

Current 'strategy.py' code:
```python
{current_code}
```

Instructions:
1. Identify logic weaknesses contributing to the performance issues.
2. Modify technical indicator thresholds, confirmation rules, or exit logic to improve the Win Rate and Profit Factor.
3. Preserve all class and method signatures.
4. Respond ONLY with the complete, updated Python code for the 'Strategy' class. 
5. Do not include any explanations or markdown formatting outside the code block.
6. Ensure the code is syntactically correct and includes all necessary imports from the original file.
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
            log.error(f"AI code evolution failed: {e}")
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

        prompt = f"""
Should we enter a trade for {symbol} based on the {strategy_name} strategy?

Current Technical Indicators:
{json.dumps(indicators, indent=2)}

Answer with "YES" or "NO" and a brief reason. Format: "DECISION: [YES/NO] | REASON: [Your reason]"
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a conservative risk manager. Your goal is to avoid low-probability setups."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.0
            )
            decision_text = response.choices[0].message.content.strip().upper()
            log.info(f"AI Decision for {symbol}: {decision_text}")
            return "DECISION: YES" in decision_text
        except Exception as e:
            log.error(f"AI signal verification failed for {symbol}: {e}")
            return True # Fallback to true to avoid missing trades on AI error
