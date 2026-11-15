import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

if not mt5.initialize():
    print("MT5 Init Failed")
    exit(1)

now = datetime.now(timezone.utc)
# Check past 14 days or from Oct 19
start = datetime(2026, 10, 19, 0, 0, 0, tzinfo=timezone.utc)
deals = mt5.history_deals_get(start, now)
orders = mt5.history_orders_get(start, now)
acc = mt5.account_info()

print(f"Account: {acc.login} | Server: {acc.server}")
print(f"Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f} | Profit: ${acc.profit:+,.2f}")
print(f"Total deals: {len(deals) if deals else 0}")

df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
entries = df_deals[df_deals['entry'] == 0].copy()
exits = df_deals[df_deals['entry'] == 1].copy()

# Match closed trades
trades = []
for _, ex in exits.iterrows():
    pos_id = ex['position_id']
    matching_en = entries[entries['position_id'] == pos_id]
    if len(matching_en) > 0:
        en = matching_en.iloc[0]
        ot = datetime.fromtimestamp(en['time'], tz=timezone.utc)
        ct = datetime.fromtimestamp(ex['time'], tz=timezone.utc)
        open_price = en['price']
        direction = "BUY" if en['type'] == 0 else "SELL"
    else:
        ot = datetime.fromtimestamp(ex['time'], tz=timezone.utc)
        ct = ot
        open_price = ex['price']
        direction = "BUY" if ex['type'] == 1 else "SELL"
    
    close_price = ex['price']
    dur_min = (ct - ot).total_seconds() / 60.0
    dur_h = dur_min / 60.0
    net_pnl = ex['profit'] + ex['commission'] + ex['swap']
    
    trades.append({
        'ticket': ex['ticket'],
        'position_id': pos_id,
        'symbol': ex['symbol'],
        'direction': direction,
        'volume': ex['volume'],
        'open_time': ot,
        'close_time': ct,
        'open_date': ot.date(),
        'close_date': ct.date(),
        'open_hour_utc': ot.hour,
        'close_hour_utc': ct.hour,
        'duration_min': round(dur_min, 1),
        'duration_hours': round(dur_h, 2),
        'open_price': open_price,
        'close_price': close_price,
        'gross_profit': ex['profit'],
        'commission': ex['commission'],
        'swap': ex['swap'],
        'net_pnl': round(net_pnl, 2),
        'comment': ex['comment']
    })

tdf = pd.DataFrame(trades).sort_values(by='close_time').reset_index(drop=True)
print(f"Matched closed trades: {len(tdf)}")

# Daily breakdown
daily = tdf.groupby('close_date').agg(
    trades=('net_pnl', 'count'),
    wins=('net_pnl', lambda x: (x > 0).sum()),
    gross_win=('net_pnl', lambda x: x[x > 0].sum()),
    gross_loss=('net_pnl', lambda x: abs(x[x < 0].sum())),
    net_pnl=('net_pnl', 'sum'),
    avg_win=('net_pnl', lambda x: x[x > 0].mean() if (x > 0).any() else 0),
    avg_loss=('net_pnl', lambda x: abs(x[x < 0].mean()) if (x < 0).any() else 0)
)
daily['win_rate%'] = (daily['wins'] / daily['trades'] * 100).round(1)
daily['pf'] = (daily['gross_win'] / daily['gross_loss']).replace(np.nan, 999.0).round(2)
daily['net_pnl'] = daily['net_pnl'].round(2)

print("\n--- DAILY PNL BREAKDOWN ---")
print(daily.to_string())

# Total stats
wins = tdf[tdf['net_pnl'] > 0]
losses = tdf[tdf['net_pnl'] < 0]
print("\n--- OVERALL METRICS ---")
print(f"Total Net PnL: ${tdf['net_pnl'].sum():+,.2f}")
print(f"Win Rate: {len(wins)/len(tdf)*100:.1f}% ({len(wins)}W / {len(losses)}L)")
print(f"Profit Factor: {wins['net_pnl'].sum() / abs(losses['net_pnl'].sum()):.2f}")
print(f"Avg Win: +${wins['net_pnl'].mean():.2f} | Avg Loss: -${abs(losses['net_pnl'].mean()):.2f}")

# Symbol breakdown
sym_stat = tdf.groupby('symbol').agg(
    trades=('net_pnl', 'count'),
    wins=('net_pnl', lambda x: (x > 0).sum()),
    net_pnl=('net_pnl', 'sum'),
    gross_win=('net_pnl', lambda x: x[x > 0].sum()),
    gross_loss=('net_pnl', lambda x: abs(x[x < 0].sum())),
    avg_duration_h=('duration_hours', 'mean')
)
sym_stat['win_rate%'] = (sym_stat['wins'] / sym_stat['trades'] * 100).round(1)
sym_stat['pf'] = (sym_stat['gross_win'] / sym_stat['gross_loss']).replace(np.nan, 999.0).round(2)
sym_stat['net_pnl'] = sym_stat['net_pnl'].round(2)
print("\n--- SYMBOL BREAKDOWN ---")
print(sym_stat.sort_values(by='net_pnl', ascending=False).to_string())

# Current open positions
positions = mt5.positions_get()
print("\n--- CURRENT OPEN POSITIONS ---")
if positions:
    for p in positions:
        print(f"#{p.ticket} | {p.symbol} {'BUY' if p.type==0 else 'SELL'} {p.volume}L | Open: {p.price_open} | Cur: {p.price_current} | SL: {p.sl} | TP: {p.tp} | Profit: ${p.profit:+.2f} | Comment: {p.comment}")
else:
    print("None")

mt5.shutdown()
