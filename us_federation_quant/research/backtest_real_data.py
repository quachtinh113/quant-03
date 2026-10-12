"""
========================================================================================
BACKTEST TRÊN DỮ LIỆU THẬT — CÔNG CỤ THƯỜNG TRỰC
========================================================================================
Chạy pod chiến lược THẬT trên giá THẬT từ MT5 terminal, không mô phỏng.

VÌ SAO CẦN FILE NÀY
-------------------
`research/run_36_month_system_backtest.py` không đọc một nến giá nào. Nó sinh
lợi suất bằng `np.random.standard_t` rồi CỘNG một hằng số lợi thế 11–19bps vào
mọi ngày, nên Sharpe 4.21 là hệ quả toán học của hằng số đó chứ không phải kết
quả đo được. Cột "Sharpe OOS Thực tế" cũng chỉ là `sharpe * 0.55` — không tồn
tại kỳ out-of-sample nào. `data_lake/` cũng là dữ liệu tổng hợp (vàng "giảm" từ
$2.649 xuống $96,60).

File này là đường dẫn duy nhất hiện có để lấy con số có thể tin được.

NGUYÊN TẮC KHÔNG NHÌN TƯƠNG LAI (Điều ② Hiến pháp)
--------------------------------------------------
- Tín hiệu tại nến t chỉ dùng dữ liệu tới hết nến t (nến đã đóng cửa).
- Khớp lệnh tại OPEN của nến t+1. Không bao giờ khớp trong cùng nến sinh tín hiệu.
- Nến MT5 là giá BID. Mua khớp ở ASK = open + spread; bán khớp ở BID.
  => trả spread đúng một lần mỗi vòng lệnh, không double-count.
- Spread lấy THẬT từng nến trong dữ liệu MT5, không phải hằng số giả định.
- KHÔNG có profit-sweep, KHÔNG có "haircut", KHÔNG có hằng số lợi thế.

CÁCH DÙNG
---------
    python research/backtest_real_data.py --fetch --months 36
    python research/backtest_real_data.py --months 36 --lot 0.01
    python research/backtest_real_data.py --months 12 --lot auto --report
========================================================================================
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import warnings
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Console Windows mặc định cp1252 sẽ nổ UnicodeEncodeError khi in emoji/tiếng Việt.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

_DIR = Path(__file__).resolve().parent
_PROJECT = _DIR.parent
_WORKSPACE = _PROJECT.parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

DATA_DIR = _PROJECT / "research" / "real_data"
LOG_DIR = _PROJECT / "logs"

# Thông số hợp đồng XAUUSDm trên Exness (đọc từ symbol_info khi --fetch).
DEFAULT_POINT = 0.001
DEFAULT_CONTRACT_SIZE = 100.0
DEFAULT_SLIPPAGE_POINTS = 10.0
BARS_PER_YEAR_M15 = 96 * 252


# ======================================================================================
# 1. LẤY DỮ LIỆU THẬT
# ======================================================================================
def fetch_real_bars(
    symbol: str = "XAUUSDm",
    timeframe_name: str = "M15",
    max_bars: int = 100_000,
    chunk: int = 10_000,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Kéo nến thật từ MT5 terminal đang chạy. CHỈ ĐỌC — không đặt lệnh nào.

    `copy_rates_range` hay trả 'Invalid params' trên terminal này, nên dùng
    `copy_rates_from_pos` theo từng lô và ghép lại.
    """
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise RuntimeError(f"Không kết nối được MT5 terminal: {mt5.last_error()}")
    try:
        tf = getattr(mt5, f"TIMEFRAME_{timeframe_name}")
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Không chọn được symbol {symbol}")

        frames: List[pd.DataFrame] = []
        pos = 0
        while pos < max_bars:
            rates = mt5.copy_rates_from_pos(symbol, tf, pos, chunk)
            if rates is None or len(rates) == 0:
                break
            frames.append(pd.DataFrame(rates))
            pos += chunk
        if not frames:
            raise RuntimeError(f"MT5 không trả nến nào cho {symbol}: {mt5.last_error()}")

        df = pd.concat(frames, ignore_index=True).drop_duplicates(subset="time")
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(columns={"tick_volume": "volume"}).sort_values("time").reset_index(drop=True)
        df = df[["time", "open", "high", "low", "close", "volume", "spread"]]

        si = mt5.symbol_info(symbol)
        spec = {
            "point": float(si.point),
            "contract_size": float(si.trade_contract_size),
            "volume_min": float(si.volume_min),
            "volume_step": float(si.volume_step),
        }
    finally:
        mt5.shutdown()

    _assert_prices_plausible(df, symbol)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / f"{symbol}_{timeframe_name}.parquet"
    df.to_parquet(out)
    (DATA_DIR / f"{symbol}_{timeframe_name}_spec.json").write_text(
        json.dumps(spec, indent=2), encoding="utf-8"
    )
    return df, spec


