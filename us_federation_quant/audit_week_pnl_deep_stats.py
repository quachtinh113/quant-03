import sys
from datetime import datetime, timezone, timedelta
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import MetaTrader5 as mt5

terminal_path = os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe")
if not mt5.initialize(path=terminal_path):
    print("MT5 Init Failed:", mt5.last_error())
    sys.exit(1)

now = datetime.now(timezone.utc)
# Week 43 start: Monday Oct 19, 2026 00:00:00 UTC
start_week = datetime(2026, 10, 19, 0, 0, 0, tzinfo=timezone.utc)

deals = mt5.history_deals_get(start_week, now)
acc = mt5.account_info()

print("=" * 85)
print(f"📊 KIỂM TOÁN HIỆU SUẤT & PNL TUẦN 43 (19/10/2026 -> 21/10/2026 UTC)")
print("=" * 85)
print(f"🏛️ Account: {acc.login} @ {acc.server}")
print(f"💰 Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f} | Floating PnL: ${acc.profit:+,.2f}")
print(f"🛡️ Margin: ${acc.margin:,.2f} | Free Margin: ${acc.margin_free:,.2f} | Margin Level: {acc.margin_level:.1f}%\n")

if deals:
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    # Closed deals: entry == 1 or profit/commission/swap != 0 (exclude deposits/transfers)
    exit_deals = df[((df['entry'] == 1) | (df['profit'] != 0)) & (df['type'] <= 1)].copy()
    print(f"Tổng số deals ghi nhận: {len(df)} | Số lệnh chốt thực tế (Exit Deals): {len(exit_deals)}")
    
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

        print(f"\n--- 1. CHỈ SỐ PNL TỔNG QUAN TUẦN NÀY ---")
        print(f"Net Realized PnL:       ${total_net:+,.2f} USD")
        print(f"Tổng Lãi (Gross Win):   +${gross_win:,.2f} USD ({len(wins)} lệnh)")
        print(f"Tổng Lỗ (Gross Loss):   -${gross_loss:,.2f} USD ({len(losses)} lệnh)")
        print(f"Tỷ lệ thắng (Win Rate): {win_rate:.1f}% ({len(wins)}W / {len(losses)}L / {len(be)}BE)")
        print(f"Profit Factor (PF):     {pf:.2f}")
        print(f"Trung bình 1 lệnh thắng: +${avg_win:,.2f} USD")
        print(f"Trung bình 1 lệnh thua:  -${avg_loss:,.2f} USD")
        print(f"Tỷ lệ Thưởng/Rủi ro (R:R): {rr_ratio:.2f} : 1")

        # Group by Symbol
        print(f"\n--- 2. HIỆU SUẤT THEO SYMBOL (XẾP HẠNG PNL) ---")
        sym_stat = exit_deals.groupby('symbol').agg(
            trades=('net_pnl', 'count'),
            win_count=('net_pnl', lambda x: (x > 0).sum()),
            total_net=('net_pnl', 'sum'),
            avg_pnl=('net_pnl', 'mean')
        ).sort_values(by='total_net', ascending=False)
        sym_stat['win_rate%'] = (sym_stat['win_count'] / sym_stat['trades'] * 100).round(1)
        sym_stat['total_net'] = sym_stat['total_net'].round(2)
        sym_stat['avg_pnl'] = sym_stat['avg_pnl'].round(2)
        print(sym_stat.to_string())

        # Exit reasons breakdown (from comments)
        print(f"\n--- 3. PHÂN TÍCH NGUYÊN NHÂN ĐÓNG LỆNH (EXIT COMMENTS) ---")
        def classify_comment(c):
            c_str = str(c).lower()
            if 'sl' in c_str or 'stop' in c_str:
                return 'Stop Loss / Trailing Hit'
            elif 'tp' in c_str or 'take' in c_str:
                return 'Take Profit Hit'
            elif 'fleet' in c_str:
                return 'Fleet Close'
            elif 'close' in c_str or 'partial' in c_str:
                return 'Manual / Partial Close'
            else:
                return 'Other / Signal Exit'
        
        exit_deals['exit_type'] = exit_deals['comment'].apply(classify_comment)
        exit_type_stat = exit_deals.groupby('exit_type').agg(
            trades=('net_pnl', 'count'),
            total_net=('net_pnl', 'sum'),
            avg_pnl=('net_pnl', 'mean')
        )
        print(exit_type_stat.to_string())

        # Top 5 losses
        print(f"\n--- 4. TOP 5 LỆNH LỖ NẶNG NHẤT TUẦN ---")
        top_loss = exit_deals.sort_values(by='net_pnl', ascending=True).head(5)
        for _, r in top_loss.iterrows():
            print(f"Ticket #{r['ticket']} | {r['time_dt'].strftime('%Y-%m-%d %H:%M')} | {r['symbol']} | Net: ${r['net_pnl']:,.2f} USD | Comment: {r['comment']}")

        # Top 5 wins
        print(f"\n--- 5. TOP 5 LỆNH THẮNG ĐẬM NHẤT TUẦN ---")
        top_win = exit_deals.sort_values(by='net_pnl', ascending=False).head(5)
        for _, r in top_win.iterrows():
            print(f"Ticket #{r['ticket']} | {r['time_dt'].strftime('%Y-%m-%d %H:%M')} | {r['symbol']} | Net: ${r['net_pnl']:,.2f} USD | Comment: {r['comment']}")
else:
    print("Không có deal nào.")

# Open positions analysis
positions = mt5.positions_get()
print("\n" + "=" * 85)
print(f"📌 6. PHÂN TÍCH 17 VỊ THẾ ĐANG MỞ (FLOATING RISK & EXPOSURE)")
print("=" * 85)
if positions:
    df_p = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
    df_p['type_str'] = df_p['type'].apply(lambda x: 'BUY' if x == 0 else 'SELL')
    
    total_floating = df_p['profit'].sum()
    be_count = df_p[((df_p['type'] == 0) & (df_p['sl'] >= df_p['price_open'])) | ((df_p['type'] == 1) & (df_p['sl'] <= df_p['price_open']) & (df_p['sl'] > 0))].shape[0]
    no_sl_count = df_p[df_p['sl'] == 0].shape[0]
    
    print(f"Tổng số lệnh mở: {len(df_p)}")
    print(f"Tổng PnL thả nổi: ${total_floating:+,.2f} USD")
    print(f"Số lệnh đã khóa Lãi/Hòa vốn (SL bảo hiểm): {be_count} / {len(df_p)} lệnh")
    print(f"Số lệnh chưa có SL (Vi phạm Article 00 nếu có): {no_sl_count} / {len(df_p)} lệnh")
    
    # Detailed open positions table
    disp_cols = ['ticket', 'symbol', 'type_str', 'volume', 'price_open', 'price_current', 'sl', 'tp', 'profit', 'comment']
    print("\nChi tiết các vị thế mở:")
    print(df_p[disp_cols].to_string())

mt5.shutdown()
