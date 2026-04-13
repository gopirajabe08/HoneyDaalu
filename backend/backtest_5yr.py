"""5-year NSE market analysis — what conditions win, what lose."""
import yfinance as yf
import pandas as pd
import numpy as np

print("Fetching 5 years NSE data...")
nifty = yf.Ticker("^NSEI")
df = nifty.history(period="5y", interval="1d")
start = df.index[0].strftime("%Y-%m-%d")
end = df.index[-1].strftime("%Y-%m-%d")
print(f"Got {len(df)} trading days ({start} to {end})")

df["EMA20"] = df["Close"].ewm(span=20).mean()
df["SMA50"] = df["Close"].rolling(50).mean()
df["Daily_Return"] = df["Close"].pct_change()
df["Next_Return"] = df["Daily_Return"].shift(-1)
df["Range_Pct"] = (df["High"] - df["Low"]) / df["Open"] * 100

delta = df["Close"].diff()
gain = delta.where(delta > 0, 0).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + gain / loss))

df["BB_Mid"] = df["Close"].rolling(20).mean()
df["BB_Std"] = df["Close"].rolling(20).std()
df["BB_Width"] = (2 * df["BB_Std"]) / df["BB_Mid"] * 100

vix = yf.Ticker("^INDIAVIX")
vix_df = vix.history(period="5y", interval="1d")
if len(vix_df) > 0:
    df["VIX"] = vix_df["Close"].reindex(df.index, method="ffill")
else:
    df["VIX"] = 15

df["Vol_Ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

df = df.dropna(subset=["SMA50", "Next_Return"])

def classify(row):
    if row["Close"] > row["EMA20"] and row["Close"] > row["SMA50"]:
        trend = "bullish"
    elif row["Close"] < row["EMA20"] and row["Close"] < row["SMA50"]:
        trend = "bearish"
    elif row["Close"] > row["SMA50"]:
        trend = "pullback"
    else:
        trend = "sideways"
    v = row.get("VIX", 15)
    if v > 22: vol = "high_vol"
    elif v > 18: vol = "elevated"
    elif v < 14: vol = "low_vol"
    else: vol = "normal"
    return f"{trend}_{vol}"

df["Regime"] = df.apply(classify, axis=1)

print("\n=== REGIME DISTRIBUTION (5 Years) ===")
regime_counts = df["Regime"].value_counts()
for regime, count in regime_counts.items():
    pct = count / len(df) * 100
    avg = df[df["Regime"] == regime]["Daily_Return"].mean() * 100
    win = (df[df["Regime"] == regime]["Next_Return"] > 0).mean() * 100
    print(f"  {regime:30s} {count:4d} days ({pct:5.1f}%) | Next-day win: {win:.0f}% | Avg: {avg:+.3f}%")

print("\n=== WHAT WINS (Next-Day Returns by Signal) ===")

conditions = {
    "RSI < 30 (oversold BUY)":      df["RSI"] < 30,
    "RSI > 70 (overbought SELL)":    df["RSI"] > 70,
    "BB Squeeze breakout":           df["BB_Width"] < df["BB_Width"].rolling(50).mean() * 0.6,
    "Bullish trend (>EMA+SMA) BUY":  (df["Close"] > df["EMA20"]) & (df["Close"] > df["SMA50"]),
    "Bearish trend (<EMA+SMA) SELL": (df["Close"] < df["EMA20"]) & (df["Close"] < df["SMA50"]),
    "High VIX + big drop (reversal)": (df["VIX"] > 22) & (df["Daily_Return"] < -0.01),
    "Volume spike (>1.5x) + up":     (df["Vol_Ratio"] > 1.5) & (df["Daily_Return"] > 0),
    "Volume spike (>1.5x) + down":   (df["Vol_Ratio"] > 1.5) & (df["Daily_Return"] < 0),
    "Big range day (>2%)":           df["Range_Pct"] > 2,
}

results = []
for name, mask in conditions.items():
    subset = df[mask]
    if len(subset) > 5:
        avg = subset["Next_Return"].mean() * 100
        win = (subset["Next_Return"] > 0).mean() * 100
        count = len(subset)
        results.append((name, count, win, avg))
        direction = "BUY signal" if avg > 0 else "SELL signal"
        print(f"  {name:40s} {count:4d} days | Win: {win:.0f}% | Avg: {avg:+.3f}% | {direction}")

print("\n=== WHAT LOSES ===")
losers = {
    "BUY in downtrend (counter-trend)":  (df["Close"] < df["SMA50"]) & (df["Close"] < df["EMA20"]),
    "Low volume day (<0.7x)":            df["Vol_Ratio"] < 0.7,
    "SELL in uptrend (counter-trend)":   (df["Close"] > df["SMA50"]) & (df["Close"] > df["EMA20"]),
    "Pre-holiday (Friday)":              df.index.weekday == 4,
}
for name, mask in losers.items():
    subset = df[mask]
    if len(subset) > 5:
        avg = subset["Next_Return"].mean() * 100
        win = (subset["Next_Return"] > 0).mean() * 100
        print(f"  {name:40s} {len(subset):4d} days | Win: {win:.0f}% | Avg: {avg:+.3f}%")

print("\n=== STRATEGY PERFORMANCE BY REGIME ===")
# Simulate: trend-follow in bullish, mean-revert in sideways, RSI in oversold
for regime in ["bullish_normal", "bearish_normal", "sideways_normal", "pullback_normal"]:
    subset = df[df["Regime"] == regime]
    if len(subset) > 10:
        trend_follow = (subset["Next_Return"] * np.sign(subset["Daily_Return"])).mean() * 100
        mean_revert = (subset["Next_Return"] * -np.sign(subset["Daily_Return"])).mean() * 100
        print(f"  {regime:25s} | Trend-follow: {trend_follow:+.3f}% | Mean-revert: {mean_revert:+.3f}% | Best: {'Trend' if trend_follow > mean_revert else 'Revert'}")
