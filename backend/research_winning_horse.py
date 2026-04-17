"""Winning Horse Research — What predicts a stock will trend all day?"""
import sys
sys.path.insert(0, ".")
import yfinance as yf
import numpy as np

stocks = ["RELIANCE", "SBIN", "HDFCBANK", "ITC", "SUNPHARMA",
          "BAJFINANCE", "TITAN", "LT", "AXISBANK", "WIPRO",
          "HCLTECH", "POWERGRID", "TATASTEEL", "ICICIBANK", "INFY",
          "BHARTIARTL", "COALINDIA", "NTPC", "KOTAKBANK", "HINDUNILVR"]

print("=" * 70)
print("WINNING HORSE RESEARCH")
print("20 Nifty stocks x 30 days x 15m candles")
print("=" * 70)

first30_same = 0
first30_reverse = 0
strong_moves = []
weak_moves = []
high_vol_moves = []
low_vol_moves = []
orb_wins = 0
orb_total = 0
entry_data = {2: [], 3: [], 4: [], 6: [], 8: []}

# Backtest: if we BUY the top 3 stocks at 10:00 AM based on first 45 min performance
top3_buy_pnl = []
random_buy_pnl = []

for sym in stocks:
    try:
        df = yf.Ticker(sym + ".NS").history(period="30d", interval="15m")
        if df is None or len(df) < 50:
            continue

        df["date"] = df.index.date

        for date in df["date"].unique():
            day = df[df["date"] == date]
            if len(day) < 12:
                continue

            day_open = float(day.iloc[0]["Open"])
            first30_high = float(day.iloc[:2]["High"].max())
            first30_low = float(day.iloc[:2]["Low"].min())
            first30_close = float(day.iloc[1]["Close"])
            day_close = float(day.iloc[-1]["Close"])

            first30_ret = (first30_close - day_open) / day_open * 100
            full_ret = (day_close - day_open) / day_open * 100

            # R1: First 30 min predicts direction?
            if first30_ret > 0.1 and full_ret > 0.1:
                first30_same += 1
            elif first30_ret < -0.1 and full_ret < -0.1:
                first30_same += 1
            elif abs(first30_ret) > 0.1 and abs(full_ret) > 0.1:
                first30_reverse += 1

            # R2: Strong vs weak start
            if abs(first30_ret) > 0.5:
                strong_moves.append(abs(full_ret))
            elif abs(first30_ret) < 0.2:
                weak_moves.append(abs(full_ret))

            # R3: Volume predictor
            if len(day) >= 8:
                first_hr_vol = float(day.iloc[:4]["Volume"].sum())
                total_vol = float(day["Volume"].sum())
                vol_ratio = first_hr_vol / (total_vol / (len(day) / 4)) if total_vol > 0 else 1
                if vol_ratio > 1.3:
                    high_vol_moves.append(abs(full_ret))
                else:
                    low_vol_moves.append(abs(full_ret))

            # R4: ORB success
            rest = day.iloc[2:]
            if len(rest) >= 4:
                if float(rest["High"].max()) > first30_high:
                    orb_total += 1
                    if day_close > first30_high:
                        orb_wins += 1
                if float(rest["Low"].min()) < first30_low:
                    orb_total += 1
                    if day_close < first30_low:
                        orb_wins += 1

            # R5: Entry time capture
            for idx in entry_data:
                if len(day) > idx + 2:
                    entry_p = float(day.iloc[idx]["Open"])
                    full_move = abs(day_close - day_open)
                    captured = abs(day_close - entry_p)
                    if full_move > 0:
                        entry_data[idx].append(captured / full_move * 100)
    except:
        continue

# Print results
total_r1 = first30_same + first30_reverse
print("\n--- R1: First 30 min predicts rest of day ---")
if total_r1 > 0:
    print(f"  YES same direction: {first30_same*100//total_r1}% of {total_r1} days")

print("\n--- R2: Strong start → Bigger day ---")
if strong_moves and weak_moves:
    print(f"  Strong first 30 min (>0.5%): avg day move = {np.mean(strong_moves):.2f}%")
    print(f"  Weak first 30 min (<0.2%):   avg day move = {np.mean(weak_moves):.2f}%")
    print(f"  Strong start = {np.mean(strong_moves)/np.mean(weak_moves):.1f}x bigger day")

print("\n--- R3: Volume as predictor ---")
if high_vol_moves and low_vol_moves:
    print(f"  High first-hour volume: avg move = {np.mean(high_vol_moves):.2f}%")
    print(f"  Low first-hour volume:  avg move = {np.mean(low_vol_moves):.2f}%")

print("\n--- R4: Opening Range Breakout ---")
if orb_total > 0:
    print(f"  ORB success rate: {orb_wins*100//orb_total}% of {orb_total} breakouts")

print("\n--- R5: Best Entry Time ---")
time_labels = {2: "9:45", 3: "10:00", 4: "10:15", 6: "10:45", 8: "11:15"}
for idx in sorted(entry_data.keys()):
    if entry_data[idx]:
        avg = np.mean(entry_data[idx])
        label = time_labels.get(idx, f"candle {idx}")
        print(f"  Entry at {label}: captures {avg:.0f}% of day move")

# R6: Ranking stocks by first 45 min → trading top 3
print("\n--- R6: Buy top 3 strongest stocks at 10:00 AM ---")
for sym in stocks[:10]:
    try:
        df = yf.Ticker(sym + ".NS").history(period="30d", interval="15m")
        if df is None or len(df) < 20:
            continue
        df["date"] = df.index.date
        for date in df["date"].unique():
            day = df[df["date"] == date]
            if len(day) < 12:
                continue
            # First 45 min return (3 candles)
            first45_ret = (float(day.iloc[2]["Close"]) - float(day.iloc[0]["Open"])) / float(day.iloc[0]["Open"]) * 100
            # Rest of day return from 10:00 entry
            entry_at_10 = float(day.iloc[3]["Open"])
            close = float(day.iloc[-1]["Close"])
            rest_ret = (close - entry_at_10) / entry_at_10 * 100

            if first45_ret > 0.3:  # Top performers first 45 min
                top3_buy_pnl.append(rest_ret)
            else:
                random_buy_pnl.append(rest_ret)
    except:
        continue

if top3_buy_pnl and random_buy_pnl:
    top_win = sum(1 for r in top3_buy_pnl if r > 0) * 100 // len(top3_buy_pnl)
    rand_win = sum(1 for r in random_buy_pnl if r > 0) * 100 // len(random_buy_pnl)
    print(f"  BUY stocks UP >0.3% in first 45 min:")
    print(f"    Win rate: {top_win}% | Avg return: {np.mean(top3_buy_pnl):+.3f}% | {len(top3_buy_pnl)} trades")
    print(f"  BUY other stocks:")
    print(f"    Win rate: {rand_win}% | Avg return: {np.mean(random_buy_pnl):+.3f}% | {len(random_buy_pnl)} trades")
    improvement = np.mean(top3_buy_pnl) - np.mean(random_buy_pnl)
    print(f"  EDGE: {improvement:+.3f}% per trade better")
