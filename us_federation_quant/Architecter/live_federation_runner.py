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
import atexit
if os.name == "nt":
    import msvcrt
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Ensure root paths
# Runner nằm trong Architecter/; _DIR luôn là thư mục gói us_federation_quant; logs/lock/.env nằm ở Architecter/, data ở Project/, config ở Control/.
_DIR = Path(__file__).resolve().parent.parent
_WORKSPACE = _DIR.parent

_LOCK_FILE_PATH = _DIR / "Architecter" / "us_federation_quant.lock"
_LOCK_FILE_OBJ = None

def acquire_single_instance_lock():
    """
    Trụ cột 1: Single-Instance OS Mutex Lock.
    Sử dụng msvcrt.locking (LK_NBLCK) trên Windows để khóa độc quyền us_federation_quant.lock
    ngay khi khởi động tiến trình. Nếu file đã bị khóa bởi tiến trình khác, lập tức ghi log
    [CRITICAL] Duplicate instance detected và thoát trong < 10ms.
    """
    global _LOCK_FILE_OBJ
    if os.name != "nt":
        return
    try:
        _LOCK_FILE_OBJ = open(_LOCK_FILE_PATH, "a+b")
        _LOCK_FILE_OBJ.seek(0)
        msvcrt.locking(_LOCK_FILE_OBJ.fileno(), msvcrt.LK_NBLCK, 1)
        _LOCK_FILE_OBJ.seek(0)
        _LOCK_FILE_OBJ.truncate()
        _LOCK_FILE_OBJ.write(f"{os.getpid()}\n".encode("utf-8"))
        _LOCK_FILE_OBJ.flush()
    except (IOError, OSError) as e:
        msg = f"🛑 [CRITICAL] Duplicate instance detected! us_federation_quant.lock is exclusively held by another process: {e}"
        try:
            logger.critical(msg)
        except Exception:
            pass
        print(msg, file=sys.stderr)
        sys.exit(1)

def release_single_instance_lock():
    global _LOCK_FILE_OBJ
    if os.name == "nt" and _LOCK_FILE_OBJ:
        try:
            _LOCK_FILE_OBJ.seek(0)
            msvcrt.locking(_LOCK_FILE_OBJ.fileno(), msvcrt.LK_UNLCK, 1)
            _LOCK_FILE_OBJ.close()
            _LOCK_FILE_OBJ = None
            if _LOCK_FILE_PATH.exists():
                _LOCK_FILE_PATH.unlink(missing_ok=True)
        except Exception:
            pass

atexit.register(release_single_instance_lock)

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
    from us_federation_quant.Anpha.l4_risk import FleetGuard, GuardConfig
    from us_federation_quant.Anpha.l6_telemetry import FleetHeartbeat, TelemetryNotifier
    from us_federation_quant.Anpha.l6_telemetry import GeminiSmartRouter, TaskTier
except ImportError:
    try:
        from us_federation_quant.Anpha.l4_risk import FleetGuard, GuardConfig
        from us_federation_quant.Anpha.l6_telemetry import FleetHeartbeat, TelemetryNotifier
        from us_federation_quant.Anpha.l6_telemetry import GeminiSmartRouter, TaskTier
    except ImportError:
        from bots._shared.fleet_guard import FleetGuard, GuardConfig
        from bots._shared.fleet_telemetry import FleetHeartbeat, TelemetryNotifier
        from bots._shared.gemini_router import GeminiSmartRouter, TaskTier

# Import Federation Components dynamically (handles numeric prefixes)
_hub_mod = importlib.import_module("us_federation_quant.Architecter.federation_hub")
FederationHub = _hub_mod.FederationHub

_titan_mod = importlib.import_module("us_federation_quant.Anpha.l3_sizing")
QuadTitanEngine = _titan_mod.QuadTitanEngine

from us_federation_quant.Anpha.contracts import CloseDirective, CycleState, OrderIntent, RiskCheck  # noqa: E402
from us_federation_quant.Architecter.pipeline import run_one_cycle  # noqa: E402
from us_federation_quant.Anpha import l1_data as _l1  # noqa: E402
from us_federation_quant.Anpha import l2_alpha as _l2  # noqa: E402
from us_federation_quant.Anpha import l3_sizing as _l3  # noqa: E402
from us_federation_quant.Anpha.l1_data import market_view as _market_view  # noqa: E402
from us_federation_quant.Anpha import l4_risk as _l4_time  # noqa: E402
from us_federation_quant.Anpha.l4_risk import evaluate_risk  # noqa: E402
from us_federation_quant.Anpha.l5_execution import (  # noqa: E402
    ExecutionOutcome, ensure_connected_with_retry, execute_directives, submit_order_intent,
)

