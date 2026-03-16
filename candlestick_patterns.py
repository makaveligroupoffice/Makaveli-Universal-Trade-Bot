import pandas as pd
import numpy as np

class CandlestickPatterns:
    @staticmethod
    def get_biases():
        """Returns a dict of pattern name -> bias ('bullish' or 'bearish')"""
        return {
            'CP_ABANDONED_BABY_BULLISH': 'bullish',
            'CP_ABANDONED_BABY_BEARISH': 'bearish',
            'CP_ADVANCE_BLOCK': 'bearish',
            'CP_BELT_HOLD_BULLISH': 'bullish',
            'CP_BELT_HOLD_BEARISH': 'bearish',
            'CP_BREAKAWAY_BULLISH': 'bullish',
            'CP_BREAKAWAY_BEARISH': 'bearish',
            'CP_CLOSING_MARUBOZU_BULLISH': 'bullish',
            'CP_CLOSING_MARUBOZU_BEARISH': 'bearish',
            'CP_CONCEALING_BABY_SWALLOW': 'bullish',
            'CP_COUNTERATTACK_BULLISH': 'bullish',
            'CP_COUNTERATTACK_BEARISH': 'bearish',
            'CP_DARK_CLOUD_COVER': 'bearish',
            'CP_DOJI_STAR_BULLISH': 'bullish',
            'CP_DOJI_STAR_BEARISH': 'bearish',
            'CP_DRAGONFLY_DOJI': 'bullish',
            'CP_ENGULFING_BULLISH': 'bullish',
            'CP_ENGULFING_BEARISH': 'bearish',
            'CP_EVENING_DOJI_STAR': 'bearish',
            'CP_EVENING_STAR': 'bearish',
            'CP_FALLING_THREE_METHODS': 'bearish',
            'CP_FALLING_WINDOW': 'bearish',
            'CP_GAPPING_SIDE_BY_SIDE_WHITE_LINES_BULLISH': 'bullish',
            'CP_GAPPING_SIDE_BY_SIDE_WHITE_LINES_BEARISH': 'bearish',
            'CP_GRAVESTONE_DOJI': 'bearish',
            'CP_HAMMER': 'bullish',
            'CP_HANGING_MAN': 'bearish',
            'CP_HARAMI_BULLISH': 'bullish',
            'CP_HARAMI_BEARISH': 'bearish',
            'CP_HARAMI_CROSS_BULLISH': 'bullish',
            'CP_HARAMI_CROSS_BEARISH': 'bearish',
            'CP_HOMING_PIGEON': 'bullish',
            'CP_IDENTIFYING_ONE_BLACK_CROW': 'bearish',
            'CP_INVERTED_HAMMER': 'bullish',
            'CP_KICKING_BULLISH': 'bullish',
            'CP_KICKING_BEARISH': 'bearish',
            'CP_LADDER_BOTTOM': 'bullish',
            'CP_LONG_LEGGED_DOJI': 'neutral',
            'CP_MARUBOZU_BULLISH': 'bullish',
            'CP_MARUBOZU_BEARISH': 'bearish',
            'CP_MATCHING_LOW': 'bullish',
            'CP_MAT_HOLD_BULLISH': 'bullish',
            'CP_MORNING_DOJI_STAR': 'bullish',
            'CP_MORNING_STAR': 'bullish',
            'CP_ON_NECK': 'bearish',
            'CP_PIERCING_LINE': 'bullish',
            'CP_RISING_THREE_METHODS': 'bullish',
            'CP_RISING_WINDOW': 'bullish',
            'CP_SEPARATING_LINES_BULLISH': 'bullish',
            'CP_SEPARATING_LINES_BEARISH': 'bearish',
            'CP_SHOOTING_STAR': 'bearish',
            'CP_SHORT_LINE_BULLISH': 'bullish',
            'CP_SHORT_LINE_BEARISH': 'bearish',
            'CP_SPINNING_TOP_BULLISH': 'bullish',
            'CP_SPINNING_TOP_BEARISH': 'bearish',
            'CP_STICK_SANDWICH': 'bullish',
            'CP_TAKURI_LINE': 'bullish',
            'CP_TASUKI_GAP_BULLISH': 'bullish',
            'CP_TASUKI_GAP_BEARISH': 'bearish',
            'CP_THREE_BLACK_CROWS': 'bearish',
            'CP_THREE_LINE_STRIKE_BULLISH': 'bullish',
            'CP_THREE_LINE_STRIKE_BEARISH': 'bearish',
            'CP_THREE_WHITE_SOLDIERS': 'bullish',
            'CP_TRI_STAR_BULLISH': 'bullish',
            'CP_TRI_STAR_BEARISH': 'bearish',
            'CP_TWEEZER_BOTTOM': 'bullish',
            'CP_TWEEZER_TOP': 'bearish',
            'CP_LONG_LOWER_SHADOW': 'bullish',
            'CP_LONG_UPPER_SHADOW': 'bearish'
        }

    @staticmethod
    def detect_all(df):
        """
        Detects 64+ TradingView candlestick patterns.
        Returns the DataFrame with additional boolean columns for each pattern.
        """
        # --- Pre-calculate basic candle properties ---
        df['body'] = (df['close'] - df['open']).abs()
        df['range'] = df['high'] - df['low']
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        df['is_bullish'] = df['close'] > df['open']
        df['is_bearish'] = df['close'] < df['open']
        
        # Averages for relative sizing
        df['body_avg'] = df['body'].rolling(window=10).mean()
        df['range_avg'] = df['range'].rolling(window=10).mean()
        
        # Helpers for pattern logic
        df['is_doji'] = df['body'] < (0.1 * df['range'])
        df['is_long_body'] = df['body'] > (1.5 * df['body_avg'])
        df['is_short_body'] = df['body'] < (0.5 * df['body_avg'])
        df['is_marubozu'] = (df['body'] > (0.9 * df['range'])) & (df['body'] > (1.2 * df['body_avg']))
        
        # --- Patterns ---
        # 1. Abandoned Baby Bullish
        df['CP_ABANDONED_BABY_BULLISH'] = (df['is_bearish'].shift(2) & df['is_doji'].shift(1) & df['is_bullish'] & 
                                         (df['high'].shift(1) < df['low'].shift(2)) & (df['high'].shift(1) < df['low']))
        # 2. Abandoned Baby Bearish
        df['CP_ABANDONED_BABY_BEARISH'] = (df['is_bullish'].shift(2) & df['is_doji'].shift(1) & df['is_bearish'] & 
                                         (df['low'].shift(1) > df['high'].shift(2)) & (df['low'].shift(1) > df['high']))
        # 3. Advance Block
        df['CP_ADVANCE_BLOCK'] = (df['is_bullish'].shift(2) & df['is_bullish'].shift(1) & df['is_bullish'] & 
                                 (df['close'] > df['close'].shift(1)) & (df['close'].shift(1) > df['close'].shift(2)) & 
                                 (df['upper_shadow'] > df['body']) & (df['upper_shadow'].shift(1) > df['body'].shift(1)))
        # 4. Belt Hold Bullish
        df['CP_BELT_HOLD_BULLISH'] = (df['is_bullish'] & (df['open'] == df['low']) & (df['body'] > (1.2 * df['body_avg'])))
        # 5. Belt Hold Bearish
        df['CP_BELT_HOLD_BEARISH'] = (df['is_bearish'] & (df['open'] == df['high']) & (df['body'] > (1.2 * df['body_avg'])))
        # 6. Breakaway Bullish
        df['CP_BREAKAWAY_BULLISH'] = (df['is_bearish'].shift(4) & df['is_bearish'].shift(3) & df['is_bearish'].shift(2) & 
                                    df['is_bearish'].shift(1) & df['is_bullish'] & (df['open'].shift(3) < df['close'].shift(4)))
        # 7. Breakaway Bearish
        df['CP_BREAKAWAY_BEARISH'] = (df['is_bullish'].shift(4) & df['is_bullish'].shift(3) & df['is_bullish'].shift(2) & 
                                    df['is_bullish'].shift(1) & df['is_bearish'] & (df['open'].shift(3) > df['high'].shift(4)))
        # 8. Closing Marubozu Bullish
        df['CP_CLOSING_MARUBOZU_BULLISH'] = (df['is_bullish'] & (df['close'] == df['high']) & (df['body'] > (1.1 * df['body_avg'])))
        # 9. Closing Marubozu Bearish
        df['CP_CLOSING_MARUBOZU_BEARISH'] = (df['is_bearish'] & (df['close'] == df['low']) & (df['body'] > (1.1 * df['body_avg'])))
        # 10. Concealing Baby Swallow
        df['CP_CONCEALING_BABY_SWALLOW'] = (df['is_marubozu'].shift(3) & df['is_marubozu'].shift(2) & 
                                           (df['high'].shift(1) > df['close'].shift(2)) & (df['low'] < df['low'].shift(1)))
        # 11. Counterattack Bullish
        df['CP_COUNTERATTACK_BULLISH'] = (df['is_bearish'].shift(1) & df['is_bullish'] & (df['close'] == df['close'].shift(1)))
        # 12. Counterattack Bearish
        df['CP_COUNTERATTACK_BEARISH'] = (df['is_bullish'].shift(1) & df['is_bearish'] & (df['close'] == df['close'].shift(1)))
        # 13. Dark Cloud Cover
        df['CP_DARK_CLOUD_COVER'] = (df['is_bullish'].shift(1) & df['is_bearish'] & (df['open'] > df['high'].shift(1)) & 
                                    (df['close'] < (df['open'].shift(1) + df['close'].shift(1))/2) & (df['close'] > df['open'].shift(1)))
        # 14. Doji
        df['CP_DOJI'] = df['is_doji']
        # 15. Doji Star Bullish
        df['CP_DOJI_STAR_BULLISH'] = (df['is_bearish'].shift(1) & df['is_doji'] & (df['high'] < df['low'].shift(1)))
        # 16. Doji Star Bearish
        df['CP_DOJI_STAR_BEARISH'] = (df['is_bullish'].shift(1) & df['is_doji'] & (df['low'] > df['high'].shift(1)))
        # 17. Dragonfly Doji
        df['CP_DRAGONFLY_DOJI'] = (df['is_doji'] & (df['upper_shadow'] < (0.1 * df['body'])) & (df['lower_shadow'] > (3 * df['body'])))
        # 18. Engulfing Bullish
        df['CP_ENGULFING_BULLISH'] = (df['is_bearish'].shift(1) & df['is_bullish'] & (df['open'] < df['close'].shift(1)) & (df['close'] > df['open'].shift(1)))
        # 19. Engulfing Bearish
        df['CP_ENGULFING_BEARISH'] = (df['is_bullish'].shift(1) & df['is_bearish'] & (df['open'] > df['close'].shift(1)) & (df['close'] < df['open'].shift(1)))
        # 20. Evening Doji Star
        df['CP_EVENING_DOJI_STAR'] = (df['is_bullish'].shift(2) & df['is_doji'].shift(1) & df['is_bearish'] & (df['open'].shift(1) > df['close'].shift(2)))
        # 21. Evening Star
        df['CP_EVENING_STAR'] = (df['is_bullish'].shift(2) & df['is_short_body'].shift(1) & df['is_bearish'] & (df['open'].shift(1) > df['close'].shift(2)))
        # 22. Falling Three Methods
        df['CP_FALLING_THREE_METHODS'] = (df['is_bearish'].shift(4) & df['is_bullish'].shift(3) & df['is_bullish'].shift(2) & 
                                         df['is_bullish'].shift(1) & df['is_bearish'] & (df['close'] < df['close'].shift(4)))
        # 23. Falling Window
        df['CP_FALLING_WINDOW'] = (df['high'] < df['low'].shift(1))
        # 24. Gapping Side-by-Side White Lines Bullish
        df['CP_GAPPING_SIDE_BY_SIDE_WHITE_LINES_BULLISH'] = (df['is_bullish'].shift(1) & df['is_bullish'] & (df['open'] == df['open'].shift(1)) & (df['open'] > df['high'].shift(2)))
        # 25. Gapping Side-by-Side White Lines Bearish
        df['CP_GAPPING_SIDE_BY_SIDE_WHITE_LINES_BEARISH'] = (df['is_bullish'].shift(1) & df['is_bullish'] & (df['open'] == df['open'].shift(1)) & (df['close'] < df['low'].shift(2)))
        # 26. Gravestone Doji
        df['CP_GRAVESTONE_DOJI'] = (df['is_doji'] & (df['lower_shadow'] < (0.1 * df['body'])) & (df['upper_shadow'] > (3 * df['body'])))
        # 27. Hammer
        df['CP_HAMMER'] = (df['lower_shadow'] > (2 * df['body'])) & (df['upper_shadow'] < (0.1 * df['body']))
        # 28. Hanging Man
        df['CP_HANGING_MAN'] = (df['lower_shadow'] > (2 * df['body'])) & (df['upper_shadow'] < (0.1 * df['body'])) & (df['close'].shift(1) < df['open'])
        # 29. Harami Bullish
        df['CP_HARAMI_BULLISH'] = (df['is_bearish'].shift(1) & df['is_bullish'] & (df['open'] > df['close'].shift(1)) & (df['close'] < df['open'].shift(1)))
        # 30. Harami Bearish
        df['CP_HARAMI_BEARISH'] = (df['is_bullish'].shift(1) & df['is_bearish'] & (df['open'] < df['close'].shift(1)) & (df['close'] > df['open'].shift(1)))
        # 31. Harami Cross Bullish
        df['CP_HARAMI_CROSS_BULLISH'] = (df['is_bearish'].shift(1) & df['is_doji'] & (df['high'] < df['open'].shift(1)) & (df['low'] > df['close'].shift(1)))
        # 32. Harami Cross Bearish
        df['CP_HARAMI_CROSS_BEARISH'] = (df['is_bullish'].shift(1) & df['is_doji'] & (df['low'] > df['open'].shift(1)) & (df['high'] < df['close'].shift(1)))
        # 33. Homing Pigeon
        df['CP_HOMING_PIGEON'] = (df['is_bearish'].shift(1) & df['is_bearish'] & (df['open'] < df['open'].shift(1)) & (df['close'] > df['close'].shift(1)))
        # 34. Identifying One Black Crow
        df['CP_IDENTIFYING_ONE_BLACK_CROW'] = (df['is_bullish'].shift(1) & df['is_bearish'] & (df['open'] < df['close'].shift(1)) & (df['close'] < df['open'].shift(1)))
        # 35. Inverted Hammer
        df['CP_INVERTED_HAMMER'] = (df['upper_shadow'] > (2 * df['body'])) & (df['lower_shadow'] < (0.1 * df['body']))
        # 36. Kicking Bullish
        df['CP_KICKING_BULLISH'] = (df['is_marubozu'].shift(1) & df['is_bearish'].shift(1) & df['is_marubozu'] & df['is_bullish'] & (df['open'] > df['open'].shift(1)))
        # 37. Kicking Bearish
        df['CP_KICKING_BEARISH'] = (df['is_marubozu'].shift(1) & df['is_bullish'].shift(1) & df['is_marubozu'] & df['is_bearish'] & (df['open'] < df['open'].shift(1)))
        # 38. Ladder Bottom
        df['CP_LADDER_BOTTOM'] = (df['is_bearish'].shift(4) & df['is_bearish'].shift(3) & df['is_bearish'].shift(2) & 
                                 (df['open'].shift(1) > df['open'].shift(2)) & df['is_bullish'] & (df['open'] > df['high'].shift(1)))
        # 39. Long Legged Doji
        df['CP_LONG_LEGGED_DOJI'] = (df['is_doji'] & (df['upper_shadow'] > df['body_avg']) & (df['lower_shadow'] > df['body_avg']))
        # 40. Marubozu Bullish
        df['CP_MARUBOZU_BULLISH'] = (df['is_marubozu'] & df['is_bullish'])
        # 41. Marubozu Bearish
        df['CP_MARUBOZU_BEARISH'] = (df['is_marubozu'] & df['is_bearish'])
        # 42. Matching Low
        df['CP_MATCHING_LOW'] = (df['is_bearish'].shift(1) & df['is_bearish'] & (df['close'] == df['close'].shift(1)))
        # 43. Mat Hold Bullish
        df['CP_MAT_HOLD_BULLISH'] = (df['is_bullish'].shift(4) & df['is_bearish'].shift(3) & df['is_bearish'].shift(2) & 
                                    df['is_bearish'].shift(1) & df['is_bullish'] & (df['close'] > df['close'].shift(4)))
        # 44. Morning Doji Star
        df['CP_MORNING_DOJI_STAR'] = (df['is_bearish'].shift(2) & df['is_doji'].shift(1) & df['is_bullish'] & (df['open'].shift(1) < df['close'].shift(2)))
        # 45. Morning Star
        df['CP_MORNING_STAR'] = (df['is_bearish'].shift(2) & df['is_short_body'].shift(1) & df['is_bullish'] & (df['open'].shift(1) < df['close'].shift(2)))
        # 46. On Neck
        df['CP_ON_NECK'] = (df['is_bearish'].shift(1) & df['is_bullish'] & (df['open'] < df['low'].shift(1)) & (df['close'] == df['low'].shift(1)))
        # 47. Piercing Line
        df['CP_PIERCING_LINE'] = (df['is_bearish'].shift(1) & df['is_bullish'] & (df['open'] < df['low'].shift(1)) & 
                                 (df['close'] > (df['open'].shift(1) + df['close'].shift(1))/2) & (df['close'] < df['open'].shift(1)))
        # 48. Rising Three Methods
        df['CP_RISING_THREE_METHODS'] = (df['is_bullish'].shift(4) & df['is_bearish'].shift(3) & df['is_bearish'].shift(2) & 
                                        df['is_bearish'].shift(1) & df['is_bullish'] & (df['close'] > df['close'].shift(4)))
        # 49. Rising Window
        df['CP_RISING_WINDOW'] = (df['low'] > df['high'].shift(1))
        # 50. Separating Lines Bullish
        df['CP_SEPARATING_LINES_BULLISH'] = (df['is_bearish'].shift(1) & df['is_bullish'] & (df['open'] == df['open'].shift(1)))
        # 51. Separating Lines Bearish
        df['CP_SEPARATING_LINES_BEARISH'] = (df['is_bullish'].shift(1) & df['is_bearish'] & (df['open'] == df['open'].shift(1)))
        # 52. Shooting Star
        df['CP_SHOOTING_STAR'] = (df['upper_shadow'] > (2 * df['body'])) & (df['lower_shadow'] < (0.1 * df['body'])) & (df['close'].shift(1) < df['open'])
        # 53. Short Line Bullish
        df['CP_SHORT_LINE_BULLISH'] = (df['is_bullish'] & df['is_short_body'])
        # 54. Short Line Bearish
        df['CP_SHORT_LINE_BEARISH'] = (df['is_bearish'] & df['is_short_body'])
        # 55. Spinning Top Bullish
        df['CP_SPINNING_TOP_BULLISH'] = (df['is_bullish'] & df['is_short_body'] & (df['upper_shadow'] > df['body']) & (df['lower_shadow'] > df['body']))
        # 56. Spinning Top Bearish
        df['CP_SPINNING_TOP_BEARISH'] = (df['is_bearish'] & df['is_short_body'] & (df['upper_shadow'] > df['body']) & (df['lower_shadow'] > df['body']))
        # 57. Stick Sandwich
        df['CP_STICK_SANDWICH'] = (df['is_bearish'].shift(2) & df['is_bullish'].shift(1) & df['is_bearish'] & (df['close'] == df['close'].shift(2)))
        # 58. Takuri Line
        df['CP_TAKURI_LINE'] = (df['is_doji'] & (df['lower_shadow'] > (3 * df['range_avg'])))
        # 59. Tasuki Gap Bullish
        df['CP_TASUKI_GAP_BULLISH'] = (df['is_bullish'].shift(2) & df['is_bullish'].shift(1) & (df['open'].shift(1) > df['close'].shift(2)) & 
                                      df['is_bearish'] & (df['open'] < df['close'].shift(1)) & (df['close'] > df['open'].shift(1)))
        # 60. Tasuki Gap Bearish
        df['CP_TASUKI_GAP_BEARISH'] = (df['is_bearish'].shift(2) & df['is_bearish'].shift(1) & (df['open'].shift(1) < df['close'].shift(2)) & 
                                      df['is_bullish'] & (df['open'] > df['close'].shift(1)) & (df['close'] < df['open'].shift(1)))
        # 61. Three Black Crows
        df['CP_THREE_BLACK_CROWS'] = (df['is_bearish'].shift(2) & df['is_bearish'].shift(1) & df['is_bearish'] & 
                                     (df['close'] < df['close'].shift(1)) & (df['close'].shift(1) < df['close'].shift(2)))
        # 62. Three Line Strike Bullish
        df['CP_THREE_LINE_STRIKE_BULLISH'] = (df['is_bearish'].shift(3) & df['is_bearish'].shift(2) & df['is_bearish'].shift(1) & 
                                             df['is_bullish'] & (df['open'] < df['close'].shift(1)) & (df['close'] > df['open'].shift(3)))
        # 63. Three Line Strike Bearish
        df['CP_THREE_LINE_STRIKE_BEARISH'] = (df['is_bullish'].shift(3) & df['is_bullish'].shift(2) & df['is_bullish'].shift(1) & 
                                             df['is_bearish'] & (df['open'] > df['close'].shift(1)) & (df['close'] < df['open'].shift(3)))
        # 64. Three White Soldiers
        df['CP_THREE_WHITE_SOLDIERS'] = (df['is_bullish'].shift(2) & df['is_bullish'].shift(1) & df['is_bullish'] & 
                                        (df['close'] > df['close'].shift(1)) & (df['close'].shift(1) > df['close'].shift(2)))
        # 65. Tweezer Bottom
        df['CP_TWEEZER_BOTTOM'] = (df['low'] == df['low'].shift(1)) & (df['lower_shadow'] > df['body_avg'])
        # 66. Tweezer Top
        df['CP_TWEEZER_TOP'] = (df['high'] == df['high'].shift(1)) & (df['upper_shadow'] > df['body_avg'])

        # 67. Tri-Star Bullish
        df['CP_TRI_STAR_BULLISH'] = (df['is_doji'].shift(2) & df['is_doji'].shift(1) & df['is_doji'] & 
                                    (df['low'].shift(1) < df['low'].shift(2)) & (df['low'].shift(1) < df['low']))
        
        # 68. Tri-Star Bearish
        df['CP_TRI_STAR_BEARISH'] = (df['is_doji'].shift(2) & df['is_doji'].shift(1) & df['is_doji'] & 
                                    (df['high'].shift(1) > df['high'].shift(2)) & (df['high'].shift(1) > df['high']))

        # 69. Long Lower Shadow
        df['CP_LONG_LOWER_SHADOW'] = (df['lower_shadow'] > (2.5 * df['body'])) & (df['lower_shadow'] > df['body_avg'] * 2)

        # 70. Long Upper Shadow
        df['CP_LONG_UPPER_SHADOW'] = (df['upper_shadow'] > (2.5 * df['body'])) & (df['upper_shadow'] > df['body_avg'] * 2)

        return df
