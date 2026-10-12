"""
========================================================================================
US FEDERATION QUANT — LIVE CONSTITUTIONAL MASTER RUNNER
Coordinates the 50 Sovereign States under the 4 Pillars of Global Quantitative Finance:
1. 🏛️ MIT: Gilbert Strang Nullspace & Andrew Lo Adaptive Markets VR(q).
2. ⚡ Wall Street: Pod Drawdown Ladder (-3%, -5%, -7.5%) & Zero Lookahead Bias.
3. 🌐 Ray Dalio: Bridgewater All-Weather Regime & Holy Grail Diversification (N_eff).
4. 🛡️ BlackRock: Alexander Hamilton Treasury (Ledoit-Wolf & 50% Profit Sweep to Reserve).

Governed by:
- 00 The Constitution: Inviolable Capital Protection.
- 01 Congress Alpha: Bicameral Legislative Deliberation.
- 02 Supreme Court: Blind OOS Trial & Judicial Warrant.
- 03 Executive Presidency: MT5 Router with Idempotency & Rate Limiting.
- 04 Federal Reserve: Dynamic QE/QT Policy Stance.
- 05 The 50 States: Dispersed Risk Pods (State 01 Gold, State 02 US30, State 05 BTC...).
- 06 The Fourth Estate: Central Risk Desk & Nuclear Football Kill-Switch.
========================================================================================
"""

from __future__ import annotations

import importlib
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Ensure root paths
_DIR = Path(__file__).resolve().parent
_WORKSPACE = _DIR.parent

for p in [str(_DIR), str(_WORKSPACE), str(_WORKSPACE / "All_Fleet_Bot"), str(_WORKSPACE / "ML_4_Bot")]:
    if p not in sys.path:
        sys.path.insert(0, p)

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Import Core Institutional Tools
try:
    from us_federation_quant.core.fleet_guard import FleetGuard, GuardConfig
    from us_federation_quant.core.fleet_telemetry import FleetHeartbeat, TelemetryNotifier
    from us_federation_quant.core.gemini_router import GeminiSmartRouter, TaskTier
except ImportError:
    try:
        from core.fleet_guard import FleetGuard, GuardConfig
        from core.fleet_telemetry import FleetHeartbeat, TelemetryNotifier
        from core.gemini_router import GeminiSmartRouter, TaskTier
    except ImportError:
        from bots._shared.fleet_guard import FleetGuard, GuardConfig
        from bots._shared.fleet_telemetry import FleetHeartbeat, TelemetryNotifier
        from bots._shared.gemini_router import GeminiSmartRouter, TaskTier

# Import Federation Components dynamically (handles numeric prefixes)
_hub_mod = importlib.import_module("us_federation_quant.federation_hub")
FederationHub = _hub_mod.FederationHub

_titan_mod = importlib.import_module("us_federation_quant.04_federal_reserve.quad_titan_engine")
QuadTitanEngine = _titan_mod.QuadTitanEngine

try:
    from us_federation_quant.core.mt5_connection_manager import MT5ConnectionManager
except ImportError:
    from All_Fleet_Bot.core.mt5_connection_manager import MT5ConnectionManager

try:
    from us_federation_quant.core.high_water_mark import HighWaterMarkTracker
except ImportError:
    from core.high_water_mark import HighWaterMarkTracker

# Setup Logging
LOG_DIR = _DIR / "logs"
try:
    from us_federation_quant.core.audit_logger import setup_logger
except ImportError:
    try:
        from core.audit_logger import setup_logger
    except ImportError:
        def setup_logger(log_dir):
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)-5s] %(message)s",
                handlers=[
                    logging.StreamHandler(sys.stdout),
                    logging.FileHandler(Path(log_dir) / "us_federation_quant.log", encoding="utf-8"),
                ],
            )
            return logging.getLogger("USFederationQuant")

logger = setup_logger(log_dir=str(LOG_DIR))

load_dotenv(_DIR / ".env")

_running = True