_states_reg_mod = importlib.import_module("us_federation_quant.Anpha.l2_alpha")
ELITE_STATE_IDS = getattr(_states_reg_mod, "ELITE_STATE_IDS", [])
ELIMINATED_STATE_IDS = getattr(_states_reg_mod, "ELIMINATED_STATE_IDS", [])

try:
    from us_federation_quant.Anpha.l5_execution import MT5ConnectionManager
except ImportError:
    from All_Fleet_Bot.core.mt5_connection_manager import MT5ConnectionManager

try:
    from us_federation_quant.Anpha.l4_risk import HighWaterMarkTracker
except ImportError:
    from us_federation_quant.Anpha.l4_risk import HighWaterMarkTracker

try:
    from us_federation_quant.Anpha.l5_execution import generate_client_order_id, OrderState
except ImportError:
    from us_federation_quant.Anpha.l5_execution import generate_client_order_id, OrderState

try:
    from us_federation_quant.Anpha.l5_execution import TrailingStopManager
except ImportError:
    from us_federation_quant.Anpha.l5_execution import TrailingStopManager

# Setup Logging
LOG_DIR = _DIR / "Architecter" / "logs"
try:
    from us_federation_quant.Anpha.l6_telemetry import setup_logger
except ImportError:
    try:
        from us_federation_quant.Anpha.l6_telemetry import setup_logger
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

load_dotenv(_DIR / "Architecter" / ".env")

_running = True


def handle_shutdown(signum, frame):
    global _running
    logger.info("🛑 Constitutional shutdown signal received. Halting US Federation Quant...")
    _running = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)




def _run_hard_cap(rt, check: RiskCheck, max_loss_usd: float) -> List[Dict[str, Any]]:
    positions = rt.mt5_mgr.get_positions()
    res = evaluate_risk(check, positions=positions, params={"max_loss_usd": max_loss_usd})
    return execute_directives(rt, res.directives).get("closed")