def _assert_prices_plausible(df: pd.DataFrame, symbol: str) -> None:
    """
    Chốt an toàn chống lặp lại thảm hoạ `data_lake`: ở đó vàng "giảm" từ $2.649
    xuống $96,60 và `real_volume` luôn đúng bằng `tick_volume * 10`. Không ai
    kiểm tra, nên mọi báo cáo dựng trên đó đều vô nghĩa suốt nhiều tháng.
    """
    if "XAU" in symbol.upper():
        lo, hi = df.close.min(), df.close.max()
        if lo < 500.0 or hi > 20_000.0:
            raise ValueError(
                f"Giá {symbol} không khả tín: min=${lo:.2f} max=${hi:.2f}. "
                f"Vàng chưa bao giờ ra khỏi dải $500–$20.000. Dữ liệu này là giả."
            )
    if (df.high < df.low).any():
        raise ValueError("Dữ liệu hỏng: có nến high < low.")
    if (df.close <= 0).any():
        raise ValueError("Dữ liệu hỏng: có giá đóng cửa <= 0.")


def load_real_bars(symbol: str = "XAUUSDm", timeframe_name: str = "M15") -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Đọc nến đã lưu. Gọi `--fetch` trước nếu chưa có."""
    path = DATA_DIR / f"{symbol}_{timeframe_name}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Chưa có dữ liệu thật tại {path}. Chạy trước:\n"
            f"  python research/backtest_real_data.py --fetch"
        )
    df = pd.read_parquet(path).sort_values("time").reset_index(drop=True)
    _assert_prices_plausible(df, symbol)
    spec_path = DATA_DIR / f"{symbol}_{timeframe_name}_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else {
        "point": DEFAULT_POINT, "contract_size": DEFAULT_CONTRACT_SIZE,
        "volume_min": 0.01, "volume_step": 0.01,
    }
    return df, spec


# ======================================================================================
# 2. SINH TÍN HIỆU BẰNG CHÍNH POD PRODUCTION
# ======================================================================================
def generate_signals(
    df: pd.DataFrame,
    lookback: int = 200,
    account_equity: float = 10_000.0,
    cash_vol_budget: Optional[float] = None,
    use_buffering: bool = False,
    progress_every: int = 15_000,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Chạy `GoldScalpPod.generate_trade_proposal` trên từng nến.
    Hỗ trợ Carver Continuous Forecasting và Position Buffering để giảm turnover churn.

    Cửa sổ `lookback` phản ánh đúng hành vi live: MT5 trả về một lượng nến cố
    định, nên pod trong thực tế cũng chỉ thấy bấy nhiêu quá khứ.

    :return: (signals, lots_requested) — signal ∈ {1 BUY, -1 SELL, 0 HOLD}
    """
    pod_mod = importlib.import_module(
        "us_federation_quant.05_the_50_states.state_01_xauusd_scalp.pod"
    )
    pod = pod_mod.GoldScalpPod(allocated_capital=account_equity)

    n = len(df)
    signals = np.zeros(n, dtype=np.int8)
    lots = np.zeros(n, dtype=float)
    ohlc = df[["open", "high", "low", "close"]]

    current_pos_lot = 0.0
    current_sig = 0

    for i in range(lookback, n - 1):
        window = ohlc.iloc[i - lookback:i + 1]
        p = pod.generate_trade_proposal(
            window,
            account_equity=account_equity,
            cash_vol_budget=cash_vol_budget,
            current_position_lot=current_pos_lot,
        )

        if use_buffering and p.is_buffered:
            signals[i] = current_sig
            lots[i] = abs(current_pos_lot)
        else:
            sig = 1 if p.action == "BUY" else (-1 if p.action == "SELL" else 0)
            signals[i] = sig
            lots[i] = p.target_lots
            current_sig = sig
            current_pos_lot = p.target_lots * sig

        if progress_every and (i - lookback) % progress_every == 0:
            print(f"  ...nến {i:,}/{n:,}", flush=True)

    return signals, lots


