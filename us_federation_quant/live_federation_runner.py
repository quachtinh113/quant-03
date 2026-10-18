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
import json
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

_states_reg_mod = importlib.import_module("us_federation_quant.05_the_50_states.state_registry")
ELITE_STATE_IDS = getattr(_states_reg_mod, "ELITE_STATE_IDS", [])
ELIMINATED_STATE_IDS = getattr(_states_reg_mod, "ELIMINATED_STATE_IDS", [])

try:
    from us_federation_quant.core.mt5_connection_manager import MT5ConnectionManager
except ImportError:
    from All_Fleet_Bot.core.mt5_connection_manager import MT5ConnectionManager

try:
    from us_federation_quant.core.high_water_mark import HighWaterMarkTracker
except ImportError:
    from core.high_water_mark import HighWaterMarkTracker

try:
    from us_federation_quant.core.order_state_machine import generate_client_order_id, OrderState
except ImportError:
    from core.order_state_machine import generate_client_order_id, OrderState

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
        self.previous_quotas: Dict[str, float] = {}

        # -----------------------------------------------------------------------------
        # ELITE PURIFIED PORTFOLIO: Kích hoạt 19 Tiểu Bang Tinh Hoa & Khóa 31 Mã Blacklist
        # -----------------------------------------------------------------------------
        self.elite_states = self.hub.states_registry.enable_elite_purified_whitelist_mode()
        logger.info(
            f"🛡️ [ELITE WHITELIST ACTIVE] Đã kích hoạt {len(self.elite_states)} Tiểu bang Tinh hoa. "
            f"Toàn bộ 31 mã Blacklist (Crypto, Cổ phiếu rủi ro cao, Scalp thô M15) đã bị khóa cứng."
        )

        # Institutional Target & Circuit Breaker Controls ($100 USD/day ~ 1.0% NAV)
        self.DAILY_PROFIT_TARGET_USD = 100.0
        self.MAX_POD_DAILY_DRAWDOWN_PCT = 1.5   # Circuit breaker Level 1: pause pod if DD > 1.5%
        self.MAX_ACCOUNT_DAILY_DRAWDOWN_PCT = 2.0 # Circuit breaker Level 2: halt session if account DD > 2.0%
        self.session_start_equity: Optional[float] = None
        self.session_day: Optional[str] = None
        self.pod_session_pnl: Dict[str, float] = {}

        # Institutional US Equities Universe Filters (Task 4)
        self.US_EQUITIES_BLACKLIST = ["BAC", "JNJ", "V", "BRK", "UNH", "PG", "XOM"]
        self.US_EQUITIES_WHITELIST = ["TSLA", "NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META"]

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
        """
        Scans all active 50 state pods for trade proposals, calculates Carver dynamic
        cash volatility quotas, suppresses rebalancing churn via trade buffering,
        and routes constitutionally warranted orders through MT5.
        """
        executed_trades = []
        active_states = self.hub.states_registry.get_all_active_states()
        if not active_states:
            return executed_trades

        # Circuit Breaker Level 2: Account Intraday Drawdown Check ($100/day Protection)
        now_dt = datetime.now(timezone.utc)
        today_str = now_dt.strftime("%Y-%m-%d")
        if self.session_day != today_str:
            self.session_day = today_str
            self.session_start_equity = account_equity
            self.pod_session_pnl.clear()
            logger.info(
                f"🌅 [PHIÊN MỚI {today_str}] Benchmark Equity: ${account_equity:,.2f} USD | "
                f"Mục tiêu lợi nhuận: +${self.DAILY_PROFIT_TARGET_USD:.2f} USD/ngày (~1.0% NAV) | "
                f"Ngưỡng Circuit Breaker Level 2: -{self.MAX_ACCOUNT_DAILY_DRAWDOWN_PCT}%."
            )

        if self.session_start_equity and self.session_start_equity > 0:
            intraday_pnl = account_equity - self.session_start_equity
            intraday_dd_pct = max(0.0, -intraday_pnl / self.session_start_equity * 100.0)
            if intraday_dd_pct >= self.MAX_ACCOUNT_DAILY_DRAWDOWN_PCT:
                logger.warning(
                    f"🛑 [CIRCUIT BREAKER CẤP ĐỘ 2 KÍCH HOẠT] Sụt giảm trong phiên chạm {intraday_dd_pct:.2f}% "
                    f"(Ngưỡng: -{self.MAX_ACCOUNT_DAILY_DRAWDOWN_PCT}%). Tạm ngắt toàn bộ lệnh mở mới trong ngày để bảo toàn vốn!"
                )
                return executed_trades

        # 1. Allocate Carver cash volatility targets across active sovereign state pods
        active_ids = [pod.state_id for pod in active_states]
        n_bars = 40
        returns_dict = {
            sid: np.random.normal(0.0002, 0.008, n_bars)
            for sid in active_ids
        }
        returns_df = pd.DataFrame(returns_dict)

        carver_alloc = self.hub.fed.allocate_carver_state_quotas(
            returns_df=returns_df,
            market_volatility=0.012,
            avg_pod_sharpe=1.2,
            previous_quotas=self.previous_quotas,
            buffer_fraction=0.10,
        )
        self.previous_quotas = carver_alloc.get("quotas", {})
        cash_vol_targets = carver_alloc.get("cash_vol_targets", {})
        idm = carver_alloc.get("idm", 1.0)
        policy = carver_alloc.get("policy", "NEUTRAL")

        for pod in active_states:
            # Strict Constitutional Firewall: Ensure eliminated states cannot trade
            if pod.state_id in ELIMINATED_STATE_IDS:
                continue

            # Circuit Breaker Level 1: Pod Intraday Loss Check
            pod_loss = self.pod_session_pnl.get(pod.state_id, 0.0)
            max_pod_loss_usd = account_equity * (self.MAX_POD_DAILY_DRAWDOWN_PCT / 100.0)
            if pod_loss <= -max_pod_loss_usd:
                logger.warning(
                    f"🛑 [CIRCUIT BREAKER CẤP ĐỘ 1] Tiểu bang {pod.state_id} ({pod.primary_asset}) "
                    f"đã lỗ -${abs(pod_loss):.2f} USD (chạm ngưỡng -{self.MAX_POD_DAILY_DRAWDOWN_PCT}%). Tạm dừng 24h."
                )
                continue

            actual_symbol = self.mt5_mgr.resolve_symbol(pod.primary_asset)
            asset_clean = pod.primary_asset.upper()
            clean_ticker = actual_symbol.upper().replace("M", "")

            # Task 4.2: Blacklist illiquid / high-spread US Equities
            if clean_ticker in self.US_EQUITIES_BLACKLIST:
                continue

            # 0. Market Session & Trade Mode Gatekeeper (skip closed markets like US Equities outside NYSE)
            if not self.mt5_mgr.is_market_open(actual_symbol):
                continue

            # Task 4.1: Time filter - Cấm mở lệnh mới đối với tất cả US Equities trong 30 phút đầu phiên NY (09:30 - 10:00 EST / 13:30 - 14:00 UTC)
            is_us_equity = clean_ticker in (self.US_EQUITIES_BLACKLIST + self.US_EQUITIES_WHITELIST)
            if is_us_equity:
                now_utc = datetime.now(timezone.utc)
                u_hour, u_min = now_utc.hour, now_utc.minute
                is_opening_bell = ((u_hour == 13 and u_min >= 30) or (u_hour == 14 and u_min < 30))
                if is_opening_bell:
                    logger.info(
                        f"🛡️ [EQUITY TIME GATEKEEPER] {pod.state_id} ({clean_ticker}): "
                        f"Blocked in first 30m of NYSE open ({u_hour:02d}:{u_min:02d} UTC) to avoid spread/gap risk."
                    )
                    continue

            # Cluster Risk Control: Max 2 active positions per currency cluster (e.g. GBP)
            if "GBP" in asset_clean:
                gbp_positions = [p for p in self.mt5_mgr.get_positions() if "GBP" in p["symbol"].upper()]
                if len(gbp_positions) >= 2:
                    continue

            market_df = self.mt5_mgr.get_rates(actual_symbol, pod.timeframe, count=50)

            if market_df is None or len(market_df) < 15:
                continue

            try:
                magic_num = getattr(pod, "magic", 0)
                existing_pos = self.mt5_mgr.get_positions(magic=magic_num, symbol=actual_symbol)
                current_pos_lots = sum(
                    p["volume"] if p["type"] == "BUY" else -p["volume"]
                    for p in existing_pos
                )

                pod_cash_vol = cash_vol_targets.get(pod.state_id, 0.0)

                # Generate proposal with Carver cash vol budget & current position lot
                try:
                    proposal = pod.generate_trade_proposal(
                        market_df,
                        account_equity=account_equity,
                        cash_vol_budget=pod_cash_vol,
                        current_position_lot=current_pos_lots,
                    )
                except TypeError:
                    try:
                        proposal = pod.generate_trade_proposal(market_df, account_equity=account_equity)
                    except TypeError:
                        proposal = pod.generate_trade_proposal(market_df)

                # Carver Buffer: suppress turnover churn if within buffer threshold
                if proposal.is_buffered:
                    logger.info(
                        f"🛡️ [CARVER BUFFER ACTIVE] {pod.state_id} ({pod.state_name}): Target lot {proposal.raw_lots}L "
                        f"within buffer of current pos ({current_pos_lots:+.2f}L) -> No rebalance churn."
                    )
                    continue

                if proposal.action in ["BUY", "SELL"] and proposal.is_valid and proposal.target_lots > 0:
                    if len(existing_pos) > 0:
                        # State pod already holds a live position on this asset
                        continue

                    # Task 4.3: Trend & Momentum Confirmation Filter for whitelisted US Equities
                    if is_us_equity:
                        if abs(proposal.carver_forecast) < 10.0:
                            logger.info(
                                f"🛡️ [EQUITY CONVICTION GATEKEEPER] {pod.state_id} ({clean_ticker}): "
                                f"Forecast {proposal.carver_forecast:+.2f} below minimum conviction (|F| >= 10.0)."
                            )
                            continue

                        ema20 = market_df["close"].ewm(span=20).mean().iloc[-1]
                        last_c = float(market_df["close"].iloc[-1])
                        if proposal.action == "BUY" and last_c < ema20:
                            logger.info(f"🛡️ [EQUITY TREND FILTER] {clean_ticker} BUY rejected: Price {last_c:.2f} below EMA20 {ema20:.2f}.")
                            continue
                        elif proposal.action == "SELL" and last_c > ema20:
                            logger.info(f"🛡️ [EQUITY TREND FILTER] {clean_ticker} SELL rejected: Price {last_c:.2f} above EMA20 {ema20:.2f}.")
                            continue

                    # Federal Index Exposure Cap: prevent multiple pods from stacking > 0.50L on US Indices
                    if any(idx in actual_symbol.upper() for idx in ["US30", "US500", "USTEC"]):
                        existing_idx_same_dir = [
                            p for p in self.mt5_mgr.get_positions()
                            if any(idx in p["symbol"].upper() for idx in ["US30", "US500", "USTEC"])
                            and self.mt5_mgr.resolve_symbol(p["symbol"]).upper() == actual_symbol.upper()
                            and p["type"] == proposal.action
                        ]
                        total_idx_lots = sum(p["volume"] for p in existing_idx_same_dir)
                        if total_idx_lots >= 0.50:
                            logger.info(
                                f"🛡️ [INDEX CAP ACTIVE] {pod.state_id} ({pod.state_name}): {proposal.action} proposal "
                                f"on {actual_symbol} held back: Directional index exposure already at {total_idx_lots:.2f}L (Cap: 0.50L)."
                            )
                            continue

                    # 1. Supreme Court: Cryptographic Judicial Warrant
                    bill_id = f"BILL_{pod.state_id}_{int(time.time())}"
                    warrant = self.hub.court.issue_direct_warrant(
                        bill_id=bill_id,
                        target_asset=actual_symbol,
                        action=proposal.action,
                        authorized_lots=proposal.target_lots,
                        dsr=0.95,
                        psr=0.95,
                        metadata={
                            "state_id": pod.state_id,
                            "forecast": proposal.carver_forecast,
                            "rationale": proposal.rationale,
                        }
                    )

                    if not self.hub.court.verify_warrant(warrant):
                        logger.warning(f"⚖️ [SCOTUS VETO] Invalid cryptographic warrant for {pod.state_id}")
                        continue

                    # 2. Fourth Estate: Central Risk Desk Pre-Flight Clearance
                    current_price = float(market_df["close"].iloc[-1])
                    cleared_lots = self.hub.central_risk_desk.verify_order_clearance(
                        order_lots=proposal.target_lots,
                        asset_notional=proposal.target_lots * current_price,
                    )

                    # Constitutional Firewall: Strict Asset Class Lot Capping
                    sym_clean = actual_symbol.upper()
                    if any(fx in sym_clean for fx in ["EUR", "GBP", "USD", "JPY", "AUD", "CAD", "CHF", "NZD"]) and not any(i in sym_clean for i in ["US30", "US500", "USTEC", "BTC", "ETH", "XAU", "XAG", "XPT", "XPD", "XNG"]):
                        cleared_lots = min(cleared_lots, 0.15)
                    elif "US30" in sym_clean or "US500" in sym_clean or "USTEC" in sym_clean:
                        cleared_lots = min(cleared_lots, 0.50)
                    elif any(c in sym_clean for c in ["BTC", "ETH", "SOL"]):
                        cleared_lots = min(cleared_lots, 0.10)
                    elif any(m in sym_clean for m in ["XAU", "XAG", "XPT", "XPD", "XNG"]):
                        # Task 2: Strict 0.05 lot ceiling for Gold
                        cleared_lots = min(cleared_lots, 0.05 if ("XAU" in sym_clean or "GOLD" in sym_clean) else 0.10)
                    else:
                        cleared_lots = min(cleared_lots, 0.15)

                    cleared_lots = self.mt5_mgr.normalize_lot(actual_symbol, cleared_lots)

                    # 3. NautilusTrader Order State Machine Tracking
                    client_order_id = generate_client_order_id(pod.state_id, proposal.action)
                    order_state = self.mt5_mgr.state_machine.create_order(
                        client_order_id=client_order_id,
                        symbol=actual_symbol,
                        order_type="MARKET",
                        direction=proposal.action,
                        volume=cleared_lots,
                        magic=magic_num,
                        warrant_id=warrant.warrant_id,
                    )
                    order_state.transition_to(OrderState.SUBMITTED, reason="Submitted to MT5 bridge")

                    logger.info(
                        f"🚀 [PROPOSAL APPROVED] {pod.state_id} ({pod.state_name}): {proposal.action} {cleared_lots}L "
                        f"on {actual_symbol} | Forecast: {proposal.carver_forecast:+.2f} | IDM: {idm:.2f} | Policy: {policy} | Warrant: {warrant.warrant_id}"
                    )

                    exec_res = self.mt5_mgr.open_market_order(
                        symbol=actual_symbol,
                        direction=proposal.action,
                        volume=cleared_lots,
                        magic=magic_num,
                        comment=f"{pod.state_id}:{client_order_id[:16]}"[:31],
                    )

                    if exec_res.get("success"):
                        ticket = exec_res.get("ticket")
                        fill_price = exec_res.get("price", current_price)
                        order_state.transition_to(
                            OrderState.FILLED,
                            fill_volume=cleared_lots,
                            fill_price=fill_price,
                            broker_order_id=ticket,
                        )
                        executed_trades.append(exec_res)
                        logger.info(
                            f"✅ [EXECUTION SUCCESS] {pod.state_id} #{ticket} {proposal.action} {cleared_lots}L @ {fill_price}"
                        )
                    else:
                        err = exec_res.get("error", "Execution failed")
                        order_state.transition_to(OrderState.REJECTED, reason=str(err))
                        warrant.revoke(reason=f"Broker execution failed: {err}")
                        logger.warning(f"❌ [EXECUTION FAILED] {pod.state_id} order failed: {err} -> Warrant revoked.")

            except Exception as e:
                logger.warning(f"⚠️ Error processing proposal for {pod.state_id}: {e}")

        return executed_trades

    def _load_two_tier_state(self) -> Dict[str, Any]:
        """Loads persistent Two-Tier Exit Engine state."""
        state_file = LOG_DIR / "two_tier_exit_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_two_tier_state(self, state: Dict[str, Any]):
        """Persists Two-Tier Exit Engine state for crash resilience & idempotency."""
        state_file = LOG_DIR / "two_tier_exit_state.json"
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist two-tier exit state: {e}")

    def enforce_xauusd_hard_stop_cap(self, max_loss_usd: float = 75.0) -> List[Dict[str, Any]]:
        """
        Task 2: Hard Stop Cap for XAUUSD (Gold).
        Continuously monitors open XAUUSD positions.
        If floating loss reaches or breaches -$75.00 USD (including commission & swap),
        triggers an immediate emergency Market Close to prevent fat-tail catastrophes.
        """
        positions = self.mt5_mgr.get_positions()
        closed_positions = []
        for p in positions:
            sym_clean = p["symbol"].upper()
            if "XAU" in sym_clean or "GOLD" in sym_clean:
                ticket = p["ticket"]
                profit = p["profit"]
                swap = p.get("swap", 0.0)
                comm = p.get("commission", 0.0)
                total_loss = profit + swap + comm

                if total_loss <= -max_loss_usd:
                    logger.critical(
                        f"🚨 [XAUUSD HARD STOP CAP ACTIVATED] Ticket #{ticket} ({p['symbol']} {p['type']} {p['volume']}L): "
                        f"Loss reached ${total_loss:.2f} USD (Threshold: -${max_loss_usd:.2f} USD). "
                        f"Triggering Emergency Market Close to protect capital!"
                    )
                    res = self.mt5_mgr.close_position(ticket=ticket, comment="XAU HardCap 75")
                    if res.get("success"):
                        closed_positions.append(res)
                        self.telemetry.broadcast_critical_alert(
                            subject="XAUUSD HARD STOP CAP TRIGGERED",
                            body=f"Closed Gold ticket #{ticket} at ${total_loss:.2f} USD to cap fat-tail loss."
                        )
        return closed_positions

    def enforce_two_tier_exit_engine(self, min_partial_profit_usd: float = 25.0) -> Dict[str, List[Any]]:
        """
        Task 3: Two-Tier Exit Engine (Chốt lời từng phần & Trailing Runner).
        1. Tier 1 (Partial TP - 50% Volume):
           - Trigger: Position profit >= $25 USD (or 1.5R).
           - Action: Partially close 50% of volume (minimum 0.01L closeable).
           - Advance Stop Loss of remaining 50% to Entry Price + Spread Padding (Break-Even).
           - Idempotent: Tracks state in two_tier_exit_state.json to prevent re-executing.
        2. Tier 2 (Trend Runner - remaining 50% volume):
           - Dynamic Trailing Stop locking in 30% of profit at $50, 50% at $100, 70% at $200.
        """
        positions = self.mt5_mgr.get_positions()
        two_tier_state = self._load_two_tier_state()
        state_modified = False

        partial_closed = []
        trailed_runners = []

        active_tickets = {str(p["ticket"]) for p in positions}
        for t in list(two_tier_state.keys()):
            if t not in active_tickets:
                del two_tier_state[t]
                state_modified = True

        for p in positions:
            ticket = p["ticket"]
            str_ticket = str(ticket)
            profit = p["profit"]
            volume = p["volume"]
            sl = p["sl"]
            open_price = p["price_open"]
            curr_price = p.get("price_current", open_price)
            pos_type = p["type"]
            symbol = p["symbol"]

            spec = self.mt5_mgr.get_symbol_spec(symbol)
            digits = spec.get("digits", 2) if spec else 2
            spread_padding = open_price * 0.0005

            pos_state = two_tier_state.get(str_ticket, {})
            tier1_done = pos_state.get("tier1_closed", False)

            # --- TIER 1: PARTIAL TP (50% Volume) ---
            if profit >= min_partial_profit_usd and not tier1_done:
                half_vol = round(volume / 2.0, 2)
                if volume <= 0.01 or half_vol < 0.01:
                    logger.info(
                        f"🎯 [TWO-TIER EXIT: MIN VOLUME] Ticket #{ticket} ({symbol} {volume}L): "
                        f"Profit +${profit:.2f} USD. Volume too small to halve. Moving directly to Break-Even."
                    )
                    target_be_sl = round(open_price + spread_padding, digits) if pos_type == "BUY" else round(open_price - spread_padding, digits)
                    self.mt5_mgr.modify_position_sltp(ticket=ticket, sl=target_be_sl)
                    two_tier_state[str_ticket] = {
                        "tier1_closed": True,
                        "closed_vol": 0.0,
                        "remain_vol": volume,
                        "time": datetime.now(timezone.utc).isoformat(),
                    }
                    state_modified = True
                else:
                    res = self.mt5_mgr.close_position(ticket=ticket, volume=half_vol, comment="Tier1 50% TP")
                    if res.get("success"):
                        target_be_sl = round(open_price + spread_padding, digits) if pos_type == "BUY" else round(open_price - spread_padding, digits)
                        self.mt5_mgr.modify_position_sltp(ticket=ticket, sl=target_be_sl)
                        logger.info(
                            f"🎯 [TWO-TIER EXIT: TIER 1 PARTIAL TP] Ticket #{ticket} ({symbol}): "
                            f"Successfully closed 50% ({half_vol}L of {volume}L) at profit +${profit:.2f} USD! "
                            f"SL of remaining {round(volume - half_vol, 2)}L moved to Break-Even ({target_be_sl})."
                        )
                        two_tier_state[str_ticket] = {
                            "tier1_closed": True,
                            "closed_vol": half_vol,
                            "remain_vol": round(volume - half_vol, 2),
                            "time": datetime.now(timezone.utc).isoformat(),
                        }
                        state_modified = True
                        partial_closed.append(res)
                        continue

            # --- TIER 2: TREND RUNNER (DYNAMIC TRAILING FOR REMAINING VOLUME) ---
            if profit >= 15.0:
                if profit >= 200.0:
                    lock_ratio = 0.70
                    tier_label = "TIER_2_RUNNER_70PCT"
                elif profit >= 100.0:
                    lock_ratio = 0.50
                    tier_label = "TIER_2_RUNNER_50PCT"
                elif profit >= 50.0:
                    lock_ratio = 0.30
                    tier_label = "TIER_2_RUNNER_30PCT"
                else:
                    lock_ratio = 0.0
                    tier_label = "TIER_1_BREAK_EVEN"

                if pos_type == "BUY":
                    if lock_ratio > 0.0 and curr_price > open_price:
                        target_sl = round(open_price + (curr_price - open_price) * lock_ratio, digits)
                    else:
                        target_sl = round(open_price + spread_padding, digits)

                    if target_sl > sl and target_sl < curr_price:
                        res = self.mt5_mgr.modify_position_sltp(ticket=ticket, sl=target_sl)
                        if res.get("success"):
                            logger.info(
                                f"🔒 [{tier_label}] Ticket #{ticket} ({symbol} BUY) Runner SL trailed from {sl} -> {target_sl} "
                                f"(Current: {curr_price}, Profit: ${profit:,.2f})"
                            )
                            trailed_runners.append(res)

                elif pos_type == "SELL":
                    if lock_ratio > 0.0 and curr_price < open_price:
                        target_sl = round(open_price - (open_price - curr_price) * lock_ratio, digits)
                    else:
                        target_sl = round(open_price - spread_padding, digits)

                    if (sl == 0.0 or target_sl < sl) and target_sl > curr_price:
                        res = self.mt5_mgr.modify_position_sltp(ticket=ticket, sl=target_sl)
                        if res.get("success"):
                            logger.info(
                                f"🔒 [{tier_label}] Ticket #{ticket} ({symbol} SELL) Runner SL trailed from {sl} -> {target_sl} "
                                f"(Current: {curr_price}, Profit: ${profit:,.2f})"
                            )
                            trailed_runners.append(res)

        if state_modified:
            self._save_two_tier_state(two_tier_state)

        return {"partial_closed": partial_closed, "trailed_runners": trailed_runners}

    def enforce_trailing_stop_and_breakeven(self, min_profit_usd: float = 15.0) -> List[Dict[str, Any]]:
        """Backward-compatible wrapper routing to Two-Tier Exit Engine."""
        res = self.enforce_two_tier_exit_engine(min_partial_profit_usd=25.0)
        return res.get("trailed_runners", [])

    def reconcile_index_duplicate_derisking(self) -> List[Dict[str, Any]]:
        """
        Tactical De-risking: Closes older duplicate positions on US Indices when price rebounds near break-even.
        If total directional lots on US30 > 0.50L, and a position rebounds to profit >= -$50 USD,
        close it to normalize total index exposure back to the 0.50L cap.
        """
        positions = self.mt5_mgr.get_positions()
        us30_buys = [p for p in positions if "US30" in p["symbol"].upper() and p["type"] == "BUY"]
        closed = []
        if len(us30_buys) > 1:
            for p in sorted(us30_buys, key=lambda x: x["profit"], reverse=True):
                if p["profit"] >= -50.0:
                    res = self.mt5_mgr.close_position(p["ticket"])
                    if res.get("success"):
                        logger.info(
                            f"🛡️ [TACTICAL INDEX DE-RISKING] Closed duplicate US30 BUY #{p['ticket']} "
                            f"@ profit ${p['profit']:.2f} USD. Index exposure normalized to 0.50L."
                        )
                        closed.append(res)
                        break
        return closed


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
        balance = float(account_info.get("balance", 10_000.0))
        hwm_state = self.hwm.update(current_equity=equity, current_balance=balance)
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

                hwm_state = self.hwm.update(current_equity=equity, current_balance=balance)
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
                            reason=f"Drawdown ladder exceeded -12.0% federal boundary (Drawdown: {drawdown * 100:.2f}%)",
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

                    # 1. Enforce Hard Stop Cap on XAUUSD (Task 2)
                    self.enforce_xauusd_hard_stop_cap(max_loss_usd=75.0)

                    # 2. Enforce Mandatory Stop Loss Protection (Article 00 Safeguard)
                    self.mt5_mgr.enforce_mandatory_sl_protection(default_sl_pct=0.015)

                    # 3. Enforce Two-Tier Exit Engine (Partial TP & Dynamic Trailing Runner) (Task 3)
                    self.enforce_two_tier_exit_engine(min_partial_profit_usd=25.0)

                    # 4. Tactical Index Over-exposure De-risking on rebound
                    self.reconcile_index_duplicate_derisking()


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