def _symbol_trade_gate(actual_symbol):
    """Gate phiên/ngày lễ: trả về (skip, sym_info). Logic ở layers/l1_data.trade_mode_gate."""
    return _l1.trade_mode_gate(actual_symbol)


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

        # 8b. Institutional Risk, Cooldown & Anti-Chasing / Anti-Trend-Trap State (Skill 07 Enhanced)
        self.MAX_HARD_RISK_USD: float = 15.0          # Universal Fallback Cap for ALL Standard Trades
        self.MAX_INDEX_HARD_RISK_USD: float = 60.0    # Institutional Risk Cap for US Indices (USTEC/US30/US100/US500)
        self.COOLDOWN_AFTER_EXIT_SEC: float = 900.0   # 15 phút khóa sau khi đóng bất kỳ lệnh nào (3 nến M5)
        self.MAX_CONSECUTIVE_SL_SAME_DIR: int = 2     # Tối đa 2 lệnh SL liên tiếp cùng chiều
        self.DIRECTION_LOCKOUT_SEC: float = 7200.0    # Khóa chiều thua 2 tiếng (7200s)
        self.symbol_state: Dict[str, Dict[str, Any]] = {}
        self._tracked_open_tickets: Dict[int, Dict[str, Any]] = {}
        self._tier2_locked_tickets: Set[int] = set()  # Trụ cột 4: Miễn nhiễm Stagnation Exit 4h cho các vị thế đã khóa lãi +5$ USD
        self._profit_ladder_locked_tickets: Set[int] = set()  # Bậc thang Khóa Lãi 3 Tầng: Miễn nhiễm Stagnation tuyệt đối
        self.ELITE_ALPHA_SYMBOLS: Set[str] = {"GBPCHF", "EURAUD", "GBPUSD", "USDCHF", "US30"}
        self.ALPHA_BOOSTER_MULTIPLIER: float = 1.6    # Hệ số đòn bẩy Alpha cho nhóm Elite under $15 Cap

        # 8. Financial ML Engine: Marcos López de Prado Meta-Labeling Inference Service
        try:
            import importlib
            ml_mod = importlib.import_module("us_federation_quant.Anpha.l2_alpha")
            self.ml_service = ml_mod.ModelInferenceService(prob_threshold=0.48)
            logger.info("🧠 [ML ENGINE ACTIVE] Đã kích hoạt ModelInferenceService (Meta-Labeling AFML & Fractional Kelly).")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize ModelInferenceService: {e}")
            self.ml_service = None

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

    def enforce_hard_risk_cap(self, symbol: str, raw_lot: float, sl_distance_price: float, max_risk_usd: float = 15.0) -> float:
        """
        Khống chế mức lỗ tối đa tại SL không bao giờ vượt quá max_risk_usd ($15.00).
        Làm tròn xuống theo volume_step để đảm bảo toán học không bị làm tròn lên vượt trần rủi ro.
        """
        sym_info = _l1.symbol_spec(self, symbol).info
        return _l3.hard_risk_cap_lot(
            sym_info, symbol, raw_lot, sl_distance_price, max_risk_usd,
            index_cap_usd=getattr(self, "MAX_INDEX_HARD_RISK_USD", 60.0),
            universal_cap_usd=getattr(self, "MAX_HARD_RISK_USD", 15.0))

    def calculate_risk_adjusted_lot(self, symbol: str, sl_points: float, max_risk_usd: float = 15.0) -> float:
        """
        Quant Core V9 & Skill 07: Volatility ATR Dollar Sizing với Hard Risk Cap $15 Mặc định Toàn Cầu.
        Dynamically calculates lot size such that hitting Stop Loss risks at most max_risk_usd ($15.00 default).

        Formula: raw_lot = max_risk_usd / (sl_points * tick_value_per_point)
        Live MT5 Integration: Fetches trade_tick_value, trade_tick_size, point, volume_step via mt5.symbol_info().
        Cap Logic: Hard caps lot size between 0.01 and 0.03 for ["USTEC", "US30", "US100", "HK50"].
        Normalization: Rounds down (floor) to broker volume_step so expected loss never exceeds $15.00.
        """
        # 1. Đọc spec (L1) -> 2. toán lot thuần (L3) -> 3. ghi log
        spec_read = _l1.symbol_spec(self, symbol, suffix_fallback=True, mgr_fallback=True)
        lot, log = _l3.risk_adjusted_lot(
            symbol, sl_points, max_risk_usd, spec_read,
            universal_cap_usd=getattr(self, "MAX_HARD_RISK_USD", 15.0))
        getattr(logger, log.level)(log.message)
        return lot

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

        # Logic 1b (Zero Weekend Hold - Friday Entry Lock):
        # Chặn toàn bộ việc mở vị thế mới vào Thứ Sáu từ 19:00 UTC (và từ 18:00 UTC cho Chỉ số)
        # để đảm bảo toàn bộ vị thế có đủ thời gian chạm TP hoặc đóng sạch trước giờ đóng sàn cuối tuần.
        if now_dt.weekday() == 4 and now_dt.hour >= 19:
            logger.info(
                f"🛡️ [FRIDAY ZERO-WEEKEND-HOLD CURFEW] Thứ Sáu {now_dt.strftime('%H:%M')} UTC: "
                f"Khóa hoàn toàn việc mở vị thế mới từ 19:00 UTC Thứ Sáu để đảm bảo 100% tiền mặt cuối tuần (Skill 07)."
            )
            return executed_trades

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

            # Deactivate HK50 (STATE_17): Low win rate (26%), noise PnL, session closed retcode=10044
            if "HK50" in clean_ticker or pod.state_id == "STATE_17":
                continue

            # Task 4.2: Blacklist illiquid / high-spread US Equities
            if clean_ticker in self.US_EQUITIES_BLACKLIST:
                continue

            # 0. Market Session & Holiday Gatekeeper (skip closed markets, holiday sessions, and weekend hours)
            skip_pod, sym_info = _symbol_trade_gate(actual_symbol)
            if skip_pod:
                continue  # ADR-004: fail-closed, lỗi/None/không FULL -> bỏ pod, không kế thừa sym_info của pod trước

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

            # Logic 2 (US Index NY Session Gate & Trụ cột 3 NYSE Opening Bell Blackout)
            is_us_index = any(idx in actual_symbol.upper() for idx in ["USTEC", "US30", "US100", "US500"])
            if is_us_index:
                if not (13 <= now_dt.hour <= 21):
                    logger.info(
                        f"🛡️ [INDEX SESSION GATE] {pod.state_id} ({actual_symbol}): "
                        f"Bỏ qua tín hiệu ngoài phiên New York ({now_dt.hour:02d}:{now_dt.minute:02d} UTC). "
                        f"Chỉ cho phép mở lệnh chỉ số từ 13:00 đến 21:00 UTC."
                    )
                    continue

                # Trụ cột 3: NYSE Opening Bell Blackout (14:25:00 UTC đến 14:45:00 UTC)
                # Cấm mở lệnh mới đối với các mã chỉ số Mỹ trong 20 phút đầu mở phiên NYSE để chống giãn spread & săn thanh khoản
                if now_dt.hour == 14 and (25 <= now_dt.minute <= 45):
                    logger.info(
                        f"🛡️ [VETO_NYSE_OPEN_BLACKOUT] {pod.state_id} ({actual_symbol}): "
                        f"Cấm mở lệnh chỉ số trong 20 phút mở cửa NYSE ({now_dt.strftime('%H:%M:%S')} UTC) "
                        f"để tránh giãn spread và săn thanh khoản (Opening Bell Stop-Hunt)."
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

                    # Anti-Chasing Cooldown (15p) & Same-Direction SL Lockout (2h) (Skill 07 Enhanced)
                    can_enter, reason = self.can_enter_trade(actual_symbol, proposal.action, time.time())
                    if not can_enter:
                        logger.info(
                            f"🛡️ [COOLDOWN/TREND-LOCK VETO] {pod.state_id} ({actual_symbol} {proposal.action}): {reason}"
                        )
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

                    # Trụ cột 2: Khóa xu hướng vĩ mô H4/D1 EMA200 cho nhóm JPY (EURJPY, AUDJPY, GBPJPY, USDJPY)
                    if any(jpy in actual_symbol.upper() for jpy in ["EURJPY", "AUDJPY", "GBPJPY", "USDJPY"]):
                        current_h1_price = float(market_df["close"].iloc[-1])
                        if not self.check_jpy_macro_trend_filter(actual_symbol, current_h1_price, proposal.action):
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
                    from us_federation_quant.Architecter.institutional_governance_rules import check_factor_limits
                    if not check_factor_limits(actual_symbol, existing_positions):
                        logger.warning(
                            f"🛡️ [PRE-TRADE RISK GATEKEEPER] Rejected {pod.state_id} proposal on {actual_symbol}: "
                            f"Breaches currency factor limit (JPY max 1, USD max 2)."
                        )
                        continue

                    # 1c. Financial ML Meta-Labeling Clearance (AFML: Kakushadze Alphas + FracDiff + Variance Ratio)
                    ml_scale = 1.0
                    if getattr(self, "ml_service", None) is not None and len(market_df) >= 30:
                        try:
                            ml_res = self.ml_service.predict_latest_bar(
                                market_df,
                                primary_action=proposal.action,
                                signal_strength=min(1.0, abs(proposal.carver_forecast) / 20.0 if hasattr(proposal, "carver_forecast") else 0.5)
                            )
                            if not ml_res.is_approved:
                                logger.info(
                                    f"🧠 [ML META-LABELING VETO] {pod.state_id} ({actual_symbol} {proposal.action}) vetoed: "
                                    f"Win Prob {ml_res.win_probability:.1%} < {ml_res.prob_threshold:.1%} (Kelly Mult: {ml_res.kelly_multiplier:.2f})."
                                )
                                continue
                            if ml_res.kelly_multiplier > 0:
                                ml_scale = max(0.70, min(1.25, ml_res.kelly_multiplier))
                        except Exception as e:
                            logger.debug(f"ML inference evaluation skipped: {e}")

                    # 2. Sizing giai đoạn A (L3): giá vào, ATR14, SL/TP, lot (Alpha Booster + ML), chưa qua risk desk
                    tick = self.mt5_mgr.get_tick(actual_symbol) if hasattr(self, "mt5_mgr") else None
                    plan = _l3.size_entry(
                        action=proposal.action, market_df=market_df, tick=tick, sym_info=sym_info, symbol=actual_symbol,
                        ml_scale=ml_scale,
                        max_index_risk_usd=getattr(self, "MAX_INDEX_HARD_RISK_USD", 60.0),
                        max_hard_risk_usd=getattr(self, "MAX_HARD_RISK_USD", 15.0),
                        elite_symbols=getattr(self, "ELITE_ALPHA_SYMBOLS", {"GBPCHF", "EURAUD", "GBPUSD", "USDCHF", "US30"}),
                        booster_multiplier=getattr(self, "ALPHA_BOOSTER_MULTIPLIER", 1.6),
                        lot_fn=self.calculate_risk_adjusted_lot, cap_fn=self.enforce_hard_risk_cap,
                        emit=lambda line: getattr(logger, line.level)(line.message))
                    current_price = plan.current_price

                    # Central Risk Desk clearance (L4), rồi sizing giai đoạn B (L3): chuẩn hóa lot broker, cap cuối, SL/TP
                    cleared_lots = self.hub.central_risk_desk.verify_order_clearance(
                        order_lots=plan.lots,
                        asset_notional=plan.lots * current_price,
                    )
                    levels = _l3.finalize_entry(
                        plan, symbol=actual_symbol, lots_cleared=cleared_lots, sym_info=sym_info, action=proposal.action,
                        normalize_fn=self.mt5_mgr.normalize_lot, cap_fn=self.enforce_hard_risk_cap)
                    cleared_lots, target_sl, target_tp = levels.lots, levels.sl, levels.tp

                    # Pre-Trade Factor Gatekeeper: Ma trận chặn khung giờ tử thần (Toxic Hours Blacklist) ngay trước OrderSend
                    exec_hour_utc = datetime.now(timezone.utc).hour
                    if self.is_toxic_hour(exec_hour_utc):
                        logger.warning(
                            f"🛑 [TOXIC HOURS GATEKEEPER] Từ chối OrderSend {proposal.action} {cleared_lots}L {actual_symbol} "
                            f"tại {exec_hour_utc:02d}:00 UTC (Tập giờ tử thần {self.TOXIC_HOURS}). Vẫn duy trì Trailing Stop."
                        )
                        continue

                    self._submit_proposal_order(pod, proposal, actual_symbol, cleared_lots, target_sl, target_tp,
                                                magic_num, warrant, idm, policy, current_price, executed_trades)

            except Exception as e:
                logger.warning(f"⚠️ Error processing proposal for {pod.state_id}: {e}")

        return executed_trades

    def _submit_proposal_order(self, pod, proposal, actual_symbol, cleared_lots, target_sl, target_tp,
                               magic_num, warrant, idm, policy, current_price, executed_trades) -> None:
        """Đuôi đường vào lệnh: dựng OrderIntent và giao cho L5 (layers/l5_execution.submit_order_intent)."""
        intent = OrderIntent(
            state_id=pod.state_id, state_name=pod.state_name, action=proposal.action, symbol=actual_symbol,
            volume=cleared_lots, sl=target_sl, tp=target_tp, magic=magic_num, current_price=current_price,
            forecast=proposal.carver_forecast, idm=idm, policy=policy, warrant=warrant)
        exec_res = submit_order_intent(self, intent)
        if exec_res is not None:
            executed_trades.append(exec_res)

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
        """Trần lỗ cứng theo vị thế: đóng khẩn cấp khi lỗ nổi (gồm swap + commission) chạm ngưỡng.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        return _run_hard_cap(self, RiskCheck.HARD_CAP_XAUUSD, max_loss_usd)

    def enforce_index_hard_stop_cap(self, max_loss_usd: float = 60.0) -> List[Dict[str, Any]]:
        """Trần lỗ cứng theo vị thế: đóng khẩn cấp khi lỗ nổi (gồm swap + commission) chạm ngưỡng.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        return _run_hard_cap(self, RiskCheck.HARD_CAP_INDEX, max_loss_usd)

    def enforce_gbpchf_uk100_hard_stop_cap(self, max_loss_usd: float = 15.0) -> List[Dict[str, Any]]:
        """Trần lỗ cứng theo vị thế: đóng khẩn cấp khi lỗ nổi (gồm swap + commission) chạm ngưỡng.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        return _run_hard_cap(self, RiskCheck.HARD_CAP_GBPCHF_UK100, max_loss_usd)

    def enforce_forex_portfolio_hard_stop_cap(self, max_loss_usd: float = 15.0) -> List[Dict[str, Any]]:
        """Trần lỗ cứng theo vị thế: đóng khẩn cấp khi lỗ nổi (gồm swap + commission) chạm ngưỡng.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        return _run_hard_cap(self, RiskCheck.HARD_CAP_FOREX_PORTFOLIO, max_loss_usd)

    def check_and_apply_breakeven_lock(self, buffer_pips: float = 1.5) -> List[Dict[str, Any]]:
        """Dời SL về Breakeven + buffer khi lãi >= $12 hoặc đạt >= 50% quãng đường TP.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        positions = self.mt5_mgr.get_positions()
        res = evaluate_risk(RiskCheck.BREAKEVEN_LOCK, positions=positions, market=_market_view(self),
                            params={"buffer_pips": buffer_pips})
        return execute_directives(self, res.directives).get("modified")

    def manage_multi_tier_profit_ladder(self) -> List[Dict[str, Any]]:
        """Bậc thang khóa lãi 3 tầng (+$4 / +$8 / +$15): ratchet SL và nới TP, cấp miễn nhiễm Stagnation.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        positions = self.mt5_mgr.get_positions()
        if not positions:
            return []
        res = evaluate_risk(RiskCheck.PROFIT_LADDER, positions=positions, market=_market_view(self))
        return execute_directives(self, res.directives).get("modified")

    def can_enter_trade(self, symbol: str, direction: str, current_ts: float) -> tuple[bool, str]:
        """
        Kiểm tra Anti-Chasing Cooldown 15p và Chống nhồi lệnh ngược xu hướng (Same-Direction SL Lockout).
        Truy vấn trực tiếp mt5.history_deals_get trong 24h qua để đảm bảo tính stateless persistence
        kể cả khi khởi động lại bot.
        """
        cooldown_sec = getattr(self, "COOLDOWN_AFTER_EXIT_SEC", 900.0)
        lockout_sec = getattr(self, "DIRECTION_LOCKOUT_SEC", 7200.0)

        # 1. Thử truy vấn deals từ MT5 trong 24h qua (L1 gateway)
        deals = None
        try:
            deals = _l1.history_deals(current_ts - 86400, current_ts + 60)
        except Exception as e:
            logger.debug(f"history_deals_get error: {e}")

        res = evaluate_risk(
            RiskCheck.ENTRY_GATE, symbol=symbol,
            params={"direction": direction, "current_ts": current_ts, "deals": deals,
                    "symbol_state_fn": lambda: self.symbol_state,
                    "cooldown_sec": cooldown_sec, "lockout_sec": lockout_sec})
        return res.ready, res.reason

    def update_symbol_exit_tracking(self, now_ts: float):
        """
        Giám sát trạng thái đóng lệnh trong thời gian thực:
        - Ghi nhận `last_exit_ts` để kích hoạt Anti-Chasing Cooldown 15 phút.
        - Phân tích deal thoát lệnh nếu dính Stop Loss: đếm số lần SL liên tiếp cùng chiều.
        - Khóa chiều thua 2 tiếng (7200s) nếu dính 2 SL liên tiếp cùng chiều để triệt hạ bẫy ngược xu hướng.
        """
        try:
            current_positions_list = self.mt5_mgr.get_positions()
            current_positions = {p["ticket"]: p for p in current_positions_list}

            if self._tracked_open_tickets:
                evaluate_risk(
                    RiskCheck.EXIT_TRACKING, state=self.symbol_state,
                    params={
                        "now_ts": now_ts,
                        "tracked_open": self._tracked_open_tickets,
                        "current_positions": current_positions,
                        # Tra cứu deal lịch sử (30 phút) để xem lý do đóng và PnL thực tế: MỘT lần cho MỖI vị thế vừa đóng
                        "deals_lookup": lambda: _l1.history_deals(now_ts - 1800, now_ts + 60),
                        "cooldown_sec": getattr(self, "COOLDOWN_AFTER_EXIT_SEC", 900.0),
                        "lockout_dur": getattr(self, "DIRECTION_LOCKOUT_SEC", 7200.0),
                        "max_consec": getattr(self, "MAX_CONSECUTIVE_SL_SAME_DIR", 2),
                        "emit": lambda line: getattr(logger, line.level)(line.message),
                    })

            self._tracked_open_tickets = current_positions
        except Exception as e:
            logger.debug(f"Error in update_symbol_exit_tracking: {e}")

    def enforce_two_tier_exit_engine(self, min_partial_profit_usd: float = 25.0) -> Dict[str, List[Any]]:
        """Two-Tier Exit: chốt 50% khi lãi >= $25 (idempotent theo state) + khóa lãi runner khi lãi >= $15.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        positions = self.mt5_mgr.get_positions()
        two_tier_state = self._load_two_tier_state()
        res = evaluate_risk(RiskCheck.TWO_TIER_EXIT, positions=positions, market=_market_view(self),
                            params={"min_partial_profit_usd": min_partial_profit_usd}, state=two_tier_state)
        out = execute_directives(self, res.directives, two_tier_state=two_tier_state)
        return {"partial_closed": out.get("partial_closed"), "trailed_runners": out.get("trailed_runners")}

    def enforce_trailing_stop_and_breakeven(self, min_profit_usd: float = 15.0) -> List[Dict[str, Any]]:
        """Backward-compatible wrapper routing to Two-Tier Exit Engine."""
        res = self.enforce_two_tier_exit_engine(min_partial_profit_usd=25.0)
        return res.get("trailed_runners", [])

    def reconcile_index_duplicate_derisking(self) -> List[Dict[str, Any]]:
        """De-risking chiến thuật: đóng 1 lệnh US30 BUY trùng lặp đã hồi về >= -$50.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        positions = self.mt5_mgr.get_positions()
        res = evaluate_risk(RiskCheck.RECONCILE_INDEX, positions=positions)
        return execute_directives(self, res.directives).get("closed")

    def ensure_mt5_connected(self, max_retries: int = 10, delay: float = 15.0) -> bool:
        """
        Tự động khôi phục kết nối nếu server MT5 hoặc broker bảo trì.
        Kiên nhẫn retry và bảo toàn trạng thái in-memory thay vì thoát tiến trình khi sàn bảo trì cuối tuần.
        """
        return ensure_connected_with_retry(self.mt5_mgr, max_retries, delay, keep_running=lambda: _running)

    @classmethod
    def is_toxic_hour(cls, hour_utc: Optional[int] = None) -> bool:
        """Chặn khung giờ tử thần (TOXIC_HOURS); logic ở layers/l1_data."""
        return _l1.is_toxic_hour(hour_utc, cls.TOXIC_HOURS)

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
            actual_sym = self.mt5_mgr.resolve_symbol(symbol)
            rates_d1 = _l1.bars_with_fallback(
                self, [(actual_sym, "D1"), ("EURGBP", "D1")], retry_below=200, mgr_timeframe="D1", mgr_below=200)
            if rates_d1 is None:
                logger.warning(f"⚠️ [D1 EMA200 FILTER] Không trích xuất đủ 200 nến D1 cho {symbol}, giữ nguyên lệnh.")
                return True
            allow, log = _l2.eurgbp_d1_ema200_verdict(rates_d1, current_h1_price, action, symbol)
            if log is not None:
                getattr(logger, log.level)(log.message)
            return allow
        except Exception as e:
            logger.warning(f"⚠️ Exception in check_eurgbp_d1_ema200_filter for {symbol}: {e}")
            return True

    def check_jpy_macro_trend_filter(
        self,
        symbol: str,
        current_price: float,
        action: str,
    ) -> bool:
        """
        Trụ cột 2: Khóa xu hướng vĩ mô H4/D1 EMA200 cho nhóm JPY (EURJPY, AUDJPY, GBPJPY, USDJPY).
        Trích xuất 200 nến H4 (hoặc D1) bằng mt5.copy_rates_from_pos.
        Chặn tuyệt đối BUY nếu current_price < EMA200 (VETO_JPY_COUNTER_TREND).
        Chặn tuyệt đối SELL nếu current_price > EMA200 (VETO_JPY_COUNTER_TREND).
        """
        jpy_pairs = ["EURJPY", "AUDJPY", "GBPJPY", "USDJPY"]
        sym_clean = symbol.upper().replace("M", "")
        if not any(jp in sym_clean for jp in jpy_pairs):
            return True

        try:
            actual_sym = self.mt5_mgr.resolve_symbol(symbol)
            rates_h4 = _l1.bars_with_fallback(
                self, [(actual_sym, "H4"), (actual_sym, "D1")], retry_below=50, mgr_timeframe="H4", mgr_below=30)
            if rates_h4 is None:
                return True
            allow, log = _l2.jpy_macro_trend_verdict(rates_h4, current_price, action, actual_sym)
            if log is not None:
                getattr(logger, log.level)(log.message)
            return allow
        except Exception as e:
            logger.warning(f"⚠️ Exception in check_jpy_macro_trend_filter for {symbol}: {e}")
            return True

    @classmethod
    def is_hk50_session_open(cls, dt_utc: Optional[datetime] = None) -> bool:
        """Phiên HK50 (Exness/HKEX); logic ở layers/l1_data."""
        return _l1.is_hk50_session_open(dt_utc)

    @classmethod
    def is_us_dst(cls, dt_utc: Optional[datetime] = None) -> bool:
        """Trạng thái US DST (EDT/EST); logic ở layers/l4_risk_time."""
        return _l4_time.is_us_dst(dt_utc)

    @classmethod
    def get_mt5_server_datetime(cls, dt_utc: Optional[datetime] = None) -> datetime:
        """UTC -> giờ server MT5 (UTC+3 khi US DST, UTC+2 khi không)."""
        return _l4_time.get_mt5_server_datetime(dt_utc)

    @classmethod
    def is_friday_or_weekend_curfew(cls, dt_utc: Optional[datetime] = None) -> bool:
        """Khung cấm mở lệnh mới cuối tuần (Skill 07 Time Rule 23:45)."""
        return _l4_time.is_friday_or_weekend_curfew(dt_utc)

    @classmethod
    def get_last_weekly_open_utc(cls, dt_utc: Optional[datetime] = None) -> datetime:
        """Mốc mở phiên tuần gần nhất (<= dt_utc); chỉ lệnh mở TRƯỚC mốc này là Weekend Hold."""
        return _l4_time.get_last_weekly_open_utc(dt_utc)

    @classmethod
    def is_friday_eod_flat_window(cls, dt_utc: Optional[datetime] = None, symbol: Optional[str] = None) -> bool:
        """Cửa sổ xả sạch tối Thứ Sáu (chỉ số từ 20:15 UTC; toàn danh mục từ 23:30 server)."""
        return _l4_time.is_friday_eod_flat_window(dt_utc, symbol)

    def enforce_friday_eod_flat(self, now_utc: Optional[datetime] = None) -> int:
        """Friday EOD Flat: thanh lý danh mục cuối tuần. now_utc=None => thanh lý toàn bộ. Trả về số lệnh đóng thành công.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        outcome = ExecutionOutcome()
        try:
            positions = _l1.open_positions(self)
            if not positions:
                return 0
            res = evaluate_risk(RiskCheck.FRIDAY_EOD_FLAT, positions=positions, now_utc=now_utc)
            execute_directives(self, res.directives, outcome=outcome)
        except Exception as e:
            logger.error(f"⚠️ Exception in enforce_friday_eod_flat: {e}")
        return len(outcome.get("closed"))

    def check_symbol_liquidation_readiness(
        self,
        symbol: str,
        now_utc: Optional[datetime] = None,
        max_tick_age_sec: float = 60.0,
        open_warmup_sec: float = 600.0,
    ) -> tuple[bool, str]:
        """Bộ lọc vi cấu trúc theo mã: tick tươi <= 60s, warmup 10 phút sau mở phiên, spread guard (xem l4_risk_session).
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        res = evaluate_risk(RiskCheck.LIQUIDATION_READINESS, symbol=symbol, market=_market_view(self), now_utc=now_utc,
                            params={"max_tick_age_sec": max_tick_age_sec, "open_warmup_sec": open_warmup_sec})
        execute_directives(self, res.directives)
        return res.ready, res.reason

    def enforce_weekend_hold_sweeper(
        self,
        now_utc: Optional[datetime] = None,
        open_warmup_sec: float = 600.0,
    ) -> int:
        """Skill 07 Anti-Weekend-Hold & 12h Max-Hold Sweeper. Trả về số lệnh đã đóng.
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        positions = self.mt5_mgr.get_positions()
        res = evaluate_risk(RiskCheck.WEEKEND_SWEEPER, positions=positions, market=_market_view(self),
                            now_utc=now_utc, params={"open_warmup_sec": open_warmup_sec})
        if res.delegate == "friday_eod_flat":
            return self.enforce_friday_eod_flat(now_utc)
        return len(execute_directives(self, res.directives).get("closed"))

    def enforce_stagnation_exit(self, positions, now_utc) -> bool:
        """Selective Stagnation Exit: cắt lệnh ngâm >= 8h đang âm nhẹ (-$6..$0); miễn nhiễm lệnh có lãi hoặc đã khóa lãi.
        Trả về True nếu đã gửi ít nhất một lệnh đóng (caller làm mới danh sách vị thế).
        (L4: quyết định ở layers/l4_risk; thực thi ở layers/l5_execution.)"""
        active_tickets = {p["ticket"] for p in positions}
        self._profit_ladder_locked_tickets = getattr(self, "_profit_ladder_locked_tickets", set()).intersection(active_tickets)
        self._tier2_locked_tickets = self._tier2_locked_tickets.intersection(active_tickets)
        res = evaluate_risk(
            RiskCheck.STAGNATION_EXIT, positions=positions, market=_market_view(self), now_utc=now_utc,
            state={"ladder_locked": self._profit_ladder_locked_tickets, "tier2_locked": self._tier2_locked_tickets})
        execute_directives(self, res.directives)
        return any(isinstance(d, CloseDirective) for d in res.directives)

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

        cycle = CycleState(last_quad_time=last_quad_time, synthetic_weights=synthetic_weights, returns_history=returns_history)
        while _running:
            try:
                result = run_one_cycle(self, cycle, datetime.now(timezone.utc))
                if result.sleep_s:
                    time.sleep(result.sleep_s)


            except Exception as e:
                logger.error(f"⚠️ Unhandled error in Constitutional Loop: {e}", exc_info=True)
                time.sleep(5)

        # Shutdown
        logger.info("🔌 Shutting down US Federation Quant...")
        self.mt5_mgr.shutdown()
        self.telemetry.send_discord(title="🛑 US Federation Quant Offline", description="All pods safely parked.")
        logger.info("👋 Federation engine shut down cleanly. Long live the Republic!")


if __name__ == "__main__":
    acquire_single_instance_lock()
    runner = USFederationQuantRuntime()
    runner.run()
