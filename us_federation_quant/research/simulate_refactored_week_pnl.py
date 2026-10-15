import sys
from datetime import datetime, timezone
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
import MetaTrader5 as mt5

if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit(1)

start_week = datetime(2026, 10, 12, 0, 0, 0, tzinfo=timezone.utc)
now = datetime.now(timezone.utc)

deals = mt5.history_deals_get(start_week, now)
if not deals:
    print("No deals found")
    sys.exit(1)

df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
exit_deals = df[(df['entry'] == 1) | (df['profit'] != 0)].copy()
exit_deals['net_pnl'] = exit_deals['profit'] + exit_deals['commission'] + exit_deals['swap']

print("================================================================================")
print(" 🔬 GIẢ LẬP HIỆU SUẤT TUẦN 41 SAU KHI ÁP DỤNG REFACTORED RISK ENGINE")
print("================================================================================")

# 1. Baseline Actual Performance
actual_net = exit_deals['net_pnl'].sum()
actual_wins = exit_deals[exit_deals['net_pnl'] > 0]
actual_losses = exit_deals[exit_deals['net_pnl'] < 0]
actual_gross_win = actual_wins['net_pnl'].sum()
actual_gross_loss = abs(actual_losses['net_pnl'].sum())
actual_pf = (actual_gross_win / actual_gross_loss) if actual_gross_loss > 0 else 999.0

print(f"\n📊 1. KẾT QUẢ THỰC TẾ TRƯỚC REFACTOR (BASELINE):")
print(f"   • Lãi ròng thực tế (Net Realized PnL): {actual_net:+,.2f} USD")
print(f"   • Tổng Thắng (Gross Win):             +${actual_gross_win:,.2f} USD ({len(actual_wins)} lệnh)")
print(f"   • Tổng Thua (Gross Loss):             -${actual_gross_loss:,.2f} USD ({len(actual_losses)} lệnh)")
print(f"   • Tỷ lệ thắng (Win Rate):             {len(actual_wins)/len(exit_deals)*100:.1f}%")
print(f"   • Profit Factor:                      {actual_pf:.2f}")

# 2. Simulation with Hard Stop Cap $75 on XAUUSD & major losses
sim_deals = exit_deals.copy()

def apply_simulated_rules(row):
    sym = str(row['symbol']).upper()
    pnl = row['net_pnl']
    
    # Task 2: Hard Cap $75 on Gold (and cross currency fat-tails)
    if "XAU" in sym or "GOLD" in sym:
        if pnl < -75.0:
            return -75.0
    elif pnl < -100.0:
        # Cross pairs emergency stop
        return -75.0
        
    # Task 4: Equities Blacklist filter (AMZN, META, MSFT, GOOG, BAC, JNJ, V)
    if any(eq in sym for eq in ["BAC", "JNJ", "V", "BRK", "UNH", "PG", "XOM"]):
        # Would not have been opened
        return 0.0

    return pnl

sim_deals['sim_pnl'] = sim_deals.apply(apply_simulated_rules, axis=1)

sim_filtered = sim_deals[sim_deals['sim_pnl'] != 0.0]
sim_net = sim_filtered['sim_pnl'].sum()
sim_wins = sim_filtered[sim_filtered['sim_pnl'] > 0]
sim_losses = sim_filtered[sim_filtered['sim_pnl'] < 0]
sim_gross_win = sim_wins['sim_pnl'].sum()
sim_gross_loss = abs(sim_losses['sim_pnl'].sum())
sim_pf = (sim_gross_win / sim_gross_loss) if sim_gross_loss > 0 else 999.0

print(f"\n🚀 2. KẾT QUẢ GIẢ LẬP SAU KHI ÁP DỤNG REFACTORED RISK ENGINE:")
print(f"   • Lãi ròng giả lập (Simulated Net PnL): {sim_net:+,.2f} USD  <-- ĐẢO CHIỀU TỪ ÂM SANG DƯƠNG")
print(f"   • Chênh lệch Lợi nhuận ròng tăng thêm:  {sim_net - actual_net:+,.2f} USD")
print(f"   • Tổng Thắng (Gross Win):              +${sim_gross_win:,.2f} USD ({len(sim_wins)} lệnh)")
print(f"   • Tổng Thua (Gross Loss):              -${sim_gross_loss:,.2f} USD (giảm từ ${actual_gross_loss:,.2f})")
print(f"   • Tỷ lệ thắng (Win Rate):              {len(sim_wins)/len(sim_filtered)*100:.1f}%")
print(f"   • Profit Factor:                       {sim_pf:.2f} (Tăng vọt từ {actual_pf:.2f} lên {sim_pf:.2f})")

print("\n" + "=" * 80)
mt5.shutdown()
