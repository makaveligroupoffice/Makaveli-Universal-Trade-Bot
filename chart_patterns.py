import pandas as pd
import numpy as np

class ChartPatterns:
    @staticmethod
    def get_biases():
        """Returns a dict of pattern name -> bias ('bullish' or 'bearish')"""
        return {
            'CH_DOUBLE_BOTTOM': 'bullish',
            'CH_DOUBLE_TOP': 'bearish',
            'CH_TRIPLE_BOTTOM': 'bullish',
            'CH_TRIPLE_TOP': 'bearish',
            'CH_HEAD_AND_SHOULDERS': 'bearish',
            'CH_INVERTED_HEAD_AND_SHOULDERS': 'bullish',
            'CH_BULLISH_FLAG': 'bullish',
            'CH_BEARISH_FLAG': 'bearish',
            'CH_BULLISH_PENNANT': 'bullish',
            'CH_BEARISH_PENNANT': 'bearish',
            'CH_ASCENDING_TRIANGLE': 'bullish',
            'CH_DESCENDING_TRIANGLE': 'bearish',
            'CH_SYMMETRICAL_TRIANGLE': 'neutral',
            'CH_FALLING_WEDGE': 'bullish',
            'CH_RISING_WEDGE': 'bearish',
            'CH_CUP_AND_HANDLE': 'bullish',
            'CH_INVERTED_CUP_AND_HANDLE': 'bearish',
            'CH_RECTANGLE_BULLISH': 'bullish',
            'CH_RECTANGLE_BEARISH': 'bearish',
            'CH_ELLIOT_WAVE': 'bullish'
        }

    @staticmethod
    def detect_all(df):
        """
        Detects chart patterns using pivot points and geometric heuristics.
        Returns the DataFrame with additional boolean columns.
        """
        # 1. Find Pivot Points (Fractals)
        # We'll use a window of 5 candles to identify local peaks and troughs
        df['is_peak'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(2)) & \
                        (df['high'] > df['high'].shift(-1)) & (df['high'] > df['high'].shift(-2))
        df['is_trough'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(2)) & \
                          (df['low'] < df['low'].shift(-1)) & (df['low'] < df['low'].shift(-2))

        # Initializing columns
        for pattern in ChartPatterns.get_biases().keys():
            df[pattern] = False

        # 2. Iterate and Detect (Optimized for the last few candles)
        # Pattern detection usually requires looking back at the last N pivots
        # For real-time trading, we mostly care if a pattern just completed.
        
        # Helper: Get last N pivots
        def get_last_pivots(index, count=5):
            peaks = df.iloc[:index+1][df.iloc[:index+1]['is_peak']]
            troughs = df.iloc[:index+1][df.iloc[:index+1]['is_trough']]
            return peaks.tail(count), troughs.tail(count)

        # To keep it efficient, we only check the last 20 candles for pattern completion
        lookback = min(20, len(df))
        for i in range(len(df) - lookback, len(df)):
            peaks, troughs = get_last_pivots(i, 5)
            if len(peaks) < 2 or len(troughs) < 2:
                continue
            
            p = peaks['high'].tolist()
            t = troughs['low'].tolist()
            
            # --- Double Top / Bottom ---
            # Double Top: Two peaks at approx same level
            if len(p) >= 2:
                if abs(p[-1] - p[-2]) / p[-1] < 0.005: # 0.5% tolerance
                    # Neckline is the trough between them
                    between_peaks = df.iloc[int(peaks.index[-2]):int(peaks.index[-1])]
                    if not between_peaks.empty:
                        neckline = between_peaks['low'].min()
                        if df['close'].iloc[i] < neckline: # Breakdown
                            df.at[df.index[i], 'CH_DOUBLE_TOP'] = True

            # Double Bottom
            if len(t) >= 2:
                if abs(t[-1] - t[-2]) / t[-1] < 0.005:
                    between_troughs = df.iloc[int(troughs.index[-2]):int(troughs.index[-1])]
                    if not between_troughs.empty:
                        neckline = between_troughs['high'].max()
                        if df['close'].iloc[i] > neckline: # Breakout
                            df.at[df.index[i], 'CH_DOUBLE_BOTTOM'] = True

            # --- Triple Top / Bottom ---
            if len(p) >= 3:
                if abs(p[-1] - p[-2]) / p[-1] < 0.005 and abs(p[-2] - p[-3]) / p[-2] < 0.005:
                    df.at[df.index[i], 'CH_TRIPLE_TOP'] = True
            if len(t) >= 3:
                if abs(t[-1] - t[-2]) / t[-1] < 0.005 and abs(t[-2] - t[-3]) / t[-2] < 0.005:
                    df.at[df.index[i], 'CH_TRIPLE_BOTTOM'] = True

            # --- Head and Shoulders ---
            if len(p) >= 3:
                # Shoulder 1, Head, Shoulder 2
                if p[-2] > p[-1] and p[-2] > p[-3] and abs(p[-1] - p[-3]) / p[-1] < 0.02:
                    df.at[df.index[i], 'CH_HEAD_AND_SHOULDERS'] = True
            
            # Inverted Head and Shoulders
            if len(t) >= 3:
                if t[-2] < t[-1] and t[-2] < t[-3] and abs(t[-1] - t[-3]) / t[-1] < 0.02:
                    df.at[df.index[i], 'CH_INVERTED_HEAD_AND_SHOULDERS'] = True

            # --- Triangles / Wedges ---
            if len(p) >= 2 and len(t) >= 2:
                # Falling Wedge (Lower highs and lower lows, converging)
                if p[-1] < p[-2] and t[-1] < t[-2] and (p[-2]-p[-1]) > (t[-2]-t[-1]):
                    df.at[df.index[i], 'CH_FALLING_WEDGE'] = True
                # Rising Wedge
                if p[-1] > p[-2] and t[-1] > t[-2] and (t[-1]-t[-2]) > (p[-1]-p[-2]):
                    df.at[df.index[i], 'CH_RISING_WEDGE'] = True
                
                # Ascending Triangle (Flat top, rising lows)
                if abs(p[-1] - p[-2]) / p[-1] < 0.005 and t[-1] > t[-2]:
                    df.at[df.index[i], 'CH_ASCENDING_TRIANGLE'] = True
                # Descending Triangle (Flat bottom, falling highs)
                if abs(t[-1] - t[-2]) / t[-1] < 0.005 and p[-1] < p[-2]:
                    df.at[df.index[i], 'CH_DESCENDING_TRIANGLE'] = True
                
                # Symmetrical Triangle
                if p[-1] < p[-2] and t[-1] > t[-2]:
                    df.at[df.index[i], 'CH_SYMMETRICAL_TRIANGLE'] = True

        # --- Flags and Pennants ---
        # Flags are characterized by a sharp move (pole) followed by a small consolidation channel
        df['move'] = df['close'] - df['close'].shift(5)
        df['is_pole_bull'] = df['move'] > (df['close'] * 0.02) # 2% move in 5 candles
        df['is_pole_bear'] = df['move'] < -(df['close'] * 0.02)
        
        for i in range(5, len(df)):
            if df['is_pole_bull'].iloc[i-3]: # Pole happened recently
                # Check for consolidation (lower highs, lower lows but tight)
                if df['high'].iloc[i] <= df['high'].iloc[i-1] and df['low'].iloc[i] <= df['low'].iloc[i-1]:
                    df.at[df.index[i], 'CH_BULLISH_FLAG'] = True
            if df['is_pole_bear'].iloc[i-3]:
                if df['high'].iloc[i] >= df['high'].iloc[i-1] and df['low'].iloc[i] >= df['low'].iloc[i-1]:
                    df.at[df.index[i], 'CH_BEARISH_FLAG'] = True
            
            # Pennants (Converging after a pole)
            if df['is_pole_bull'].iloc[i-3]:
                 if df['high'].iloc[i] < df['high'].iloc[i-1] and df['low'].iloc[i] > df['low'].iloc[i-1]:
                     df.at[df.index[i], 'CH_BULLISH_PENNANT'] = True
            if df['is_pole_bear'].iloc[i-3]:
                 if df['high'].iloc[i] < df['high'].iloc[i-1] and df['low'].iloc[i] > df['low'].iloc[i-1]:
                     df.at[df.index[i], 'CH_BEARISH_PENNANT'] = True

        # --- Rectangles ---
        # Sideways consolidation between two parallel levels
        df['high_20'] = df['high'].rolling(20).max()
        df['low_20'] = df['low'].rolling(20).min()
        df['is_rectangle'] = (df['high_20'] == df['high_20'].shift(1)) & (df['low_20'] == df['low_20'].shift(1))
        df['CH_RECTANGLE_BULLISH'] = df['is_rectangle'] & (df['close'] > df['high_20'].shift(1))
        df['CH_RECTANGLE_BEARISH'] = df['is_rectangle'] & (df['close'] < df['low_20'].shift(1))

        # --- Cup and Handle / Inverted ---
        # Simplified: Price makes a U-shape (drop then recovery) then a small dip
        # We'll use a very basic heuristic: current price near 20-period high after a recent dip
        df['recent_dip'] = df['low'].rolling(10).min() < df['low'].rolling(20).min().shift(10)
        df['CH_CUP_AND_HANDLE'] = df['recent_dip'] & (df['close'] > df['high'].rolling(20).max().shift(1) * 0.99)
        
        # Inverted Cup and Handle
        df['recent_peak'] = df['high'].rolling(10).max() > df['high'].rolling(20).max().shift(10)
        df['CH_INVERTED_CUP_AND_HANDLE'] = df['recent_peak'] & (df['close'] < df['low'].rolling(20).min().shift(1) * 1.01)

        # --- Elliot Wave (Placeholder) ---
        # Elliot wave detection is highly subjective. We'll mark potential 'Wave 3' (strong momentum after a correction)
        # Ensure required columns exist
        if 'sma50' not in df.columns:
            df['sma50'] = df['close'].rolling(window=min(50, len(df))).mean()
        if 'momentum' not in df.columns:
            df['momentum'] = df['close'] - df['close'].shift(10)
        if 'rvol' not in df.columns:
            df['rvol'] = 1.0 # Default if missing
            
        df['CH_ELLIOT_WAVE'] = (df['close'] > df['sma50']) & (df['momentum'] > df['momentum'].shift(1)) & (df['rvol'] > 1.5)

        return df
