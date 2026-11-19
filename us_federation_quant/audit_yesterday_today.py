import json
import os
from datetime import datetime, timezone
import pandas as pd

CACHE_FILE = r"c:\Quant_03\us_federation_quant\logs\weekly_mt5_deals_cache.json"

with open(CACHE_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

deals = data.get("deals", [])
df = pd.DataFrame(deals)
df["dt_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
df["dt_ict"] = df["dt_utc"].dt.tz_convert("Asia/Ho_Chi_Minh")
df["date_utc"] = df["dt_utc"].dt.strftime("%Y-%m-%d")
df["date_ict"] = df["dt_ict"].dt.strftime("%Y-%m-%d")
df["net_pnl"] = df["profit"] + df["commission"] + df["swap"]

# Pair entry deals (entry==0) with exit deals (entry==1) by position_id
entries = df[df["entry"] == 0].set_index("position_id")
exits = df[df["entry"] == 1].copy()

trades = []
for idx, exit_row in exits.iterrows():
    pos_id = exit_row["position_id"]
    entry_row = entries.loc[pos_id] if pos_id in entries.index else None
    
    if entry_row is not None and isinstance(entry_row, pd.DataFrame):
        entry_row = entry_row.iloc[0]
        
    entry_comment = entry_row["comment"] if entry_row is not None else ""
    entry_time = entry_row["dt_ict"] if entry_row is not None else None
    exit_time = exit_row["dt_ict"]
    
    holding_hours = (exit_row["time"] - entry_row["time"]) / 3600.0 if entry_row is not None else 0.0
    
    # State identification
    state = "UNKNOWN"
    if "STATE_" in str(entry_comment):
        state = entry_comment.split(":")[0] if ":" in entry_comment else entry_comment
    elif "STATE_" in str(exit_row["comment"]):
        state = exit_row["comment"].split(":")[0] if ":" in exit_row["comment"] else exit_row["comment"]
        
    trades.append({
        "position_id": pos_id,
        "symbol": exit_row["symbol"],
        "state": state,
        "entry_comment": entry_comment,
        "exit_comment": exit_row["comment"],
        "volume": exit_row["volume"],
        "entry_price": entry_row["price"] if entry_row is not None else 0.0,
        "exit_price": exit_row["price"],
        "profit": exit_row["profit"],
        "swap": exit_row["swap"],
        "commission": exit_row["commission"],
        "net_pnl": exit_row["net_pnl"],
        "holding_hours": holding_hours,
        "entry_time_ict": str(entry_time),
        "exit_time_ict": str(exit_time),
        "date_ict": exit_row["date_ict"],
        "date_utc": exit_row["date_utc"],
    })

tdf = pd.DataFrame(trades)

print("=" * 90)
print("CHI TIẾT PNL & LỆNH ĐÓNG THEO NGÀY (GIỜ VIỆT NAM - ICT)")
print("=" * 90)

for d, grp in tdf.groupby("date_ict"):
    wins = grp[grp["net_pnl"] > 0]
    losses = grp[grp["net_pnl"] < 0]
    be = grp[grp["net_pnl"] == 0]
    gross_win = wins["net_pnl"].sum()
    gross_loss = losses["net_pnl"].sum()
    net = grp["net_pnl"].sum()
    wr = len(wins) / len(grp) * 100 if len(grp) > 0 else 0
    pf = abs(gross_win / gross_loss) if gross_loss != 0 else 999.0
    print(f"\n📅 NGÀY: {d} ICT")
    print(f"   Tổng số lệnh: {len(grp)} | Win: {len(wins)} | Loss: {len(losses)} | BE: {len(be)} | Win Rate: {wr:.1f}%")
    print(f"   Gross Win: +${gross_win:,.2f} | Gross Loss: -${abs(gross_loss):,.2f} | Net PnL: ${net:+,.2f} | PF: {pf:.2f}")

print("\n" + "=" * 90)
print("DANH SÁCH TOÀN BỘ LỆNH ĐÓNG NGÀY HÔM QUA (18/11) & HÔM NAY (19/11)")
print("=" * 90)

recent = tdf[tdf["date_ict"].isin(["2026-11-18", "2026-11-19"])].sort_values(by="exit_time_ict")
for idx, r in recent.iterrows():
    pnl_str = f"+${r['net_pnl']:.2f}" if r['net_pnl'] > 0 else f"-${abs(r['net_pnl']):.2f}"
    status = "WIN " if r['net_pnl'] > 0 else ("LOSS" if r['net_pnl'] < 0 else "BE  ")
    print(f"[{status}] {r['exit_time_ict'][:19]} | {r['symbol']:<7} | Vol:{r['volume']:.2f} | PnL:{pnl_str:>8} | State:{r['state']:<10} | Hold:{r['holding_hours']:.1f}h | In:{r['entry_comment'][:25]} | Out:{r['exit_comment']}")

# Save detailed table to json for analysis
recent.to_json(r"c:\Quant_03\us_federation_quant\logs\recent_analysis_18_19.json", orient="records", indent=2)
