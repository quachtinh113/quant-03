import os
import sys
from datetime import datetime, timezone
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import MetaTrader5 as mt5

terminal_path = os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe")
if not mt5.initialize(path=terminal_path):
    print("MT5 Init Failed:", mt5.last_error())
    sys.exit(1)

now = datetime.now(timezone.utc)
start_week = datetime(2026, 10, 19, 0, 0, 0, tzinfo=timezone.utc)

deals = mt5.history_deals_get(start_week, now)
deals_df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())

entries = deals_df[deals_df['entry'] == 0].copy()
exits = deals_df[deals_df['entry'] == 1].copy()

# Match round turns
round_turns = []
for _, ex in exits.iterrows():
    pos_id = ex['position_id']
    matching_entries = entries[entries['position_id'] == pos_id]
    if len(matching_entries) > 0:
        en = matching_entries.iloc[0]
        ot = datetime.fromtimestamp(en['time'], tz=timezone.utc)
        ct = datetime.fromtimestamp(ex['time'], tz=timezone.utc)
        dur_h = (ct - ot).total_seconds() / 3600.0
        en_price = en['price']
        ex_price = ex['price']
        direction = "BUY" if en['type'] == 0 else "SELL"
    else:
        ot = datetime.fromtimestamp(ex['time'], tz=timezone.utc)
        ct = ot
        dur_h = 0.0
        en_price = ex['price']
        ex_price = ex['price']
        direction = "BUY" if ex['type'] == 1 else "SELL"

    net = ex['profit'] + ex['commission'] + ex['swap']
    round_turns.append({
        'ticket': ex['ticket'],
        'position_id': pos_id,
        'symbol': ex['symbol'],
        'direction': direction,
        'volume': ex['volume'],
        'open_time': ot,
        'close_time': ct,
        'duration_hours': round(dur_h, 2),
        'open_price': en_price,
        'close_price': ex_price,
        'gross_profit': ex['profit'],
        'net_pnl': round(net, 2),
        'comment': ex['comment']
    })

rt_df = pd.DataFrame(round_turns).sort_values(by='close_time').reset_index(drop=True)

# 1. Analyze Losing Streaks
rt_df['is_win'] = rt_df['net_pnl'] > 0
streaks = []
current_streak = 0
streak_type = None

for idx, r in rt_df.iterrows():
    if r['is_win']:
        if streak_type == 'LOSS':
            streaks.append(('LOSS', current_streak, idx - current_streak, idx - 1))
        streak_type = 'WIN'
        current_streak += 1
    else:
        if streak_type == 'WIN':
            streaks.append(('WIN', current_streak, idx - current_streak, idx - 1))
        streak_type = 'LOSS'
        current_streak += 1

if streak_type is not None:
    streaks.append((streak_type, current_streak, len(rt_df) - current_streak, len(rt_df) - 1))

print("=" * 80)
print("1. TRUY VẾT CÁC CHUỖI THUA LỖ (LOSING STREAKS)")
print("=" * 80)
loss_streaks = [s for s in streaks if s[0] == 'LOSS']
loss_streaks.sort(key=lambda x: x[1], reverse=True)

for s in loss_streaks[:3]:
    cnt, start_idx, end_idx = s[1], s[2], s[3]
    streak_deals = rt_df.iloc[start_idx:end_idx+1]
    loss_sum = streak_deals['net_pnl'].sum()
    print(f"\n🔥 Chuỗi thua dài {cnt} lệnh liên tiếp | Tổng thiệt hại: ${loss_sum:,.2f} USD")
    print(f"   Thời gian: từ {streak_deals.iloc[0]['close_time'].strftime('%m-%d %H:%M')} đến {streak_deals.iloc[-1]['close_time'].strftime('%m-%d %H:%M')}")
    print("   Chi tiết các lệnh:")
    for _, d in streak_deals.iterrows():
        print(f"   - #{d['ticket']} | {d['symbol']} {d['direction']} {d['volume']}L | Giữ: {d['duration_hours']}h | Net: ${d['net_pnl']:+,.2f} | Comment: {d['comment']}")

# 2. Cumulative Equity Curve & Drawdown Analysis
rt_df['cum_pnl'] = rt_df['net_pnl'].cumsum()
start_equity = 8771.22  # High water mark on Oct 19
rt_df['equity'] = start_equity + rt_df['cum_pnl']
rt_df['peak'] = rt_df['equity'].cummax()
rt_df['drawdown_usd'] = rt_df['equity'] - rt_df['peak']
rt_df['drawdown_pct'] = (rt_df['drawdown_usd'] / rt_df['peak']) * 100

max_dd_row = rt_df.loc[rt_df['drawdown_pct'].idxmin()]
print("\n" + "=" * 80)
print("2. ĐIỂM SỤT GIẢM VỐN LỚN NHẤT (MAX DRAWDOWN EVENT)")
print("=" * 80)
print(f"Thời điểm DD sâu nhất: {max_dd_row['close_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"Equity tại đáy: ${max_dd_row['equity']:,.2f} USD | Đỉnh trước đó: ${max_dd_row['peak']:,.2f} USD")
print(f"Drawdown lớn nhất: ${max_dd_row['drawdown_usd']:,.2f} USD ({max_dd_row['drawdown_pct']:.2f}%)")

# 3. Post-V9 Exit Reason & Buffer Analysis
v9_time = datetime(2026, 10, 22, 18, 15, 0, tzinfo=timezone.utc)
v9_deals = rt_df[rt_df['close_time'] >= v9_time].copy()

print("\n" + "=" * 80)
print(f"3. HIỆU SUẤT EXIT ARBITRATOR & TRAILING STOP POST-V9 ({len(v9_deals)} deals)")
print("=" * 80)

def classify_exit(c):
    cs = str(c).lower()
    if 'tp' in cs or 'take' in cs: return 'Take Profit (TP Hit)'
    elif 'sl' in cs or 'stop' in cs: return 'Stop Loss / Trailing SL Hit'
    elif 'fleet' in cs: return 'Fleet Close (Panic)'
    else: return 'Signal Exit / Manual'

v9_deals['exit_cat'] = v9_deals['comment'].apply(classify_exit)
print(v9_deals.groupby('exit_cat').agg(
    count=('net_pnl', 'count'),
    wins=('net_pnl', lambda x: (x > 0).sum()),
    total_pnl=('net_pnl', 'sum'),
    avg_pnl=('net_pnl', 'mean'),
    avg_duration_h=('duration_hours', 'mean')
).to_string())

mt5.shutdown()
