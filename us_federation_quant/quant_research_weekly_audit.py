import os
import sys
from datetime import datetime, timezone, timedelta
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

# 1. Fetch Deals & Orders
deals = mt5.history_deals_get(start_week, now)
orders = mt5.history_orders_get(start_week, now)

if not deals:
    print("No deals found.")
    mt5.shutdown()
    sys.exit(0)

deals_df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
orders_df = pd.DataFrame(list(orders), columns=orders[0]._asdict().keys()) if orders else pd.DataFrame()

# Match entries and exits by position_id
entries = deals_df[deals_df['entry'] == 0].copy()
exits = deals_df[deals_df['entry'] == 1].copy()

# Map exits with entries by position_id
closed_trades = []
for _, exit_deal in exits.iterrows():
    pos_id = exit_deal['position_id']
    pos_entries = entries[entries['position_id'] == pos_id]
    if len(pos_entries) > 0:
        entry_deal = pos_entries.iloc[0]
        open_time = datetime.fromtimestamp(entry_deal['time'], tz=timezone.utc)
        close_time = datetime.fromtimestamp(exit_deal['time'], tz=timezone.utc)
        duration_min = (close_time - open_time).total_seconds() / 60.0
        open_price = entry_deal['price']
        close_price = exit_deal['price']
        direction = "BUY" if entry_deal['type'] == 0 else "SELL"
    else:
        open_time = datetime.fromtimestamp(exit_deal['time'], tz=timezone.utc)
        close_time = open_time
        duration_min = 0.0
        open_price = exit_deal['price']
        close_price = exit_deal['price']
        direction = "BUY" if exit_deal['type'] == 1 else "SELL"

    net_pnl = exit_deal['profit'] + exit_deal['commission'] + exit_deal['swap']
    
    # Classify asset class
    sym = exit_deal['symbol'].upper()
    if 'XAU' in sym or 'GOLD' in sym:
        asset_class = 'Commodities (Gold)'
    elif any(k in sym for k in ['USTEC', 'US30', 'HK50', 'UK100', 'US100']):
        asset_class = 'Equity Indices'
    elif any(k in sym for k in ['NVDA', 'AAPL', 'MSFT', 'AMZN', 'GOOG', 'META', 'TSLA', 'WMT', 'PG', 'V', 'JNJ', 'XOM']):
        asset_class = 'US Equities'
    elif any(k in sym for k in ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCHF', 'USDJPY']):
        asset_class = 'FX Majors'
    else:
        asset_class = 'FX Crosses'

    closed_trades.append({
        'ticket': exit_deal['ticket'],
        'position_id': pos_id,
        'symbol': exit_deal['symbol'],
        'asset_class': asset_class,
        'direction': direction,
        'volume': exit_deal['volume'],
        'open_time': open_time,
        'close_time': close_time,
        'duration_min': round(duration_min, 1),
        'duration_hours': round(duration_min / 60.0, 2),
        'open_price': open_price,
        'close_price': close_price,
        'gross_profit': exit_deal['profit'],
        'commission': exit_deal['commission'],
        'swap': exit_deal['swap'],
        'net_pnl': round(net_pnl, 2),
        'comment': exit_deal['comment']
    })

ct_df = pd.DataFrame(closed_trades)
print(f"Loaded {len(ct_df)} matched closed round-turn positions.\n")

# 1. Performance by Asset Class
print("=" * 80)
print("1. HIỆU SUẤT THEO NHÓM SẢN PHẨM (ASSET CLASS BREAKDOWN)")
print("=" * 80)
asset_summary = ct_df.groupby('asset_class').agg(
    trades=('net_pnl', 'count'),
    wins=('net_pnl', lambda x: (x > 0).sum()),
    gross_win=('net_pnl', lambda x: x[x > 0].sum()),
    gross_loss=('net_pnl', lambda x: abs(x[x < 0].sum())),
    net_pnl=('net_pnl', 'sum'),
    avg_win=('net_pnl', lambda x: x[x > 0].mean() if (x > 0).any() else 0),
    avg_loss=('net_pnl', lambda x: abs(x[x < 0].mean()) if (x < 0).any() else 0),
    avg_duration_h=('duration_hours', 'mean')
)
asset_summary['win_rate%'] = (asset_summary['wins'] / asset_summary['trades'] * 100).round(1)
asset_summary['profit_factor'] = (asset_summary['gross_win'] / asset_summary['gross_loss']).replace(np.nan, 999.0).round(2)
asset_summary['net_pnl'] = asset_summary['net_pnl'].round(2)
print(asset_summary[['trades', 'win_rate%', 'profit_factor', 'net_pnl', 'avg_win', 'avg_loss', 'avg_duration_h']].to_string())

# Check XAUUSD specific activity
print("\n" + "=" * 80)
print("KIỂM TRA XAUUSD RIÊNG BIỆT")
print("=" * 80)
xau_trades = ct_df[ct_df['symbol'].str.contains('XAU', case=False)]
print(f"Số lệnh XAUUSD tuần này: {len(xau_trades)}")
if len(xau_trades) > 0:
    print(xau_trades[['ticket', 'direction', 'volume', 'open_time', 'close_time', 'duration_hours', 'net_pnl', 'comment']].to_string())

# 2. Holding Time vs PnL Analysis
print("\n" + "=" * 80)
print("2. PHÂN TÍCH HOLDING TIME (THỜI GIAN GIỮ LỆNH VS HIỆU QUẢ PNL)")
print("=" * 80)
bins = [0, 15, 60, 240, 720, 1440, 10000]
labels = ['< 15m (Scalp)', '15m - 1h (Intraday Fast)', '1h - 4h (H1 Session)', '4h - 12h (H4 Multi-Session)', '12h - 24h (Daily Swing)', '> 24h (Multi-Day Hold)']
ct_df['time_bracket'] = pd.cut(ct_df['duration_min'], bins=bins, labels=labels, right=False)

ht_summary = ct_df.groupby('time_bracket', observed=False).agg(
    trades=('net_pnl', 'count'),
    wins=('net_pnl', lambda x: (x > 0).sum()),
    gross_win=('net_pnl', lambda x: x[x > 0].sum()),
    gross_loss=('net_pnl', lambda x: abs(x[x < 0].sum())),
    net_pnl=('net_pnl', 'sum'),
    avg_pnl=('net_pnl', 'mean')
)
ht_summary['win_rate%'] = (ht_summary['wins'] / ht_summary['trades'] * 100).round(1)
ht_summary['profit_factor'] = (ht_summary['gross_win'] / ht_summary['gross_loss']).replace(np.nan, 999.0).round(2)
print(ht_summary[['trades', 'win_rate%', 'profit_factor', 'net_pnl', 'avg_pnl']].to_string())

winners = ct_df[ct_df['net_pnl'] > 0]
losers = ct_df[ct_df['net_pnl'] < 0]
print(f"\nThời gian giữ lệnh trung bình của lệnh THẮNG: {winners['duration_hours'].mean():.2f} giờ ({winners['duration_min'].mean():.1f} phút)")
print(f"Thời gian giữ lệnh trung bình của lệnh THUA:  {losers['duration_hours'].mean():.2f} giờ ({losers['duration_min'].mean():.1f} phút)")
print(f"Lệnh thắng giữ lâu nhất: {winners['duration_hours'].max():.2f} giờ (${winners.loc[winners['duration_hours'].idxmax(), 'net_pnl']:+.2f} USD)")
print(f"Lệnh thua giữ lâu nhất:  {losers['duration_hours'].max():.2f} giờ (${losers.loc[losers['duration_hours'].idxmax(), 'net_pnl']:+.2f} USD)")

# 3. Execution Drag / Latency Analysis
print("\n" + "=" * 80)
print("3. PHÂN TÍCH LỆNH CÓ SLIPPAGE / CHÊNH LỆCH ENTRY & LOG LATENCY")
print("=" * 80)
mt5.shutdown()
