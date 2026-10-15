import sys
from datetime import datetime, timezone, timedelta
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
import MetaTrader5 as mt5

if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit(1)

now = datetime.now(timezone.utc)
# Week 41 start: Monday Oct 12, 2026 00:00:00 UTC
start_week = datetime(2026, 10, 12, 0, 0, 0, tzinfo=timezone.utc)

deals = mt5.history_deals_get(start_week, now)
acc = mt5.account_info()

print("=" * 80)
print(f"📊 KIỂM TOÁN TỔNG THỂ TUẦN 41 (12/10/2026 -> 15/10/2026 UTC)")
print("=" * 80)
print(f"Account: {acc.login} @ {acc.server}")
print(f"Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f} | Floating: ${acc.profit:,.2f}")
print(f"Margin: ${acc.margin:,.2f} | Free Margin: ${acc.margin_free:,.2f} | Margin Level: {acc.margin_level:.1f}%")

if deals:
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    # Closed deals: entry == 1 or profit/commission/swap != 0
    exit_deals = df[(df['entry'] == 1) | (df['profit'] != 0)].copy()
    print(f"\nTổng số deals ghi nhận: {len(df)} | Số lệnh chốt (Exit Deals): {len(exit_deals)}")
    
    if len(exit_deals) > 0:
        exit_deals['net_pnl'] = exit_deals['profit'] + exit_deals['commission'] + exit_deals['swap']
        exit_deals['time_dt'] = pd.to_datetime(exit_deals['time'], unit='s', utc=True)
        exit_deals['date'] = exit_deals['time_dt'].dt.date
        
        wins = exit_deals[exit_deals['net_pnl'] > 0]
        losses = exit_deals[exit_deals['net_pnl'] < 0]
        be = exit_deals[exit_deals['net_pnl'] == 0]
        
        total_net = exit_deals['net_pnl'].sum()
        gross_win = wins['net_pnl'].sum()
        gross_loss = abs(losses['net_pnl'].sum())
        win_rate = len(wins) / len(exit_deals) * 100
        pf = (gross_win / gross_loss) if gross_loss > 0 else 999.0
        
        avg_win = wins['net_pnl'].mean() if len(wins) > 0 else 0.0
        avg_loss = abs(losses['net_pnl'].mean()) if len(losses) > 0 else 0.0
        rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        print(f"\n--- CHỈ SỐ PNL TUẦN NÀY ---")
        print(f"Net Realized PnL:       ${total_net:+,.2f} USD")
        print(f"Gross Profit:           +${gross_win:,.2f} USD ({len(wins)} lệnh)")
        print(f"Gross Loss:             -${gross_loss:,.2f} USD ({len(losses)} lệnh)")
        print(f"Tỷ lệ thắng (Win Rate): {win_rate:.1f}% ({len(wins)}W / {len(losses)}L / {len(be)}BE)")
        print(f"Profit Factor:          {pf:.2f}")
        print(f"Trung bình 1 lệnh thắng: +${avg_win:,.2f} USD")
        print(f"Trung bình 1 lệnh thua:  -${avg_loss:,.2f} USD")
        print(f"Tỷ lệ Thưởng/Rủi ro (R:R): {rr_ratio:.2f} : 1  <-- TỬ HUYỆT HỆ THỐNG")

        # Group by Symbol
        print(f"\n--- HIỆU SUẤT THEO SYMBOL TRONG TUẦN ---")
        sym_stat = exit_deals.groupby('symbol').agg(
            trades=('net_pnl', 'count'),
            win_count=('net_pnl', lambda x: (x > 0).sum()),
            total_net=('net_pnl', 'sum'),
            avg_pnl=('net_pnl', 'mean')
        ).sort_values(by='total_net', ascending=False)
        print(sym_stat.to_string())

        # Top 5 losses
        print(f"\n--- TOP 5 LỆNH LỖ NẶNG NHẤT TUẦN ---")
        top_loss = exit_deals.sort_values(by='net_pnl', ascending=True).head(5)
        for _, r in top_loss.iterrows():
            print(f"Ticket #{r['ticket']} | {r['time_dt'].strftime('%Y-%m-%d %H:%M')} | {r['symbol']} | Net: ${r['net_pnl']:,.2f} USD | Comment: {r['comment']}")

        # Top 5 wins
        print(f"\n--- TOP 5 LỆNH THẮNG ĐẬM NHẤT TUẦN ---")
        top_win = exit_deals.sort_values(by='net_pnl', ascending=False).head(5)
        for _, r in top_win.iterrows():
            print(f"Ticket #{r['ticket']} | {r['time_dt'].strftime('%Y-%m-%d %H:%M')} | {r['symbol']} | Net: ${r['net_pnl']:,.2f} USD | Comment: {r['comment']}")
else:
    print("Không có deal nào.")

# Open positions analysis
positions = mt5.positions_get()
print("\n" + "=" * 80)
print(f"📌 PHÂN TÍCH VỊ THẾ ĐANG MỞ (FLOATING DRAWDOWN / PROFIT)")
print("=" * 80)
if positions:
    df_p = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
    df_p['type_str'] = df_p['type'].apply(lambda x: 'BUY' if x == 0 else 'SELL')
    
    total_floating = df_p['profit'].sum()
    be_count = df_p[((df_p['type'] == 0) & (df_p['sl'] >= df_p['price_open'])) | ((df_p['type'] == 1) & (df_p['sl'] <= df_p['price_open']) & (df_p['sl'] > 0))].shape[0]
    
    print(f"Tổng số lệnh mở: {len(df_p)}")
    print(f"Tổng PnL thả nổi: ${total_floating:+,.2f} USD")
    print(f"Số lệnh đã khóa Lãi/Hòa vốn (SL bảo hiểm): {be_count} / {len(df_p)} lệnh")

    sym_pos = df_p.groupby('symbol').agg(
        lots=('volume', 'sum'),
        count=('ticket', 'count'),
        floating=('profit', 'sum')
    ).sort_values(by='floating', ascending=True)
    print("\nTop cặp đang âm (Drawdown):")
    print(sym_pos.head(6).to_string())
    print("\nTop cặp đang dương (Profit):")
    print(sym_pos.tail(6).sort_values(by='floating', ascending=False).to_string())

mt5.shutdown()