# ======================================================================================
# 3. ENGINE KHỚP LỆNH
# ======================================================================================
@dataclass
class BacktestResult:
    label: str
    initial_capital: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    sharpe: float
    max_drawdown_pct: float
    num_trades: int
    win_rate_pct: float
    profit_factor: Optional[float]
    gross_pnl_before_costs: float
    total_costs: float
    account_blown: bool
    blown_at: Optional[str]
    years: float
    equity_curve: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))

    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop("equity_curve", None)
        return d


def run_backtest(
    df: pd.DataFrame,
    signals: np.ndarray,
    lots_requested: np.ndarray,
    spec: Dict[str, float],
    lookback: int = 200,
    initial_capital: float = 10_000.0,
    fixed_lot: Optional[float] = 0.01,
    slippage_points: float = DEFAULT_SLIPPAGE_POINTS,
    apply_spread: bool = True,
    hold_means_flat: bool = False,
    label: str = "",
) -> BacktestResult:
    """
    Khớp tín hiệu tại OPEN nến t+1 với spread thật và trượt giá.

    :param fixed_lot: None = dùng lot pod tự tính; số = lot cố định.
    :param hold_means_flat: True thì HOLD đóng vị thế; False thì giữ nguyên.
    :param apply_spread: False để đo lợi thế GỘP (trước phí) — dùng chẩn đoán.
    """
    point = float(spec.get("point", DEFAULT_POINT))
    contract = float(spec.get("contract_size", DEFAULT_CONTRACT_SIZE))
    o = df.open.values
    c = df.close.values
    spread_px = df.spread.values * point
    slip_px = slippage_points * point
    times = df.time.values

    equity = initial_capital
    position = 0
    lot = 0.0
    entry_px = 0.0
    peak = initial_capital
    max_dd = 0.0
    total_costs = 0.0
    trades: List[float] = []
    curve = np.full(len(df), np.nan)
    blown_at: Optional[str] = None

    for i in range(lookback, len(df) - 1):
        sig = int(signals[i])
        target = sig if (sig != 0 or hold_means_flat) else position

        if target != position:
            px = o[i + 1]
            sp = spread_px[i + 1] if apply_spread else 0.0

            if position != 0:  # đóng vị thế đang mở
                exit_px = (px - slip_px) if position > 0 else (px + sp + slip_px)
                pnl = (exit_px - entry_px) * position * lot * contract
                equity += pnl
                trades.append(pnl)
                total_costs += (sp + 2.0 * slip_px) * lot * contract

            if target != 0:  # mở vị thế mới
                lot = fixed_lot if fixed_lot is not None else max(0.01, round(lots_requested[i], 2))
                entry_px = (px + sp + slip_px) if target > 0 else (px - slip_px)
            else:
                lot = 0.0
            position = target

        mtm = equity + ((c[i + 1] - entry_px) * position * lot * contract if position != 0 else 0.0)
        curve[i] = mtm
        peak = max(peak, mtm)
        if peak > 0:
            # Chặn ở 1.0: không thể mất nhiều hơn toàn bộ vốn, và tài khoản đã
            # dừng ở 0 — không chặn thì một vị thế quá khổ cho ra "DD 25.000%".
            max_dd = max(max_dd, min(1.0, (peak - mtm) / peak))

        if mtm <= 0.0:
            blown_at = str(pd.Timestamp(times[i]))
            curve[i:] = 0.0
            equity = 0.0
            break

    return _summarize(
        df, curve, trades, total_costs, equity, initial_capital,
        lookback, max_dd, blown_at, label,
    )


