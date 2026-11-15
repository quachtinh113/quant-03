import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

if not mt5.initialize():
    print("MT5 Init Failed")
    exit(1)

# Focus on this week: Oct 26, 2026 00:00:00 UTC to Oct 31, 2026
start_week = datetime(2026, 10, 26, 0, 0, 0, tzinfo=timezone.utc)
now = datetime.now(timezone.utc)

deals = mt5.history_deals_get(start_week, now)
df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
entries = df_deals[df_deals['entry'] == 0].copy()
exits = df_deals[df_deals['entry'] == 1].copy()

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
    
    # Exness server time is typically UTC+0 in winter or UTC+2/3 depending on DST.
    # Let's check hour of day (UTC)
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
print(f"=== THIS WEEK (26/10 -> 31/10) TRADES: {len(tdf)} ===")
print(f"Net PnL: ${tdf['net_pnl'].sum():+,.2f} USD")
wins = tdf[tdf['net_pnl'] > 0]
losses = tdf[tdf['net_pnl'] < 0]
print(f"Gross Win: +${wins['net_pnl'].sum():,.2f} ({len(wins)} trades)")
print(f"Gross Loss: -${abs(losses['net_pnl'].sum()):,.2f} ({len(losses)} trades)")
print(f"Win Rate: {len(wins)/len(tdf)*100:.1f}%")
print(f"Profit Factor: {wins['net_pnl'].sum() / abs(losses['net_pnl'].sum()):.2f}")
print(f"Avg Win: +${wins['net_pnl'].mean():.2f} | Avg Loss: -${abs(losses['net_pnl'].mean()):.2f}")

# Breakdown by Symbol for this week
print("\n--- THIS WEEK SYMBOL STATS ---")
w_sym = tdf.groupby('symbol').agg(
    trades=('net_pnl', 'count'),
    wins=('net_pnl', lambda x: (x > 0).sum()),
    net=('net_pnl', 'sum'),
    gross_win=('net_pnl', lambda x: x[x > 0].sum()),
    gross_loss=('net_pnl', lambda x: abs(x[x < 0].sum())),
    avg_win=('net_pnl', lambda x: x[x > 0].mean() if (x > 0).any() else 0),
    avg_loss=('net_pnl', lambda x: abs(x[x < 0].mean()) if (x < 0).any() else 0),
    avg_dur=('duration_hours', 'mean')
)
w_sym['win_rate%'] = (w_sym['wins'] / w_sym['trades'] * 100).round(1)
w_sym['pf'] = (w_sym['gross_win'] / w_sym['gross_loss']).replace(np.nan, 999.0).round(2)
print(w_sym.sort_values(by='net', ascending=False).to_string())

# Investigate EURGBP trades this week
print("\n--- EURGBP ANALYSIS THIS WEEK ---")
eurgbp = tdf[tdf['symbol'] == 'EURGBP']
print(f"EURGBP Total: {len(eurgbp)} trades, Net: ${eurgbp['net_pnl'].sum():+,.2f}")
print("Exit comments breakdown:")
print(eurgbp['comment'].value_counts().head(10))
print("Top 5 worst EURGBP losses:")
print(eurgbp.sort_values(by='net_pnl').head(5)[['ticket', 'direction', 'volume', 'open_time', 'close_time', 'duration_min', 'net_pnl', 'comment']].to_string())

# Hourly PnL distribution (Golden vs Toxic hours)
print("\n--- HOURLY PERFORMANCE (UTC OPEN HOUR) ---")
hourly = tdf.groupby('open_hour_utc').agg(
    trades=('net_pnl', 'count'),
    wins=('net_pnl', lambda x: (x > 0).sum()),
    net=('net_pnl', 'sum')
)
hourly['win_rate%'] = (hourly['wins'] / hourly['trades'] * 100).round(1)
print(hourly.to_string())

# Holding time brackets
print("\n--- HOLDING TIME BRACKETS (THIS WEEK) ---")
bins = [0, 0.25, 1.0, 4.0, 12.0, 24.0, 1000]
labels = ['< 15m', '15m - 1h', '1h - 4h', '4h - 12h', '12h - 24h', '> 24h']
tdf['dur_bracket'] = pd.cut(tdf['duration_hours'], bins=bins, labels=labels, right=False)
ht = tdf.groupby('dur_bracket', observed=False).agg(
    trades=('net_pnl', 'count'),
    wins=('net_pnl', lambda x: (x > 0).sum()),
    net=('net_pnl', 'sum'),
    gross_win=('net_pnl', lambda x: x[x > 0].sum()),
    gross_loss=('net_pnl', lambda x: abs(x[x < 0].sum())),
)
ht['win_rate%'] = (ht['wins'] / ht['trades'] * 100).round(1)
ht['pf'] = (ht['gross_win'] / ht['gross_loss']).replace(np.nan, 999.0).round(2)
print(ht.to_string())

# Bad Loss vs Good Loss definition:
# Bad Loss: Trades exceeding $35 max risk OR trades held > 4 hours in sideway that lost, OR trades entered during toxic hours, OR slippage/panic close
# Good Loss: Controlled SL hit <= $20 within normal session
print("\n--- LOSS ATTRIBUTION ---")
bad_losses = losses[(abs(losses['net_pnl']) > 30.0) | (losses['duration_hours'] > 4.0)]
good_losses = losses[~losses.index.isin(bad_losses.index)]
print(f"Total Losses: {len(losses)} trades (-${abs(losses['net_pnl'].sum()):,.2f} USD)")
print(f"Bad Losses (Slippage / Long Hold / Spike): {len(bad_losses)} trades (-${abs(bad_losses['net_pnl'].sum()):,.2f} USD)")
print(f"Good Controlled Losses (Model expected stop): {len(good_losses)} trades (-${abs(good_losses['net_pnl'].sum()):,.2f} USD)")

potential_pnl = tdf['net_pnl'].sum() + abs(bad_losses['net_pnl'].sum())
print(f"\nActual Net PnL: ${tdf['net_pnl'].sum():+,.2f} USD")
print(f"Potential Net PnL (Without Bad Losses): ${potential_pnl:+,.2f} USD")

mt5.shutdown()
