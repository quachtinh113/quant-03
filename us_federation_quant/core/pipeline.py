"""Bản đồ điều phối MỘT TRANG: một vòng chạy của bot đọc từ trên xuống qua 6 tầng.

  L1 DATA -> L2 ALPHA -> L3 SIZING -> L4 RISK -> L5 EXECUTION -> L6 TELEMETRY
Pipeline chỉ NỐI các tầng (composition root); không chứa logic nghiệp vụ. Nghiệp vụ nằm ở `layers/l1..l6` và các phương thức mỏng
của USFederationQuantRuntime. Vòng `while _running` + xử lý lỗi + ngủ nằm ở runner; hàm này trả CycleResult(sleep_s).
golden: tests/test_golden_run_orchestration.py (thứ tự gọi) và tests/test_golden_scan_pipeline.py (vòng chậm / vào lệnh).
"""
import logging
import sys
import time

from us_federation_quant.layers.contracts import CycleResult
from us_federation_quant.layers.l5_execution import execute_directives

logger = logging.getLogger("USFederationQuant")


def run_one_cycle(rt, st, now_utc) -> CycleResult:
    """Một vòng: dữ liệu -> sổ drawdown -> vòng nhanh (3s) -> vòng chậm (60s). `st` là CycleState (đổi tại chỗ)."""
    # ── L1 DATA: kết nối + tài khoản ──
    if not rt.ensure_mt5_connected(max_retries=10, delay=15.0):
        return CycleResult(sleep_s=0.0)        # mất kết nối: thử lại ngay như `continue` cũ
    account_info = rt.mt5_mgr.get_account_info()
    if not account_info:
        return CycleResult(sleep_s=5.0)
    equity = float(account_info.get("equity", 10_000.0))
    balance = float(account_info.get("balance", 10_000.0))
    # ── L4 RỦI RO: sổ drawdown từ đỉnh vốn (HWM) ──
    hwm_state = rt.hwm.update(current_equity=equity, current_balance=balance)
    drawdown = hwm_state.drawdown_fraction
    floating_pnl = equity - balance
    # ── VÒNG NHANH (mỗi 3s): L4 RỦI RO quyết định -> L5 THỰC THI (qua chỉ thị) ──
    rt.update_symbol_exit_tracking(time.time())
    rt.enforce_weekend_hold_sweeper(now_utc)
    rt.enforce_gbpchf_uk100_hard_stop_cap(max_loss_usd=15.0)
    rt.enforce_forex_portfolio_hard_stop_cap(max_loss_usd=15.0)
    rt.enforce_index_hard_stop_cap(max_loss_usd=60.0)
    rt.enforce_xauusd_hard_stop_cap(max_loss_usd=75.0)
    try:
        rt.manage_multi_tier_profit_ladder()
    except Exception as e:
        logger.debug(f"Multi-Tier Profit Ladder Routine Error: {e}")
    rt.enforce_two_tier_exit_engine(min_partial_profit_usd=25.0)
    try:
        rt.ts_manager.update_trailing_stops()
    except Exception as e:
        logger.debug(f"Trailing Stop Routine Error: {e}")
    rt.mt5_mgr.enforce_mandatory_sl_protection(default_sl_pct=0.015)
    rt.reconcile_index_duplicate_derisking()
    positions = rt.mt5_mgr.get_positions()
    if rt.enforce_stagnation_exit(positions, now_utc):
        positions = rt.mt5_mgr.get_positions()
    if time.time() - st.last_quad_time >= 60.0:
        st.last_quad_time = time.time()
        # L4 RỦI RO: audit Quad-Titan -> kill switch (Nuclear Football) -> quét lợi nhuận về ví lạnh
        titan_audit = rt.quad_titans.execute_quad_audit(
            current_equity=equity,
            portfolio_drawdown=drawdown,
            current_weights=st.synthetic_weights,
            returns_history=st.returns_history,
        )
        if titan_audit.get("nuclear_football_triggered"):
            logger.critical("🚨 NUCLEAR FOOTBALL TRIGGERED! Initiating emergency federation liquidation...")
            rt.hub.central_risk_desk.kill_switch.manual_emergency_shutdown(
                reason=f"Drawdown ladder exceeded -12.0% federal boundary (Drawdown: {drawdown * 100:.2f}%)",
                broker_connector=rt.mt5_mgr,
                executor=lambda dirs: execute_directives(rt, dirs).captured,
            )
            rt.telemetry.broadcast_critical_alert(
                subject="NUCLEAR FOOTBALL ACTIVATED",
                body=f"Federation liquidated to preserve capital! Equity: ${equity:,.2f}",
            )
            sys.exit(99)
        try:
            from us_federation_quant.core.institutional_governance_rules import InstitutionalStatutoryRules
            swept, total_reserve = InstitutionalStatutoryRules.execute_blackrock_profit_sweep(current_equity=equity)
            if swept > 0:
                logger.info(f"🛡️ [LỆNH 4]: Đã quét ${swept:,.2f} USD vào ví lạnh Hamilton. Tổng dự trữ: ${total_reserve:,.2f} USD")
        except Exception as e:
            logger.warning(f"Vault sweep check notice: {e}")
        # L2 ALPHA -> L3 SIZING -> L4 chốt chặn/risk desk -> L5 THỰC THI (vào lệnh)
        rt.scan_and_route_state_proposals(account_equity=equity)
        # L6 TELEMETRY: nhịp tim, timeline, trạng thái
        latency = rt.heartbeat.measure_socket_latency()
        active_states = len([s for s in rt.hub.states_registry.states.values() if s.is_active])
        positions = rt.mt5_mgr.get_positions()
        rt.log_timeline_status(account_info, titan_audit, active_states, latency, hwm_state, positions)
        rt.heartbeat.beat(
            status="CONSTITUTIONAL_HEALTHY",
            symbol="FEDERATION_50",
            action="CYCLE_CHECK",
            pnl=floating_pnl,
            open_positions=len(positions),
        )
    return CycleResult(sleep_s=3.0)