def _summarize(df, curve, trades, total_costs, final_equity, initial_capital,
               lookback, max_dd, blown_at, label) -> BacktestResult:
    cv = pd.Series(curve).dropna()

    # Equity cuối kỳ là giá trị mark-to-market cuối cùng, KHÔNG phải equity đã
    # chốt: vị thế còn mở ở nến cuối vẫn mang lãi/lỗ, bỏ nó đi là báo cáo sai.
    if len(cv):
        final_equity = float(cv.iloc[-1])

    # Tính theo giây, không theo .days: kỳ ngắn hơn 1 ngày sẽ cho years = 0 và
    # làm nổ ZeroDivisionError ở công thức CAGR.
    years = (df.time.iloc[-1] - df.time.iloc[lookback]).total_seconds() / (365.25 * 24 * 3600)
    tr = np.array(trades) if trades else np.array([0.0])
    wins, losses = tr[tr > 0], tr[tr < 0]

    rets = cv.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(BARS_PER_YEAR_M15)) if rets.std() > 0 else 0.0

    total_ret = final_equity / initial_capital - 1.0
    cagr = ((final_equity / initial_capital) ** (1.0 / years) - 1.0) if final_equity > 0 and years > 0 else -1.0
    net = final_equity - initial_capital

    return BacktestResult(
        label=label,
        initial_capital=round(initial_capital, 2),
        final_equity=round(final_equity, 2),
        total_return_pct=round(total_ret * 100.0, 2),
        cagr_pct=round(cagr * 100.0, 2),
        sharpe=round(sharpe, 2),
        max_drawdown_pct=round(max_dd * 100.0, 2),
        num_trades=len(trades),
        win_rate_pct=round(len(wins) / len(trades) * 100.0, 2) if trades else 0.0,
        profit_factor=round(float(wins.sum() / abs(losses.sum())), 3) if len(losses) and losses.sum() != 0 else None,
        gross_pnl_before_costs=round(net + total_costs, 2),
        total_costs=round(total_costs, 2),
        account_blown=blown_at is not None,
        blown_at=blown_at,
        years=round(years, 2),
        equity_curve=curve,
    )


def buy_and_hold_benchmark(df, spec, lookback=200, lot=0.01, initial_capital=10_000.0) -> BacktestResult:
    """Chuẩn so sánh khớp khối lượng: mua 1 lần ở đầu kỳ, giữ tới cuối."""
    point = float(spec.get("point", DEFAULT_POINT))
    contract = float(spec.get("contract_size", DEFAULT_CONTRACT_SIZE))
    entry = df.open.values[lookback] + df.spread.values[lookback] * point
    pnl = (df.close.values[-1] - entry) * lot * contract
    years = (df.time.iloc[-1] - df.time.iloc[lookback]).total_seconds() / (365.25 * 24 * 3600)
    final = initial_capital + pnl
    cagr = ((final / initial_capital) ** (1.0 / years) - 1.0) if final > 0 and years > 0 else 0.0
    return BacktestResult(
        label=f"BENCHMARK Mua & Giữ ({lot} lot)",
        initial_capital=initial_capital, final_equity=round(final, 2),
        total_return_pct=round(pnl / initial_capital * 100.0, 2),
        cagr_pct=round(cagr * 100.0, 2),
        sharpe=0.0, max_drawdown_pct=0.0, num_trades=1, win_rate_pct=0.0,
        profit_factor=None, gross_pnl_before_costs=round(pnl, 2), total_costs=0.0,
        account_blown=False, blown_at=None, years=round(years, 2),
    )