def handle_shutdown(signum, frame):
    global _running
    logger.info("🛑 Constitutional shutdown signal received. Halting US Federation Quant...")
    _running = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


class USFederationQuantRuntime:
    """Master Institutional Runtime coordinating Federation Hub, Quad-Titan Engine, and MT5."""

    def __init__(self, initial_capital_usd: float = 10_000.0):
        self.hub = FederationHub(secret_key="FEDERATION_SUPREME_SEAL")
        self.quad_titans = QuadTitanEngine(initial_capital_usd=initial_capital_usd)
        self.mt5_mgr = MT5ConnectionManager()
        self.guard = FleetGuard(GuardConfig(max_lot_cap=0.50, mandatory_sl=True))
        self.telemetry = TelemetryNotifier()
        self.heartbeat = FleetHeartbeat(bot_id="us_federation_quant", logs_dir=str(LOG_DIR))
        self.ai_router = GeminiSmartRouter(max_daily_usd=5.0)
        # Đỉnh vốn bền vững qua restart — nguồn duy nhất cho thang drawdown -3%/-5%/-7.5%.
        self.hwm = HighWaterMarkTracker(bot_id="us_federation_quant", logs_dir=str(LOG_DIR))

    def print_constitutional_dashboard(
        self,
        account_info: Dict[str, Any],
        titan_audit: Dict[str, Any],
        active_states_count: int,
        latency_ms: float,
        hwm_state=None,
    ):
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        regime = titan_audit["ray_dalio_macro"]["regime"]
        n_eff = titan_audit["ray_dalio_macro"]["holy_grail_n_eff"]
        reserve = titan_audit["blackrock_treasury"]["risk_free_reserve_usd"]
        is_neutral = titan_audit["mit_quantitative"]["is_strictly_factor_neutral"]
        vr_regime = titan_audit["mit_quantitative"]["lo_market_regime"]
        wall_st_status = titan_audit["wall_street_defense"]["pod_status"]

        lines = [
            "",
            "===================================================================================================",
            f" 🦅 HỢP CHÚNG QUỐC HOA KỲ QUANT (US FEDERATION QUANT) — 50 TIỂU BANG | {now_utc}",
            "===================================================================================================",
            f" 🏛️  Account: {account_info.get('login')} @ {account_info.get('server')} | "
            f"Balance: ${account_info.get('balance', 0):,.2f} | Equity: ${account_info.get('equity', 0):,.2f} | Ping: {latency_ms:.1f}ms",
            (f" 📉 Đỉnh vốn (High-Water Mark): ${hwm_state.high_water_mark_usd:,.2f} | "
             f"Drawdown thật từ đỉnh: {hwm_state.drawdown_pct:+.2f}% | "
             f"Lãi/lỗ trôi nổi: ${account_info.get('equity', 0) - account_info.get('balance', 0):+,.2f}"
             if hwm_state is not None else " 📉 High-Water Mark: chưa khởi tạo"),
            "---------------------------------------------------------------------------------------------------",
            " 👑 BỘ TỨ TRỤ ĐỊNH LƯỢNG (QUAD-TITAN QUANTITATIVE FOUNDATION):",
            f"  1. 🏛️ MIT Pillar:           Factor Orthogonal Nullspace: {'✅ 100% NEUTRAL' if is_neutral else '⚠️ LEAKAGE'} | Lo VR: {vr_regime}",
            f"  2. ⚡ Wall Street Pillar:    Pod Defense: {wall_st_status} | Drawdown: {titan_audit['wall_street_defense']['drawdown_pct']:.2f}%",
            f"  3. 🌐 Ray Dalio Pillar:      Macro Regime: {regime}",
            f"                             Holy Grail Chén Thánh: N_eff = {n_eff:.1f} Uncorrelated Bets ({titan_audit['ray_dalio_macro']['diversification_ratio']}%)",
            f"  4. 🛡️ BlackRock Pillar:     Hamilton Safety Reserve: ${reserve:,.2f} USD (Cashflow 50% Profit Swept)",
            "---------------------------------------------------------------------------------------------------",
            f" 🌐 FEDERATION POD STATUS:   {active_states_count} / 50 Sovereign States Active | "
            f"Nuclear Football: {'🚨 ĐÃ KÍCH HOẠT' if titan_audit.get('nuclear_football_triggered') else 'SAFE'}",
            "===================================================================================================",
            "",
        ]
        print("\n".join(lines), flush=True)

    def log_timeline_status(
        self,
        account_info: Dict[str, Any],
        titan_audit: Dict[str, Any],
        active_states_count: int,
        latency_ms: float,
        hwm_state=None,
        open_positions: Optional[List[Dict[str, Any]]] = None,
    ):
        regime = titan_audit["ray_dalio_macro"]["regime"]
        dd_pct = hwm_state.drawdown_pct if hwm_state is not None else 0.0
        hwm_val = hwm_state.high_water_mark_usd if hwm_state is not None else 0.0
        eq = account_info.get("equity", 0.0)
        bal = account_info.get("balance", 0.0)
        float_pnl = eq - bal
        pos_count = len(open_positions) if open_positions else 0

        logger.info(
            f"⏱️ [TIMELINE VÀO LỆNH] Equity: ${eq:,.2f} | HWM: ${hwm_val:,.2f} (DD: {dd_pct:+.2f}%) | "
            f"Lãi/Lỗ: ${float_pnl:+,.2f} | 50 States: {active_states_count}/50 Active | "
            f"Lệnh mở: {pos_count} | Macro: {regime} | Ping: {latency_ms:.1f}ms"
        )
        if open_positions:
            for p in open_positions:
                logger.info(
                    f"  📌 [POSITION] Ticket #{p['ticket']}: {p['symbol']} {p['type']} {p['volume']}L @ {p['price_open']} "
                    f"(Lãi trôi nổi: ${p['profit']:+,.2f} USD, SL={p['sl']}, TP={p['tp']})"
                )
        else:
            logger.info("  🔍 [TIMELINE SCAN] 50/50 Tiểu bang Sẵn sàng | Đang quét tín hiệu vào lệnh (XAUUSDm, US30, USDJPY, BTC...)")

    def scan_and_route_state_proposals(self, account_equity: float) -> List[Dict[str, Any]]:
        """Scans all active 50 state pods for trade proposals and routes approved orders to MT5."""
        executed_trades = []
        active_states = self.hub.states_registry.get_all_active_states()

        for pod in active_states:
            actual_symbol = self.mt5_mgr.resolve_symbol(pod.primary_asset)
            asset_clean = pod.primary_asset.upper()

            # Cluster Risk Control: Max 2 active positions per currency cluster (e.g. GBP)
            if "GBP" in asset_clean:
                gbp_positions = [p for p in self.mt5_mgr.get_positions() if "GBP" in p["symbol"].upper()]
                if len(gbp_positions) >= 2:
                    continue

            market_df = self.mt5_mgr.get_rates(actual_symbol, pod.timeframe, count=50)

            if market_df is None or len(market_df) < 15:
                continue

            try:
                try:
                    proposal = pod.generate_trade_proposal(market_df, account_equity=account_equity)
                except TypeError:
                    proposal = pod.generate_trade_proposal(market_df)

                if proposal.action in ["BUY", "SELL"] and proposal.is_valid:
                    magic_num = getattr(pod, "magic", 0)
                    existing_pos = self.mt5_mgr.get_positions(magic=magic_num, symbol=actual_symbol)

                    if len(existing_pos) == 0:
                        logger.info(
                            f"🚀 [PROPOSAL DETECTED] {pod.state_id} ({pod.state_name}): {proposal.action} {proposal.target_lots}L "
                            f"on {actual_symbol} | {proposal.rationale}"
                        )
                        exec_res = self.mt5_mgr.open_market_order(
                            symbol=actual_symbol,
                            direction=proposal.action,
                            volume=proposal.target_lots,
                            magic=magic_num,
                            comment=str(pod.state_id)[:31]
                        )
                        if exec_res.get("success"):
                            executed_trades.append(exec_res)
                            logger.info(
                                f"✅ [EXECUTION SUCCESS] {pod.state_id} #{exec_res.get('ticket')} {proposal.action} {proposal.target_lots}L @ {exec_res.get('price')}"
                            )
            except Exception as e:
                logger.warning(f"⚠️ Error processing proposal for {pod.state_id}: {e}")

        return executed_trades

    def enforce_trailing_stop_and_breakeven(self, min_profit_usd: float = 15.0) -> List[Dict[str, Any]]:
        """Automatically moves Stop Loss to Break-Even (+offset) when position profit >= min_profit_usd."""
        positions = self.mt5_mgr.get_positions()
        protected = []
        for p in positions:
            ticket = p["ticket"]
            profit = p["profit"]
            sl = p["sl"]
            open_price = p["price_open"]
            pos_type = p["type"]
            symbol = p["symbol"]

            if profit >= min_profit_usd:
                spec = self.mt5_mgr.get_symbol_spec(symbol)
                digits = spec.get("digits", 2) if spec else 2

                if pos_type == "BUY":
                    be_sl = round(open_price * 1.0005, digits)
                    if sl < open_price:
                        res = self.mt5_mgr.modify_position_sltp(ticket=ticket, sl=be_sl)
                        if res.get("success"):
                            logger.info(f"🔒 [AUTO BREAK-EVEN] Ticket #{ticket} ({symbol} BUY) SL moved to {be_sl} (Profit: ${profit:,.2f})")
                            protected.append(res)
                elif pos_type == "SELL":
                    be_sl = round(open_price * 0.9995, digits)
                    if sl == 0.0 or sl > open_price:
                        res = self.mt5_mgr.modify_position_sltp(ticket=ticket, sl=be_sl)
                        if res.get("success"):
                            logger.info(f"🔒 [AUTO BREAK-EVEN] Ticket #{ticket} ({symbol} SELL) SL moved to {be_sl} (Profit: ${profit:,.2f})")
                            protected.append(res)

        return protected


    def run(self):
        logger.info("================================================================================")
        logger.info("🦅 KÍCH HOẠT HỢP CHỦNG QUỐC HOA KỲ QUANT (TAM QUYỀN PHÂN LẬP & 50 TIỂU BANG)...")
        logger.info("================================================================================")

        # 1. Connect MT5
        self.mt5_mgr.connect()

        self.telemetry.send_discord(
            title="🦅 US Federation Quant Online",
            description="All 50 States & Quad-Titan Quantitative Foundation (MIT - Wall St - Dalio - BlackRock) Initialized.",
        )

        last_quad_time = 0.0
        synthetic_weights = np.array([0.20, 0.20, 0.20, 0.20, 0.20])
        returns_history = np.random.normal(0.0005, 0.01, (60, 5))

        # Initial Quad-Titan Audit & Startup Dashboard (CHỈ IN 1 LẦN DỰ ÁN BAN ĐẦU)
        account_info = self.mt5_mgr.get_account_info() or {}
        equity = float(account_info.get("equity", 10_000.0))
        hwm_state = self.hwm.update(current_equity=equity)
        drawdown = hwm_state.drawdown_fraction

        initial_audit = self.quad_titans.execute_quad_audit(
            current_equity=equity,
            portfolio_drawdown=drawdown,
            current_weights=synthetic_weights,
            returns_history=returns_history,
        )
        active_states = len([s for s in self.hub.states_registry.states.values() if s.is_active])
        latency = self.heartbeat.measure_socket_latency()

        # In Bảng điều khiển Hợp Chủng Quốc Hoa Kỳ Quant ĐÚNG 1 LẦN khi khởi động
        self.print_constitutional_dashboard(account_info, initial_audit, active_states, latency, hwm_state)

        logger.info("🏛️ Entering Constitutional Governance Loop (Continuous Timeline Scan)...")

        while _running:
            try:
                now_utc = datetime.now(timezone.utc)

                # MT5 Auto-Reconnect
                if not self.mt5_mgr.ensure_connected():
                    logger.warning("⏳ Reconnecting MT5 terminal...")
                    time.sleep(5)
                    continue

                account_info = self.mt5_mgr.get_account_info()
                if not account_info:
                    time.sleep(5)
                    continue

                equity = float(account_info.get("equity", 10_000.0))
                balance = float(account_info.get("balance", 10_000.0))

                hwm_state = self.hwm.update(current_equity=equity)
                drawdown = hwm_state.drawdown_fraction
                floating_pnl = equity - balance

                # Quad-Titan Audit & Timeline Log & State Proposals Scan (every 60s)
                if time.time() - last_quad_time >= 60.0:
                    last_quad_time = time.time()
                    titan_audit = self.quad_titans.execute_quad_audit(
                        current_equity=equity,
                        portfolio_drawdown=drawdown,
                        current_weights=synthetic_weights,
                        returns_history=returns_history,
                    )

                    # Check Nuclear Kill-Switch
                    if titan_audit.get("nuclear_football_triggered"):
                        logger.critical("🚨 NUCLEAR FOOTBALL TRIGGERED! Initiating emergency federation liquidation...")
                        self.hub.central_risk_desk.kill_switch.manual_emergency_shutdown(
                            reason=f"Drawdown ladder exceeded -7.5% federal boundary (Drawdown: {drawdown * 100:.2f}%)",
                            broker_connector=self.mt5_mgr,
                        )
                        self.telemetry.broadcast_critical_alert(
                            subject="NUCLEAR FOOTBALL ACTIVATED",
                            body=f"Federation liquidated to preserve capital! Equity: ${equity:,.2f}",
                        )
                        break

                    # LỆNH 4: BlackRock Aladdin 50% Profit Sweep into Hamilton Vault
                    try:
                        from us_federation_quant.institutional_governance_rules import InstitutionalStatutoryRules
                        swept, total_reserve = InstitutionalStatutoryRules.execute_blackrock_profit_sweep(current_equity=equity)
                        if swept > 0:
                            logger.info(f"🛡️ [LỆNH 4]: Đã quét ${swept:,.2f} USD vào ví lạnh Hamilton. Tổng dự trữ: ${total_reserve:,.2f} USD")
                    except Exception as e:
                        logger.warning(f"Vault sweep check notice: {e}")

                    # Scan & Execute 50 State Pod Proposals
                    self.scan_and_route_state_proposals(account_equity=equity)

                    latency = self.heartbeat.measure_socket_latency()
                    active_states = len([s for s in self.hub.states_registry.states.values() if s.is_active])

                    # 1. Enforce Mandatory Stop Loss Protection (Article 00 Safeguard)
                    self.mt5_mgr.enforce_mandatory_sl_protection(default_sl_pct=0.015)

                    # 2. Enforce Auto Break-Even Lock on profitable positions (+$15 USD)
                    self.enforce_trailing_stop_and_breakeven(min_profit_usd=15.0)


                    positions = self.mt5_mgr.get_positions()

                    # In log Timeline Vào Lệnh đơn thay vì lặp lại bảng điều khiển 2-3-4-5 lần
                    self.log_timeline_status(account_info, titan_audit, active_states, latency, hwm_state, positions)

                    self.heartbeat.beat(
                        status="CONSTITUTIONAL_HEALTHY",
                        symbol="FEDERATION_50",
                        action="CYCLE_CHECK",
                        pnl=floating_pnl,
                        open_positions=len(positions),
                    )

                time.sleep(15)


            except Exception as e:
                logger.error(f"⚠️ Unhandled error in Constitutional Loop: {e}", exc_info=True)
                time.sleep(5)

        # Shutdown
        logger.info("🔌 Shutting down US Federation Quant...")
        self.mt5_mgr.shutdown()
        self.telemetry.send_discord(title="🛑 US Federation Quant Offline", description="All pods safely parked.")
        logger.info("👋 Federation engine shut down cleanly. Long live the Republic!")


if __name__ == "__main__":
    runner = USFederationQuantRuntime()
    runner.run()
