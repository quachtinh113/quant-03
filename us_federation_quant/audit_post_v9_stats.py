import MetaTrader5 as mt5
from datetime import datetime, timezone
import pandas as pd

mt5.initialize()
deals = mt5.history_deals_get(datetime(2026, 10, 22, 18, 15, 0, tzinfo=timezone.utc), datetime.now(timezone.utc))
if deals:
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    exits = df[((df['entry'] == 1) | (df['profit'] != 0)) & (df['type'] <= 1)].copy()
    exits['net'] = exits['profit'] + exits['commission'] + exits['swap']
    wins = exits[exits['net'] > 0]
    losses = exits[exits['net'] < 0]
    print("=== POST-V9 REFACTORING PERFORMANCE (22/10 18:15 UTC -> 24/10) ===")
    print(f"Closed Trades Count: {len(exits)}")
    print(f"Total Net Realized Profit: ${exits['net'].sum():+,.2f} USD")
    print(f"Gross Profit: +${wins['net'].sum():,.2f} USD ({len(wins)} wins)")
    print(f"Gross Loss:   -${abs(losses['net'].sum()):,.2f} USD ({len(losses)} losses)")
    win_rate = len(wins)/len(exits)*100 if len(exits) else 0
    gross_win = wins['net'].sum()
    gross_loss = abs(losses['net'].sum())
    pf = (gross_win / gross_loss) if gross_loss > 0 else 999.0
    avg_win = wins['net'].mean() if len(wins) else 0
    avg_loss = abs(losses['net'].mean()) if len(losses) else 0
    rr = (avg_win / avg_loss) if avg_loss else 0
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Profit Factor (PF): {pf:.2f}")
    print(f"Avg Win: +${avg_win:.2f} USD | Avg Loss: -${avg_loss:.2f} USD | R:R = {rr:.2f}:1")
    print("\nPerformance by Symbol:")
    stat = exits.groupby('symbol').agg(
        trades=('net', 'count'),
        wins=('net', lambda x: (x > 0).sum()),
        total_pnl=('net', 'sum'),
        avg_pnl=('net', 'mean')
    ).sort_values(by='total_pnl', ascending=False)
    stat['win_rate%'] = (stat['wins'] / stat['trades'] * 100).round(1)
    print(stat.to_string())

acc = mt5.account_info()
print(f"\nCurrent Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f} | Floating: ${acc.profit:+,.2f}")
mt5.shutdown()