def edge_significance(df, signals, spec, lookback=200, lot=0.01) -> Dict[str, float]:
    """
    Kiểm định t một mẫu trên PnL từng lệnh TRƯỚC phí.

    Đây là câu hỏi duy nhất đáng hỏi trước khi tinh chỉnh bất cứ ngưỡng nào:
    lợi thế gộp có phân biệt được với 0 hay không. Nếu không, mọi tối ưu chỉ là
    overfit — và kết quả 2026-09-26 cho State_01 là p = 0,436.
    """
    from scipy import stats

    point = float(spec.get("point", DEFAULT_POINT))
    contract = float(spec.get("contract_size", DEFAULT_CONTRACT_SIZE))
    o = df.open.values
    pos, entry, trades = 0, 0.0, []
    for i in range(lookback, len(df) - 1):
        target = int(signals[i]) if signals[i] != 0 else pos
        if target != pos:
            px = o[i + 1]
            if pos != 0:
                trades.append((px - entry) * pos * lot * contract)
            if target != 0:
                entry = px
            pos = target

    tr = np.array(trades) if trades else np.array([0.0])
    t_stat, p_value = stats.ttest_1samp(tr, 0.0) if len(tr) > 1 else (0.0, 1.0)
    avg_cost = (df.spread.mean() * point + 2 * DEFAULT_SLIPPAGE_POINTS * point) * lot * contract

    return {
        "num_trades": len(trades),
        "mean_gross_pnl_per_trade": round(float(tr.mean()), 4),
        "std_pnl_per_trade": round(float(tr.std()), 4),
        "t_statistic": round(float(t_stat), 3),
        "p_value": round(float(p_value), 4),
        "has_significant_edge": bool(p_value < 0.05 and tr.mean() > 0),
        "avg_cost_per_trade": round(float(avg_cost), 4),
        "breakeven_coverage_pct": round(float(tr.mean() / avg_cost * 100.0), 1) if avg_cost > 0 else 0.0,
    }


