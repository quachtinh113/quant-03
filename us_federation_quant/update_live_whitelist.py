"""
========================================================================================
US FEDERATION QUANT — SCRIPT CẬP NHẬT CẤU HÌNH THỰC CHIẾN (ELITE WHITELIST LOADER)
Kích hoạt danh mục 19 Tiểu bang Tinh hoa và Khóa cứng 31 mã Blacklist cho Bot MT5.
========================================================================================
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_DIR = Path(__file__).resolve().parent
_WORKSPACE = _DIR.parent
for p in [str(_DIR), str(_WORKSPACE)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import importlib
_states_mod = importlib.import_module("us_federation_quant.05_the_50_states.state_registry")
StateFederationRegistry = _states_mod.StateFederationRegistry
ELITE_STATE_IDS = _states_mod.ELITE_STATE_IDS
ELIMINATED_STATE_IDS = _states_mod.ELIMINATED_STATE_IDS


def main():
    print("=" * 95)
    print(" 🦅 US FEDERATION QUANT — CẬP NHẬT CẤU HÌNH THỰC CHIẾN WHITELIST 19 TIỂU BANG")
    print("=" * 95)

    registry = StateFederationRegistry(elite_mode=True)
    active_states = registry.get_all_active_states()
    quarantined_states = [s for s in registry.states.values() if not s.is_active]

    print(f"\n[INFO] Đã nạp thành công {len(active_states)} / 50 Tiểu bang vào Whitelist thực chiến.")
    print(f"[INFO] Toàn bộ {len(quarantined_states)} mã Blacklist (Crypto, Cổ phiếu rủi ro, Scalp thô M15) đã bị khóa cứng.\n")

    print(f"{'No.':<4} {'State ID':<10} {'Symbol':<10} {'Asset Class':<16} {'Style / Timeframe':<32} {'Status'}")
    print("-" * 95)
    for idx, s in enumerate(active_states, 1):
        print(f"{idx:<4} {s.state_id:<10} {s.primary_asset:<10} {s.state_name[:15]:<16} {s.strategy_style[:22]} ({s.timeframe}){'':<4} {'✅ ACTIVE (ELITE)'}")

    print("-" * 95)
    print(f"\n🚫 DANH SÁCH 31 MÃ BỊ SA THẢI KHỎI HỆ THỐNG:")
    symbols_eliminated = [f"{s.state_id} ({s.primary_asset})" for s in quarantined_states]
    for i in range(0, len(symbols_eliminated), 4):
        print("   " + ", ".join(symbols_eliminated[i:i+4]))

    # Lưu file trạng thái cấu hình thực chiến
    config_file = _DIR / "logs" / "live_elite_whitelist_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "ELITE_WHITELIST_ACTIVE",
        "daily_profit_target_usd": 100.0,
        "max_pod_daily_drawdown_pct": 1.5,
        "max_account_daily_drawdown_pct": 2.0,
        "active_elite_count": len(active_states),
        "quarantined_count": len(quarantined_states),
        "elite_state_ids": [s.state_id for s in active_states],
        "eliminated_state_ids": [s.state_id for s in quarantined_states],
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Đã lưu cấu hình thực chiến -> {config_file}")
    print("🚀 Hệ thống đã sẵn sàng vận hành tự động theo mục tiêu $100 USD/ngày!")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    main()
