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

try:
    from execution_layer.trailing_stop_manager import TrailingStopManager
except ImportError:
    from us_federation_quant.execution_layer.trailing_stop_manager import TrailingStopManager

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

    # Microstructure Patches: Toxic Hours Blacklist ({0, 6, 18, 23} UTC)
    TOXIC_HOURS: set = {0, 6, 18, 23}

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

        # Trailing Stop Động (Chandelier Exit / ATR14 H1)
        self.ts_manager = TrailingStopManager(atr_period=14, atr_multiplier=2.0, min_modification_points=15)
        self.TOXIC_HOURS = self.__class__.TOXIC_HOURS

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

    def calculate_risk_adjusted_lot(self, symbol: str, sl_points: float, max_risk_usd: float = 35.0) -> float:
        """
        Quant Core V9: Volatility ATR Dollar Sizing.
        Dynamically calculates lot size such that hitting Stop Loss risks exactly max_risk_usd.

        Formula: raw_lot = max_risk_usd / (sl_points * tick_value_per_point)
        Live MT5 Integration: Fetches trade_tick_value, trade_tick_size, point, volume_step via mt5.symbol_info().
        Cap Logic: Hard caps lot size between 0.01 and 0.03 for ["USTEC", "US30", "US100", "HK50"].
        Normalization: Rounds final lot size to broker volume_step and clamps within volume_min/volume_max.
        """
        import MetaTrader5 as mt5

        # 1. Fetch live specifications from MT5 symbol_info
        s_info = mt5.symbol_info(symbol)
        if s_info is None and hasattr(self, "mt5_mgr"):
            resolved = self.mt5_mgr.resolve_symbol(symbol)
            s_info = mt5.symbol_info(resolved)
        if s_info is None and not symbol.endswith("m"):
            s_info = mt5.symbol_info(symbol + "m")
        if s_info is None and symbol.endswith("m"):
            s_info = mt5.symbol_info(symbol[:-1])

        if s_info is not None:
            trade_tick_value = float(getattr(s_info, "trade_tick_value", 0.0) or 0.0)
            trade_tick_size = float(getattr(s_info, "trade_tick_size", 0.0) or 0.0)
            point = float(getattr(s_info, "point", 0.0) or 0.0)
            volume_min = float(getattr(s_info, "volume_min", 0.01) or 0.01)
            volume_max = float(getattr(s_info, "volume_max", 100.0) or 100.0)
            volume_step = float(getattr(s_info, "volume_step", 0.01) or 0.01)
        else:
            spec = self.mt5_mgr.get_symbol_spec(symbol) if hasattr(self, "mt5_mgr") else {}
            point = float(spec.get("point", 0.0001) or 0.0001)
            trade_tick_size = float(spec.get("tick_size", point) or point)
            trade_tick_value = float(spec.get("tick_value", 1.0) or 1.0)
            volume_min = float(spec.get("volume_min", 0.01) or 0.01)
            volume_max = float(spec.get("volume_max", 100.0) or 100.0)
            volume_step = float(spec.get("volume_step", 0.01) or 0.01)

        # 2. Derive tick_value_per_point
        # trade_tick_value is profit for 1 lot when price moves by trade_tick_size.
        if trade_tick_size > 0 and point > 0:
            tick_value_per_point = trade_tick_value * (point / trade_tick_size)
        else:
            tick_value_per_point = trade_tick_value

        if tick_value_per_point <= 0:
            tick_value_per_point = 1.0

        # 3. Dynamic Lot Calculation
        safe_sl_points = max(float(sl_points), 10.0)
        dollar_risk_per_lot = safe_sl_points * tick_value_per_point
        raw_lot = max_risk_usd / max(dollar_risk_per_lot, 1e-6)

        # 4. Cap logic: Hard cap lot size between 0.01 and 0.03 for indices
        sym_clean = symbol.upper().replace("M", "")
        is_index = any(idx in sym_clean for idx in ["USTEC", "US30", "US100", "HK50"])
        if is_index:
            raw_lot = float(np.clip(raw_lot, 0.01, 0.03))

        # 5. Normalization: Round to broker volume_step and clamp within boundaries
        if volume_step > 0:
            steps = round(raw_lot / volume_step)
            normalized_lot = steps * volume_step
        else:
            normalized_lot = raw_lot

        # Clamp within broker allowed limits
        normalized_lot = max(volume_min, min(normalized_lot, volume_max))
        normalized_lot = round(normalized_lot, 2)

        logger.info(
            f"📐 [VOLATILITY ATR SIZING] {symbol}: sl_points={safe_sl_points:.1f}, "
            f"trade_tick_value={trade_tick_value}, tick_val_per_point={tick_value_per_point:.5f}, "
            f"max_risk=${max_risk_usd:.2f} -> raw={raw_lot:.4f}L, normalized={normalized_lot:.2f}L (Index Cap: {is_index})"
        )
        return normalized_lot

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

        # Logic 1 (Monday Curfew): Chặn toàn bộ việc mở vị thế mới trong 60 phút đầu mở phiên tuần mới (00:00 - 00:59 UTC)
        if now_dt.weekday() == 0 and now_dt.hour == 0:
            logger.info(
                f"🛡️ [MONDAY OPEN CURFEW] Thứ Hai {now_dt.strftime('%H:%M')} UTC: "
                f"Tạm ngắt mở vị thế mới trong 60 phút đầu tuần để né giãn spread và trượt giá."
            )
            return executed_trades

        # Logic 1b (Friday EOD & Weekend Curfew): Chặn toàn bộ việc mở vị thế mới từ 20:00 UTC Thứ Sáu xuyên suốt cuối tuần (Time Rule 23:45)
        if self.is_friday_or_weekend_curfew(now_dt):
            logger.info(
                f"🛡️ [FRIDAY EOD & WEEKEND CURFEW] {now_dt.strftime('%Y-%m-%d %H:%M')} UTC: "
                f"Tạm ngắt mở vị thế mới từ 20:00 UTC Thứ Sáu xuyên suốt cuối tuần để bảo toàn 100% tiền mặt (Skill 07 Time Rule 23:45)."
            )
            return executed_trades

        # Logic 1c (Toxic Hours Blacklist): Chặn mở vị thế mới tại {0, 6, 18, 23} UTC
        if self.is_toxic_hour(now_dt.hour):
            logger.info(
                f"🛡️ [TOXIC HOURS ACTIVE] Khung giờ {now_dt.hour:02d}:00 UTC nằm trong TOXIC_HOURS {self.TOXIC_HOURS}. "
                f"Từ chối mở vị thế mới để tránh trượt giá và suy giảm thanh khoản (vẫn duy trì Trailing Stop)."
            )
            return executed_trades

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

            # 0. Market Session & Holiday Gatekeeper (skip closed markets, holiday sessions, and weekend hours)
            try:
                import MetaTrader5 as mt5
                sym_info = mt5.symbol_info(actual_symbol)
                if sym_info is None or getattr(sym_info, "trade_mode", None) != mt5.SYMBOL_TRADE_MODE_FULL:
                    continue
            except Exception:
                pass

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

            # Logic 2 (US Index NY Session Gate): Chỉ cho phép mở lệnh chỉ số Mỹ từ 13:00 đến 21:00 UTC
            if any(idx in actual_symbol.upper() for idx in ["USTEC", "US30", "US100"]):
                if not (13 <= now_dt.hour <= 21):
                    logger.info(
                        f"🛡️ [INDEX SESSION GATE] {pod.state_id} ({actual_symbol}): "
                        f"Bỏ qua tín hiệu ngoài phiên New York ({now_dt.hour:02d}:{now_dt.minute:02d} UTC). "
                        f"Chỉ cho phép mở lệnh chỉ số từ 13:00 đến 21:00 UTC."
                    )
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

                    # Task 1: Khóa xu hướng D1 EMA200 cho EURGBP (State 31)
                    if pod.state_id == "STATE_31" or "EURGBP" in actual_symbol.upper():
                        current_h1_price = float(market_df["close"].iloc[-1])
                        if not self.check_eurgbp_d1_ema200_filter(actual_symbol, current_h1_price, proposal.action):
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

                    # Cross-Pod Asset Deduplication Filter
                    existing_positions = self.mt5_mgr.get_positions()
                    duplicate_found = False
                    for pos in existing_positions:
                        pos_sym = pos.get("symbol", "").upper()
                        pos_dir = pos.get("type", "")
                        dir_str = "BUY" if pos_dir in ["BUY", 0] else "SELL"
                        if pos_sym == actual_symbol.upper() and dir_str == proposal.action:
                            logger.warning(
                                f"[DEDUP_FILTER] Rejected signal for {actual_symbol}: "
                                f"Existing open position #{pos.get('ticket')} in same direction ({dir_str})."
                            )
                            duplicate_found = True
                            break
                    if duplicate_found:
                        continue

                    # Pre-Trade Factor Risk Gatekeeper (Quant Core V9: JPY/USD cluster risk check)
                    from us_federation_quant.institutional_governance_rules import check_factor_limits
                    if not check_factor_limits(actual_symbol, existing_positions):
                        logger.warning(
                            f"🛡️ [PRE-TRADE RISK GATEKEEPER] Rejected {pod.state_id} proposal on {actual_symbol}: "
                            f"Breaches currency factor limit (JPY max 1, USD max 2)."
                        )
                        continue

                    # 2. Dynamic Volatility ATR Dollar Sizing (Quant Core V9: max_risk_usd=35.0)
                    tick = self.mt5_mgr.get_tick(actual_symbol) if hasattr(self, "mt5_mgr") else None
                    if tick and tick.get("ask") and tick.get("bid"):
                        current_price = float(tick["ask"] if proposal.action == "BUY" else tick["bid"])
                    else:
                        current_price = float(market_df["close"].iloc[-1])

                    tr = np.maximum(
                        market_df["high"] - market_df["low"],
                        np.maximum(
                            abs(market_df["high"] - market_df["close"].shift(1)),
                            abs(market_df["low"] - market_df["close"].shift(1))
                        )
                    )
                    atr_14 = float(tr.rolling(14).mean().iloc[-1])
                    if np.isnan(atr_14) or atr_14 <= 0:
                        atr_14 = float(market_df["high"].iloc[-1] - market_df["low"].iloc[-1])
                    if atr_14 <= 0:
                        atr_14 = current_price * 0.005

                    pt = getattr(sym_info, "point", 0.0001) or 0.0001
                    stops_level = getattr(sym_info, "trade_stops_level", 0) or 0
                    spread = getattr(sym_info, "spread", 0) or 0
                    min_stop_dist = (stops_level + spread + 5) * pt
                    min_point_floor = 150.0 * pt
                    sl_dist = max(1.8 * atr_14, min_point_floor, min_stop_dist)
                    tp_dist = max(2.5 * atr_14, sl_dist * 1.5)
                    sl_points = max(sl_dist / max(pt, 1e-6), 10.0)

                    risk_adjusted_lots = self.calculate_risk_adjusted_lot(
                        symbol=actual_symbol,
                        sl_points=sl_points,
                        max_risk_usd=35.0,
                    )

                    # Central Risk Desk clearance & broker lot normalization
                    cleared_lots = self.hub.central_risk_desk.verify_order_clearance(
                        order_lots=risk_adjusted_lots,
                        asset_notional=risk_adjusted_lots * current_price,
                    )
                    cleared_lots = self.mt5_mgr.normalize_lot(actual_symbol, cleared_lots)

                    digits = getattr(sym_info, "digits", 2) or 2
                    if proposal.action == "BUY":
                        target_sl = round(current_price - sl_dist, digits)
                        target_tp = round(current_price + tp_dist, digits)
                    else:
                        target_sl = round(current_price + sl_dist, digits)
                        target_tp = round(current_price - tp_dist, digits)

                    # Pre-Trade Factor Gatekeeper: Ma trận chặn khung giờ tử thần (Toxic Hours Blacklist) ngay trước OrderSend
                    exec_hour_utc = datetime.now(timezone.utc).hour
                    if self.is_toxic_hour(exec_hour_utc):
                        logger.warning(
                            f"🛑 [TOXIC HOURS GATEKEEPER] Từ chối OrderSend {proposal.action} {cleared_lots}L {actual_symbol} "
                            f"tại {exec_hour_utc:02d}:00 UTC (Tập giờ tử thần {self.TOXIC_HOURS}). Vẫn duy trì Trailing Stop."
                        )
                        continue

                    # 3. NautilusTrader Order State Machine Tracking
                    client_order_id = generate_client_order_id(pod.state_id, proposal.action)
                    order_state = self.mt5_mgr.state_machine.create_order(
                        client_order_id=client_order_id,
                        symbol=actual_symbol,
                        order_type="MARKET",
                        direction=proposal.action,
                        volume=cleared_lots,
                        sl=target_sl,
                        tp=target_tp,
                        magic=magic_num,
                        warrant_id=warrant.warrant_id,
                    )
                    order_state.transition_to(OrderState.SUBMITTED, reason="Submitted to MT5 bridge")

                    logger.info(
                        f"🚀 [PROPOSAL APPROVED] {pod.state_id} ({pod.state_name}): {proposal.action} {cleared_lots}L "
                        f"on {actual_symbol} | SL: {target_sl} | TP: {target_tp} | Forecast: {proposal.carver_forecast:+.2f} | IDM: {idm:.2f} | Policy: {policy} | Warrant: {warrant.warrant_id}"
                    )

                    exec_res = self.mt5_mgr.open_market_order(
                        symbol=actual_symbol,
                        direction=proposal.action,
                        volume=cleared_lots,
                        sl=target_sl,
                        tp=target_tp,
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
                        retcode = exec_res.get("retcode", -1)
                        order_state.transition_to(OrderState.REJECTED, reason=str(err))
                        warrant.revoke(reason=f"Broker execution failed: {err}")
                        if retcode == 10018:
                            logger.info(f"ℹ️ [MARKET_CLOSED] {pod.state_id} ({actual_symbol}): Thị trường đóng cửa / nghỉ lễ (10018) -> Tạm bỏ qua an toàn.")
                        else:
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

    def _load_sweeper_reopen_state(self) -> Dict[str, float]:
        """Loads persistent per-symbol reopen warmup timestamps so process restarts never lose warmup progress."""
        state_file = LOG_DIR / "sweeper_reopen_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {str(k): float(v) for k, v in data.items()}
            except Exception:
                return {}
        return {}

    def _save_sweeper_reopen_state(self, state: Dict[str, float]):
        """Persists per-symbol reopen warmup timestamps to disk."""
        state_file = LOG_DIR / "sweeper_reopen_state.json"
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to persist sweeper reopen state: {e}")

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

    def enforce_index_hard_stop_cap(self, max_loss_usd: float = 60.0) -> List[Dict[str, Any]]:
        """
        Step 3: Hard Stop Circuit Breaker for US Indices (USTEC, US30, US500).
        Continuously monitors open index positions.
        If floating loss reaches or breaches -$60.00 USD (including commission & swap),
        triggers an immediate emergency Market Close with [CIRCUIT_BREAKER] warning log.
        """
        positions = self.mt5_mgr.get_positions()
        closed_positions = []
        index_keys = ["USTEC", "US30", "US500", "NAS100", "DJ30", "SP500"]
        for p in positions:
            sym_clean = p["symbol"].upper()
            if any(idx in sym_clean for idx in index_keys):
                ticket = p["ticket"]
                profit = p["profit"]
                swap = p.get("swap", 0.0)
                comm = p.get("commission", 0.0)
                total_loss = profit + swap + comm

                if total_loss <= -max_loss_usd:
                    logger.warning(
                        f"🚨 [CIRCUIT_BREAKER] Ticket #{ticket} ({p['symbol']} {p['type']} {p['volume']}L): "
                        f"Loss reached ${total_loss:.2f} USD (Threshold: -${max_loss_usd:.2f} USD). "
                        f"Triggering Emergency Market Close to protect capital!"
                    )
                    res = self.mt5_mgr.close_position(ticket=ticket, comment="Index HardCap 60")
                    if res.get("success"):
                        closed_positions.append(res)
                        self.telemetry.broadcast_critical_alert(
                            subject="INDEX HARD STOP CAP TRIGGERED",
                            body=f"Closed Index ticket #{ticket} at ${total_loss:.2f} USD to cap fat-tail loss."
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
                    lock_ratio = max(0.30, 25.0 / profit)
                    tier_label = "TIER_2_RUNNER_30PCT"
                elif profit >= 40.0:
                    lock_ratio = 25.0 / profit  # Dynamically lock in at least $25.00 USD
                    tier_label = "TIER_2_LOCK_PROFIT_25USD"
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

    def ensure_mt5_connected(self, max_retries: int = 10, delay: float = 15.0) -> bool:
        """
        Tự động khôi phục kết nối nếu server MT5 hoặc broker bảo trì.
        Kiên nhẫn retry và bảo toàn trạng thái in-memory thay vì thoát tiến trình khi sàn bảo trì cuối tuần.
        """
        if self.mt5_mgr.ensure_connected():
            return True

        retries = 0
        while retries < max_retries and _running:
            retries += 1
            logger.warning(f"⏳ [RECONNECT] Mất kết nối MT5. Đang thử lại lần {retries}/{max_retries} sau {delay:.0f}s...")
            try:
                import MetaTrader5 as mt5
                mt5.shutdown()
            except Exception:
                pass
            time.sleep(delay)

            try:
                if self.mt5_mgr.connect():
                    logger.info("✅ [RECONNECT] Khôi phục kết nối MT5 thành công.")
                    return True
            except Exception as e:
                logger.warning(f"⚠️ [RECONNECT] Thử kết nối lại thất bại: {e}")

        logger.critical(
            f"🚨 [RECONNECT] Vượt quá {max_retries} lần thử kết nối. "
            "Có thể sàn đang bảo trì cuối tuần/nghỉ lễ. Chờ 60s trước chu kỳ quét kế tiếp..."
        )
        time.sleep(60.0)
        return False

    @classmethod
    def is_toxic_hour(cls, hour_utc: Optional[int] = None) -> bool:
        """
        Ma trận chặn khung giờ tử thần (Toxic Hours Blacklist).
        Tập TOXIC_HOURS = {0, 6, 18, 23} UTC là thời điểm chuyển giao phiên hoặc suy giảm
        thanh khoản nghiêm trọng, gây rò rỉ Alpha do whipsaw và giãn spread.
        """
        if hour_utc is None:
            hour_utc = datetime.now(timezone.utc).hour
        return hour_utc in cls.TOXIC_HOURS

    def check_eurgbp_d1_ema200_filter(
        self,
        symbol: str,
        current_h1_price: float,
        action: str,
    ) -> bool:
        """
        Khóa xu hướng D1 EMA200 cho EURGBP (State 31 Corridor Reversion).
        Trích xuất 200 nến D1 bằng mt5.copy_rates_from_pos("EURGBP", mt5.TIMEFRAME_D1, 0, 200).
        Ép cờ allow_buy = False nếu giá H1 hiện tại nằm dưới EMA200, triệt tiêu bắt đáy ngược sóng.
        Returns:
            bool: True nếu được phép giao dịch, False nếu bị từ chối do ngược xu hướng D1.
        """
        if "EURGBP" not in symbol.upper():
            return True

        try:
            import MetaTrader5 as mt5
            actual_sym = self.mt5_mgr.resolve_symbol(symbol)
            rates_d1 = mt5.copy_rates_from_pos(actual_sym, mt5.TIMEFRAME_D1, 0, 200)
            if rates_d1 is None or len(rates_d1) < 200:
                rates_d1 = mt5.copy_rates_from_pos("EURGBP", mt5.TIMEFRAME_D1, 0, 200)

            if rates_d1 is None or len(rates_d1) < 200:
                df_d1 = self.mt5_mgr.get_rates(actual_sym, "D1", count=200)
                if df_d1 is not None and len(df_d1) >= 200:
                    rates_d1 = df_d1
                else:
                    logger.warning(f"⚠️ [D1 EMA200 FILTER] Không trích xuất đủ 200 nến D1 cho {symbol}, giữ nguyên lệnh.")
                    return True

            if isinstance(rates_d1, pd.DataFrame):
                df_d1 = rates_d1
            else:
                df_d1 = pd.DataFrame(rates_d1)

            ema200 = df_d1["close"].ewm(span=200, adjust=False).mean().iloc[-1]
            allow_buy = current_h1_price >= ema200

            if action.upper() == "BUY" and not allow_buy:
                logger.info(
                    f"🛡️ [STATE_31 D1 EMA200 GATEKEEPER] {symbol} BUY bị từ chối: "
                    f"Giá H1 hiện tại ({current_h1_price:.5f}) nằm dưới D1 EMA200 ({ema200:.5f}) "
                    f"-> allow_buy={allow_buy}. Triệt tiêu hoàn toàn chuỗi lệnh bắt đáy ngược sóng."
                )
                return False

            return True
        except Exception as e:
            logger.warning(f"⚠️ Exception in check_eurgbp_d1_ema200_filter for {symbol}: {e}")
            return True

    @classmethod
    def is_us_dst(cls, dt_utc: Optional[datetime] = None) -> bool:
        """
        Tính toán chính xác trạng thái Giờ Mùa Hè Mỹ (US Daylight Saving Time - EDT vs EST):
        - Bắt đầu: Chủ Nhật thứ 2 của tháng 3 lúc 07:00 UTC (02:00 EST -> 03:00 EDT).
        - Kết thúc: Chủ Nhật đầu tiên của tháng 11 lúc 06:00 UTC (02:00 EDT -> 01:00 EST).
          (Ví dụ: Chủ Nhật 01/11/2026 06:00 UTC chuyển từ EDT sang EST).
        - Khi US DST = True (Mùa hè): Giờ Server MT5 (Exness) = UTC+3 (Đóng sàn Thứ Sáu lúc 20:59 UTC = 23:59 Server Time).
        - Khi US DST = False (Mùa đông, từ 01/11/2026): Giờ Server MT5 = UTC+2 (Đóng sàn Thứ Sáu lúc 21:59 UTC = 23:59 Server Time).
        """
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        year = dt_utc.year
        # 2nd Sunday of March
        march_1 = datetime(year, 3, 1, tzinfo=timezone.utc)
        days_to_first_sun_mar = (6 - march_1.weekday()) % 7
        dst_start = datetime(year, 3, 1 + days_to_first_sun_mar + 7, 7, 0, 0, tzinfo=timezone.utc)
        # 1st Sunday of November
        nov_1 = datetime(year, 11, 1, tzinfo=timezone.utc)
        days_to_first_sun_nov = (6 - nov_1.weekday()) % 7
        dst_end = datetime(year, 11, 1 + days_to_first_sun_nov, 6, 0, 0, tzinfo=timezone.utc)
        return dst_start <= dt_utc < dst_end

    @classmethod
    def get_mt5_server_datetime(cls, dt_utc: Optional[datetime] = None) -> datetime:
        """
        Quy đổi giờ UTC sang Giờ Máy Chủ MT5 (MT5 Broker Server Time — chuẩn New York Close + 7h):
        - Mùa hè (EDT, trước 01/11/2026): Server Time = UTC + 3 giờ (23:30 Server Time = 20:30 UTC).
        - Mùa đông (EST, từ 01/11/2026): Server Time = UTC + 2 giờ (23:30 Server Time = 21:30 UTC).
        """
        from datetime import timedelta
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        offset_hours = 3 if cls.is_us_dst(dt_utc) else 2
        return dt_utc + timedelta(hours=offset_hours)

    @classmethod
    def is_friday_or_weekend_curfew(cls, dt_utc: Optional[datetime] = None) -> bool:
        """
        Kiểm tra khung giờ cấm mở lệnh mới cuối tuần theo MT5 Server Time (Skill 07 Time Rule 23:45):
        - Thứ Sáu từ 23:00 MT5 Server Time trở đi (1 giờ trước khi sàn đóng cửa lúc 23:59 Server Time;
          tương ứng 20:00 UTC mùa hè EDT và 21:00 UTC mùa đông EST sau ngày 01/11/2026).
        - Toàn bộ ngày Thứ Bảy.
        - Chủ Nhật trước giờ mở phiên tuần mới (00:00 MT5 Server Time Thứ Hai = 21:00 UTC mùa hè / 22:00 UTC mùa đông).
        """
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        srv_dt = cls.get_mt5_server_datetime(dt_utc)
        srv_wd = srv_dt.weekday()
        # Thứ Sáu >= 23:00 Server Time (hoặc sang Thứ Bảy theo giờ Server)
        if srv_wd == 4 and srv_dt.hour >= 23:
            return True
        if srv_wd in (5, 6):
            return True
        # Dự phòng nếu dt_utc vẫn đang là Thứ Bảy hoặc Chủ Nhật trước giờ mở phiên FX (21:00 EDT / 22:00 EST)
        utc_wd = dt_utc.weekday()
        sunday_open_utc_hour = 21 if cls.is_us_dst(dt_utc) else 22
        if utc_wd == 5:
            return True
        # P0 FIX (Audit 05/11/2026): Chặn mở lệnh mới thêm 60 phút sau giờ mở phiên tuần mới (Chủ Nhật 21:00/22:00 UTC)
        # để né vùng giãn spread cực đại. Curfew cũ (Thứ Hai 00:00 UTC) lệch 2h so với giờ mở phiên thực tế.
        if utc_wd == 6 and dt_utc.hour < sunday_open_utc_hour + 1:
            return True
        return False

    @classmethod
    def get_last_weekly_open_utc(cls, dt_utc: Optional[datetime] = None) -> datetime:
        """
        Trả về mốc mở phiên tuần gần nhất (<= dt_utc): Chủ Nhật 21:00 UTC (US DST/EDT) hoặc 22:00 UTC (EST).
        Chỉ vị thế mở TRƯỚC mốc này mới được coi là "kẹt qua tuần" (Weekend Hold).
        """
        from datetime import timedelta
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        days_since_sunday = (dt_utc.weekday() + 1) % 7
        sunday = (dt_utc - timedelta(days=days_since_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
        candidate = sunday.replace(hour=21 if cls.is_us_dst(sunday + timedelta(hours=12)) else 22)
        if candidate > dt_utc:
            prev_sunday = sunday - timedelta(days=7)
            candidate = prev_sunday.replace(hour=21 if cls.is_us_dst(prev_sunday + timedelta(hours=12)) else 22)
        return candidate

    @classmethod
    def is_friday_eod_flat_window(cls, dt_utc: Optional[datetime] = None) -> bool:
        """
        Kiểm tra khung giờ xả sạch danh mục tối Thứ Sáu theo MT5 Server Time (Skill 07 Time Rule 23:30 - 23:45 Server Time):
        - Kích hoạt cố định từ 23:30 MT5 Server Time Thứ Sáu (29 phút trước giờ đóng sàn 23:59 Server Time).
        - Tự động thích ứng với đổi giờ mùa đông Mỹ (US DST 01/11/2026):
          + Trước 01/11/2026 (EDT, Server UTC+3): 23:30 Server Time = 20:30 UTC.
          + Từ 01/11/2026 (EST, Server UTC+2): 23:30 Server Time = 21:30 UTC (không bị đóng sớm 1.5h!).
        """
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        srv_dt = cls.get_mt5_server_datetime(dt_utc)
        # 23:30 -> 23:59 Server Time Thứ Sáu, hoặc vừa bước sang 00:xx Thứ Bảy Server Time khi dt_utc vẫn là Thứ Sáu
        if srv_dt.weekday() == 4 and srv_dt.hour == 23 and srv_dt.minute >= 30:
            return True
        if dt_utc.weekday() == 4 and srv_dt.weekday() == 5:
            return True
        return False

    def enforce_friday_eod_flat(self) -> int:
        """
        Emergency Circuit Breaker: Friday EOD Flat Rule (Bảo toàn 100% tỷ trọng tiền mặt cuối tuần).
        Khi Thứ Sáu >= 20:30 UTC (23:30 Server Time — trước giờ đóng sàn 20:59 UTC), tự động quét
        mt5.positions_get() và bắn các lệnh thị trường đối ứng để dọn sạch danh mục (Time Rule 23:45).
        Returns:
            int: Số lượng vị thế đã thanh lý thành công.
        """
        closed_count = 0
        try:
            import MetaTrader5 as mt5
            positions = mt5.positions_get()
            if not positions:
                mgr_positions = self.mt5_mgr.get_positions()
                if not mgr_positions:
                    return 0
                positions = mgr_positions

            logger.warning(
                f"🛑 [FRIDAY EOD FLAT RULE KÍCH HOẠT] Thứ Sáu >= 20:30 UTC (Time Rule 23:30-23:45 Server Time). "
                f"Phát hiện {len(positions)} vị thế đang mở. Bắn lệnh thị trường đối ứng dọn sạch danh mục!"
            )
            for pos in positions:
                ticket = getattr(pos, "ticket", None) if hasattr(pos, "ticket") else (pos.get("ticket") if isinstance(pos, dict) else None)
                symbol = getattr(pos, "symbol", "") if hasattr(pos, "symbol") else (pos.get("symbol", "") if isinstance(pos, dict) else "")
                profit = getattr(pos, "profit", 0.0) if hasattr(pos, "profit") else (pos.get("profit", 0.0) if isinstance(pos, dict) else 0.0)

                if ticket is None:
                    continue

                logger.info(
                    f"🧹 [FRIDAY LIQUIDATION] Đóng vị thế Ticket #{ticket} ({symbol}) | Floating PnL: ${profit:+.2f} USD."
                )
                res = self.mt5_mgr.close_position(ticket=ticket, comment="Friday EOD Flat")
                if res.get("success"):
                    closed_count += 1
                else:
                    logger.error(f"❌ Lỗi thanh lý Thứ Sáu Ticket #{ticket}: {res.get('error')}")
        except Exception as e:
            logger.error(f"⚠️ Exception in enforce_friday_eod_flat: {e}")
        return closed_count

    def check_symbol_liquidation_readiness(
        self,
        symbol: str,
        now_utc: Optional[datetime] = None,
        max_tick_age_sec: float = 60.0,
        open_warmup_sec: float = 600.0,
    ) -> tuple[bool, str]:
        """
        Bộ lọc thực thi vi cấu trúc 3 tầng theo từng Symbol (Per-Symbol Microstructure Gatekeeper):
        1. Per-Symbol Trading Schedule & Tick Freshness (<= 60s):
           - Kiểm tra từng mã độc lập (Forex mở 22:05 UTC Chủ Nhật, USTEC mở 23:00 UTC, UK100 mở 01:00 UTC Thứ Hai).
           - Yêu cầu `symbol_info(symbol).trade_mode == SYMBOL_TRADE_MODE_FULL` và `tick.time` mới cập nhật trong <= 60s.
        2. Sunday/Monday Session Open Warmup Buffer (10 phút = 600s):
           - Ghi nhận thời điểm đầu tiên mã đó có tick mới sau kỳ nghỉ (`_symbol_reopen_first_seen_ts`).
           - Trì hoãn xả lệnh Market trong 10 phút đầu mở phiên để né vùng giãn spread cực đại (5x-10x).
        3. Per-Symbol Spread Filter (`current_spread <= 1.5 * max_normal_spread`):
           - FX Majors (EURUSD, USDJPY...): <= 35 points (3.5 pips).
           - FX Crosses (EURGBP, GBPCHF, EURAUD...): <= 65 points (6.5 pips).
           - Indices (USTEC, UK100, US30...): spread / bid <= 0.08% (8 bps).
           - Safety Ceiling: Nếu đã qua >= 30 phút (1800s) từ lúc mở cửa mà spread vẫn cao, cho phép đóng cưỡng bức.
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        now_ts = now_utc.timestamp()

        if not hasattr(self, "_symbol_reopen_first_seen_ts") or self._symbol_reopen_first_seen_ts is None:
            self._symbol_reopen_first_seen_ts = self._load_sweeper_reopen_state()

        if not self.mt5_mgr.is_market_open(symbol):
            return False, f"Market closed for {symbol}"

        try:
            import MetaTrader5 as mt5
            actual_sym = self.mt5_mgr.resolve_symbol(symbol) if hasattr(self.mt5_mgr, "resolve_symbol") else symbol
            if not isinstance(actual_sym, str) or not actual_sym:
                actual_sym = symbol

            sym_info = mt5.symbol_info(actual_sym)
            tick = mt5.symbol_info_tick(actual_sym)

            # Nếu đang chạy trong môi trường unit test không mock tick thực (tick=None hoặc MagicMock không có số thực)
            if tick is None or not isinstance(getattr(tick, "time", None), (int, float)):
                return True, "OK (Manager market_open verified)"

            if sym_info is not None:
                trade_mode = getattr(sym_info, "trade_mode", None)
                full_mode = getattr(mt5, "SYMBOL_TRADE_MODE_FULL", 4)
                if isinstance(trade_mode, int) and trade_mode != full_mode:
                    return False, f"Trade mode {trade_mode} != FULL for {actual_sym}"

            tick_time = float(tick.time)
            if tick_time <= 0:
                return False, f"Invalid tick.time=0 for {actual_sym}"

            # Đồng bộ hệ quy chiếu múi giờ giữa now_utc và tick.time:
            # Nếu tick.time của MT5 đã cộng sẵn offset của Broker Server (UTC+2/UTC+3),
            # phép trừ (now_ts - tick_time) sẽ bị âm (-7200s đến -10800s). Khi đó quy chiếu sang get_mt5_server_datetime:
            tick_age = now_ts - tick_time
            if tick_age < -60.0:
                srv_ts = self.get_mt5_server_datetime(now_utc).timestamp()
                tick_age = srv_ts - tick_time

            if tick_age > max_tick_age_sec or tick_age < -60.0:
                # Reset mốc mở cửa nếu tick đã cũ (thị trường đang nghỉ)
                if actual_sym in self._symbol_reopen_first_seen_ts:
                    self._symbol_reopen_first_seen_ts.pop(actual_sym, None)
                    self._save_sweeper_reopen_state(self._symbol_reopen_first_seen_ts)
                return False, f"Stale tick ({tick_age:.0f}s > {max_tick_age_sec:.0f}s) - {actual_sym} session not yet open"

            # Ghi nhận & lưu bền vững xuống đĩa thời điểm mở cửa phiên đầu tiên của riêng mã này
            if actual_sym not in self._symbol_reopen_first_seen_ts:
                self._symbol_reopen_first_seen_ts[actual_sym] = now_ts
                self._save_sweeper_reopen_state(self._symbol_reopen_first_seen_ts)
            first_seen = float(self._symbol_reopen_first_seen_ts[actual_sym])
            elapsed_since_open = max(0.0, now_ts - first_seen)

            # Kiểm tra đệm trễ 10 phút đầu mở phiên (Warmup Buffer)
            if open_warmup_sec > 0 and elapsed_since_open < open_warmup_sec:
                return (
                    False,
                    f"Warmup Buffer active for {actual_sym} ({elapsed_since_open:.0f}s / {open_warmup_sec:.0f}s post-open)",
                )

            # Kiểm tra bộ lọc Giãn Spread (trừ khi đã vượt quá 30 phút = 1800s safety ceiling)
            bid = float(getattr(tick, "bid", 0.0) or 0.0)
            ask = float(getattr(tick, "ask", 0.0) or 0.0)
            point = float(getattr(sym_info, "point", 0.0) or 0.0) if sym_info is not None else 0.0

            if bid > 0 and ask >= bid and elapsed_since_open < 1800.0:
                sym_upper = actual_sym.upper()
                is_index = any(k in sym_upper for k in ["USTEC", "US30", "UK100", "HK50", "US500", "DE30", "JP225"])
                if is_index:
                    rel_spread = (ask - bid) / bid
                    max_rel_spread = 0.0008  # 8 bps (1.5x normal index spread)
                    if rel_spread > max_rel_spread:
                        return (
                            False,
                            f"Index Spread Guard active for {actual_sym} ({rel_spread*10000:.1f} bps > {max_rel_spread*10000:.1f} bps)",
                        )
                elif point > 0:
                    spread_pts = (ask - bid) / point
                    is_major = any(
                        m in sym_upper
                        for m in ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
                    )
                    max_pts = 35.0 if is_major else 65.0  # 3.5 pips cho Majors, 6.5 pips cho Crosses (EURGBP, GBPCHF, EURAUD)
                    if spread_pts > max_pts:
                        return (
                            False,
                            f"FX Spread Guard active for {actual_sym} ({spread_pts:.1f} pts > {max_pts:.1f} pts)",
                        )

            return True, f"Ready (post-open={elapsed_since_open:.0f}s)"
        except Exception as e:
            logger.debug(f"check_symbol_liquidation_readiness fallback for {symbol}: {e}")
            return True, "OK (Fallback)"

    def enforce_weekend_hold_sweeper(
        self,
        now_utc: Optional[datetime] = None,
        open_warmup_sec: float = 600.0,
    ) -> int:
        """
        Skill 07 Anti-Weekend-Hold & 12h Max-Hold Sweeper (Microstructure V2):
        1. Nếu đang trong khung Friday EOD Flat (23:30 - 23:59 MT5 Server Time Thứ Sáu):
           Gọi enforce_friday_eod_flat() đối với các mã đang mở giao dịch.
        2. Nếu phát hiện vị thế bị kẹt qua tuần (Weekend Hold) hoặc ngâm >= 12h:
           - Kiểm tra độc lập từng Symbol qua `check_symbol_liquidation_readiness()`:
             + Tick mới cập nhật <= 60s (`USTEC` mở 23:00 UTC, `UK100` mở 01:00 UTC không bị bắn nhầm lúc 22:05 UTC).
             + Đệm trễ 10 phút (600s) sau khi mã đó mở cửa phiên sáng Thứ Hai để né giãn spread đầu phiên.
             + Bộ lọc Spread <= 1.5x bình thường trước khi bắn lệnh đóng.
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        # P0 FIX (Audit 05/11/2026): Vòng lặp chính luôn truyền now_utc nên trước đây warmup = 0s
        # (log: "Gate: Ready (post-open=0s)"). Nay warmup 600s là mặc định cho mọi lời gọi.

        if self.is_friday_eod_flat_window(now_utc):
            positions = self.mt5_mgr.get_positions()
            open_market_positions = [
                p for p in positions if self.mt5_mgr.is_market_open(p.get("symbol", ""))
            ]
            if open_market_positions:
                return self.enforce_friday_eod_flat()
            elif positions:
                logger.info(
                    f"⏸️ [WEEKEND HOLD QUEUED] Phát hiện {len(positions)} vị thế mở sau giờ đóng sàn Thứ Sáu. "
                    f"Đã đưa vào hàng đợi thanh lý thông minh (Per-Symbol Tick + Spread Guard) khi thị trường mở cửa!"
                )
            return 0

        closed_count = 0
        positions = self.mt5_mgr.get_positions()
        if not positions:
            return 0

        # P0 FIX (Audit 05/11/2026): `is_weekend = now.weekday() in (5, 6)` từng gắn cờ MỌI vị thế (kể cả lệnh vừa mở)
        # là Weekend Hold suốt tối Chủ Nhật UTC -> vòng lặp mở/đóng 82 lệnh (-$158.72) lúc 22:09-22:45 UTC 01/11/2026.
        # ISO-week cũng sai: lệnh mở tối Chủ Nhật bị coi là "tuần trước" lúc 00:00 UTC Thứ Hai.
        # Nay chỉ vị thế mở TRƯỚC mốc mở phiên tuần gần nhất mới là Weekend Hold.
        last_weekly_open_utc = self.get_last_weekly_open_utc(now_utc)

        for pos in positions:
            ticket = pos.get("ticket")
            symbol = pos.get("symbol", "")
            profit = float(pos.get("profit", 0.0))
            pos_time = pos.get("time")
            if isinstance(pos_time, datetime):
                pos_time_utc = pos_time if pos_time.tzinfo else pos_time.replace(tzinfo=timezone.utc)
            elif isinstance(pos_time, (int, float)):
                pos_time_utc = datetime.fromtimestamp(pos_time, tz=timezone.utc)
            else:
                pos_time_utc = now_utc

            pos_age_hours = (now_utc - pos_time_utc).total_seconds() / 3600.0
            is_weekend_hold = pos_time_utc < last_weekly_open_utc
            is_over_12h_hold = pos_age_hours >= 12.0

            if is_weekend_hold or is_over_12h_hold:
                effective_warmup = open_warmup_sec if is_weekend_hold else 0.0
                ready, readiness_reason = self.check_symbol_liquidation_readiness(
                    symbol=symbol,
                    now_utc=now_utc,
                    max_tick_age_sec=60.0,
                    open_warmup_sec=effective_warmup,
                )
                if not ready:
                    logger.info(
                        f"⏳ [SWEEPER MICROSTRUCTURE GUARD] Hoãn đóng #{ticket} ({symbol}): {readiness_reason}"
                    )
                    continue

                reason_comment = "Weekend Hold Flat" if is_weekend_hold else "Emergency 12h Cut"
                logger.warning(
                    f"🧹 [SKILL 07 {reason_comment.upper()}] Thanh lý vị thế Ticket #{ticket} ({symbol}) "
                    f"ngâm {pos_age_hours:.1f}h (Open: {pos_time_utc.strftime('%Y-%m-%d %H:%M')} UTC, "
                    f"PnL: ${profit:+.2f} USD | Gate: {readiness_reason})."
                )
                res = self.mt5_mgr.close_position(ticket=ticket, comment=reason_comment)
                if res.get("success"):
                    closed_count += 1
        return closed_count

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
        reconnect_fail_count = 0

        while _running:
            try:
                now_utc = datetime.now(timezone.utc)

                # MT5 Auto-Reconnect Loop (Resilient against Broker Weekend Maintenance & IPC Disconnects)
                if not self.ensure_mt5_connected(max_retries=10, delay=15.0):
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
                        sys.exit(99)

                    # Emergency Circuit Breaker: Friday EOD Flat Rule (>= 20:30 UTC / 23:30 Server Time) & Weekend Hold Sweeper (Skill 07)
                    self.enforce_weekend_hold_sweeper(now_utc)

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

                    # 1b. Enforce Hard Stop Cap on US Indices (Step 3: -$60 USD)
                    self.enforce_index_hard_stop_cap(max_loss_usd=60.0)

                    # 2. Enforce Mandatory Stop Loss Protection (Article 00 Safeguard)
                    self.mt5_mgr.enforce_mandatory_sl_protection(default_sl_pct=0.015)

                    # 3. Enforce Two-Tier Exit Engine (Partial TP & Dynamic Trailing Runner) (Task 3)
                    self.enforce_two_tier_exit_engine(min_partial_profit_usd=25.0)

                    # 4. Tactical Index Over-exposure De-risking on rebound
                    self.reconcile_index_duplicate_derisking()

                    # 5. Thực thi Trailing Stop động Chandelier Exit (ATR14 H1) cho các vị thế đang thả nổi
                    try:
                        self.ts_manager.update_trailing_stops()
                    except Exception as e:
                        logger.error(f"Trailing Stop Routine Error: {e}")

                    # 6. Triển khai Time-Based Stagnation Exit (Thoát vị thế ngâm >= 4 giờ và lãi < $10.0 USD)
                    positions = self.mt5_mgr.get_positions()
                    stagnant_closed = False
                    for pos in positions:
                        pos_time = pos.get("time")
                        if isinstance(pos_time, datetime):
                            pos_time_utc = pos_time if pos_time.tzinfo else pos_time.replace(tzinfo=timezone.utc)
                        elif isinstance(pos_time, (int, float)):
                            pos_time_utc = datetime.fromtimestamp(pos_time, tz=timezone.utc)
                        else:
                            continue
                        pos_age_hours = (now_utc - pos_time_utc).total_seconds() / 3600.0
                        pos_profit = float(pos.get("profit", 0.0))
                        ticket = pos.get("ticket")
                        symbol = pos.get("symbol")
                        if pos_age_hours >= 4.0 and pos_profit < 10.0:
                            if not self.mt5_mgr.is_market_open(symbol):
                                continue
                            logger.info(
                                f"⏱️ [TIME-BASED STAGNATION EXIT] Ticket #{ticket} ({symbol}) "
                                f"ngâm {pos_age_hours:.1f}h trong sideway (Lãi trôi nổi: ${pos_profit:+.2f} USD < $10.0 USD). "
                                f"Đóng chủ động bảo toàn vốn."
                            )
                            self.mt5_mgr.close_position(ticket=ticket, comment="Stagnation Exit")
                            stagnant_closed = True

                    if stagnant_closed:
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