# ======================================================================================
# 4. CLI
# ======================================================================================
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Backtest pod thật trên dữ liệu MT5 thật.")
    ap.add_argument("--fetch", action="store_true", help="Kéo nến mới từ MT5 terminal đang chạy")
    ap.add_argument("--symbol", default="XAUUSDm")
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--months", type=int, default=36)
    ap.add_argument("--lot", default="0.01", help="Số cố định, hoặc 'auto' để dùng sizing của pod")
    ap.add_argument("--capital", type=float, default=10_000.0)
    ap.add_argument("--lookback", type=int, default=200)
    ap.add_argument("--slippage-points", type=float, default=DEFAULT_SLIPPAGE_POINTS)
    ap.add_argument("--carver", action="store_true", help="Bật Carver Systematic Sizing & Trade Buffering")
    ap.add_argument("--report", action="store_true", help="Ghi báo cáo JSON + Markdown vào logs/")
    args = ap.parse_args(argv)

    if args.fetch:
        print(f"📡 Đang kéo {args.symbol} {args.timeframe} thật từ MT5 terminal...")
        df, spec = fetch_real_bars(args.symbol, args.timeframe)
        print(f"   ✅ {len(df):,} nến | {df.time.min()} -> {df.time.max()}")
    else:
        df, spec = load_real_bars(args.symbol, args.timeframe)

    df = df[df.time >= df.time.max() - pd.DateOffset(months=args.months)].reset_index(drop=True)
    print(f"\n📊 DỮ LIỆU THẬT: {len(df):,} nến {args.timeframe} | "
          f"{df.time.min():%Y-%m-%d} -> {df.time.max():%Y-%m-%d}")
    print(f"   Giá: ${df.close.min():,.2f} - ${df.close.max():,.2f} | "
          f"spread TB {df.spread.mean():.1f} points")

    print(f"\n🧮 Sinh tín hiệu bằng GoldScalpPod production (cửa sổ {args.lookback} nến)...")
    signals, lots = generate_signals(df, args.lookback, args.capital)
    n_buy, n_sell, n_hold = int((signals == 1).sum()), int((signals == -1).sum()), int((signals == 0).sum())
    print(f"   [BASELINE] BUY={n_buy:,} SELL={n_sell:,} HOLD={n_hold:,} "
          f"-> ở ngoài thị trường chỉ {n_hold / len(signals) * 100:.2f}% thời gian")

    fixed_lot = None if str(args.lot).lower() == "auto" else float(args.lot)
    results: List[BacktestResult] = []
    for hold_flat in (False, True):
        mode = "HOLD=đóng" if hold_flat else "HOLD=giữ"
        lot_lbl = "lot pod tự tính" if fixed_lot is None else f"lot {fixed_lot}"
        results.append(run_backtest(
            df, signals, lots, spec, args.lookback, args.capital, fixed_lot,
            args.slippage_points, True, hold_flat, f"{lot_lbl} / {mode}"))

    # Kịch bản Carver Systematic Sizing & Position Buffering
    if args.carver:
        daily_cash_vol = float(args.capital * 0.16 / 16.0) # 16% annual vol target -> ~100 USD/day
        print(f"\n🦅 [CARVER ENGINE] Đang sinh tín hiệu với Continuous Forecasting & Trade Buffering (Budget: ${daily_cash_vol:,.2f}/ngày)...")
        c_signals, c_lots = generate_signals(
            df,
            args.lookback,
            args.capital,
            cash_vol_budget=daily_cash_vol,
            use_buffering=True,
        )
        c_buy, c_sell, c_hold = int((c_signals == 1).sum()), int((c_signals == -1).sum()), int((c_signals == 0).sum())
        print(f"   [CARVER BUFFER] BUY={c_buy:,} SELL={c_sell:,} HOLD={c_hold:,} "
              f"-> ở ngoài thị trường {c_hold / len(c_signals) * 100:.2f}% thời gian")
        carver_res = run_backtest(
            df, c_signals, c_lots, spec, args.lookback, args.capital, None,
            args.slippage_points, True, False, "CARVER Vol Target + Buffer (+/-10%)"
        )
        results.append(carver_res)

    # Phân rã chi phí: cùng tín hiệu, bật/tắt phí.
    diag_lot = fixed_lot if fixed_lot is not None else 0.01
    no_cost = run_backtest(df, signals, lots, spec, args.lookback, args.capital,
                           diag_lot, 0.0, False, False, f"lot {diag_lot} / KHÔNG phí (lý tưởng)")
    results.append(no_cost)
    results.append(buy_and_hold_benchmark(df, spec, args.lookback, diag_lot, args.capital))

    cols = ["label", "final_equity", "total_return_pct", "cagr_pct", "sharpe",
            "max_drawdown_pct", "num_trades", "win_rate_pct", "profit_factor",
            "total_costs", "gross_pnl_before_costs", "account_blown"]
    table = pd.DataFrame([r.to_dict() for r in results])[cols]
    print("\n" + "=" * 118)
    print(f"KẾT QUẢ BACKTEST {args.months} THÁNG — {args.symbol} {args.timeframe} DỮ LIỆU THẬT "
          f"({results[0].years} năm)")
    print("=" * 118)
    print(table.to_string(index=False))

    sig_stats = edge_significance(df, signals, spec, args.lookback, diag_lot)
    print("\n" + "-" * 118)
    print("KIỂM ĐỊNH LỢI THẾ GỘP (trước phí) — câu hỏi duy nhất đáng hỏi trước khi tinh chỉnh:")
    for k, v in sig_stats.items():
        print(f"   {k:<32} {v}")
    verdict = ("✅ CÓ lợi thế thống kê" if sig_stats["has_significant_edge"]
               else "❌ KHÔNG có lợi thế thống kê — tinh chỉnh ngưỡng chỉ là overfit")
    print(f"   => {verdict}")

    if args.report:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "data_source": "MT5 terminal (giá thật)",
            "is_synthetic": False,
            "symbol": args.symbol, "timeframe": args.timeframe,
            "months": args.months, "bars": len(df),
            "period_start": str(df.time.min()), "period_end": str(df.time.max()),
            "signal_distribution": {"BUY": n_buy, "SELL": n_sell, "HOLD": n_hold},
            "edge_significance": sig_stats,
            "results": [r.to_dict() for r in results],
        }
        out = LOG_DIR / f"real_backtest_{args.symbol}_{args.months}m.json"
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n💾 Đã ghi báo cáo -> {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
