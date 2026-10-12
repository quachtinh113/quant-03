import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("us_federation_quant/logs/audit_50_states_models_shortlist.json", "r", encoding="utf-8") as f:
    data = json.load(f)["rankings"]

by_class = {}
for r in data:
    by_class.setdefault(r["asset_class"], []).append(r)

print("=" * 85)
print("TỔNG HỢP MODEL LỌT CHUẨN ĐỊNH LƯỢNG CHO 50 TIỂU BANG THEO TỪNG NHÓM TÀI SẢN EXNESS")
print("=" * 85)

for c, lst in by_class.items():
    print(f"\n[{c.upper()}] - {len(lst)} Tiểu bang:")
    for r in lst:
        print(f"  {r['rank']:2d}. {r['state_id']} ({r['asset_symbol']:<8}) => Model: {r['winning_model']:<34} | Sharpe: {r['sharpe_ratio']:<5.2f} | DSR: {r['dsr_p_value']:<6.4f} | Calmar: {r['calmar_ratio']:<5.1f} | DD: {r['max_drawdown_pct']:<4.1f}%")
