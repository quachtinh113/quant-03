"""
Kiểm thử engine backtest dữ liệu thật.

PHẠM VI
-------
Ở đây kiểm CƠ CHẾ của engine (khớp lệnh, chi phí, chốt an toàn dữ liệu), KHÔNG
kiểm hiệu suất chiến lược. Vì vậy nến trong file này được dựng thủ công cho
từng ca — đó là hợp lệ với test cơ chế, và khác hoàn toàn với việc dựng nến giả
rồi báo cáo như kết quả giao dịch thật (chính là lỗi của
`run_36_month_system_backtest.py`).

Ca quan trọng nhất: `test_khop_lenh_tai_OPEN_nen_sau_khong_phai_CLOSE_nen_tin_hieu`
— chốt Điều ② Hiến pháp (không nhìn tương lai) ở tầng khớp lệnh.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from us_federation_quant.research.backtest_real_data import (  # noqa: E402
    _assert_prices_plausible,
    buy_and_hold_benchmark,
    edge_significance,
    run_backtest,
)

SPEC = {"point": 0.001, "contract_size": 100.0, "volume_min": 0.01, "volume_step": 0.01}


def make_bars(closes, spread_points=0.0, opens=None):
    """Dựng DataFrame nến M15 tối thiểu cho test cơ chế."""
    n = len(closes)
    closes = np.asarray(closes, dtype=float)
    o = np.asarray(opens, dtype=float) if opens is not None else closes.copy()
    return pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC"),
        "open": o,
        "high": np.maximum(o, closes) + 1.0,
        "low": np.minimum(o, closes) - 1.0,
        "close": closes,
        "volume": np.full(n, 100.0),
        "spread": np.full(n, float(spread_points)),
    })


# ==============================================================================
# 1. CHỐT KHÔNG NHÌN TƯƠNG LAI — ĐIỀU ② HIẾN PHÁP
# ==============================================================================
def test_khop_lenh_tai_OPEN_nen_sau_khong_phai_CLOSE_nen_tin_hieu():
    """
    Tín hiệu sinh ở nến t phải khớp tại OPEN nến t+1. Nếu engine khớp tại CLOSE
    nến t, nó đã dùng thông tin của chính nến sinh tín hiệu — tức nhìn tương lai,
    và mọi kết quả sẽ bị thổi phồng.

    Dựng nến để hai cách cho ra số khác nhau rõ rệt: close nến tín hiệu = 2000,
    nhưng open nến sau nhảy lên 2050 (gap). Khớp đúng thì vào ở 2050.
    """
    lookback = 2
    closes = [2000.0, 2000.0, 2000.0, 2000.0, 2100.0, 2100.0]
    opens  = [2000.0, 2000.0, 2000.0, 2050.0, 2100.0, 2100.0]
    df = make_bars(closes, spread_points=0.0, opens=opens)

    sig = np.zeros(len(df), dtype=np.int8)
    sig[2] = 1  # BUY tại nến 2 -> phải vào ở open nến 3 = 2050

    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=lookback,
                     initial_capital=10_000.0, fixed_lot=0.01,
                     slippage_points=0.0, apply_spread=False, label="t+1")

    # Vào 2050, thoát/đánh giá ở close cuối 2100 -> +50 USD/oz * 1 oz = +$50.
    # Nếu sai (vào ở close nến 2 = 2000) sẽ ra +$100.
    assert r.final_equity == pytest.approx(10_050.0, abs=0.01), (
        "Engine phải khớp tại OPEN nến t+1 (2050), không phải CLOSE nến t (2000)"
    )


def test_tin_hieu_o_nen_cuoi_khong_duoc_khop():
    """Nến cuối không có nến t+1 để khớp, nên tín hiệu ở đó phải bị bỏ qua."""
    df = make_bars([2000.0] * 5)
    sig = np.zeros(len(df), dtype=np.int8)
    sig[len(df) - 1] = 1
    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     fixed_lot=0.01, slippage_points=0.0, apply_spread=False)
    assert r.num_trades == 0


# ==============================================================================
# 2. MÔ HÌNH CHI PHÍ
# ==============================================================================
def test_spread_bi_tinh_dung_MOT_lan_moi_vong_lenh():
    """
    Nến MT5 là giá BID: mua ở ASK (= open + spread), bán ở BID (= open).
    Giá đi ngang thì lỗ đúng bằng 1 lần spread, không phải 2 lần.
    """
    df = make_bars([2000.0] * 8, spread_points=200.0)   # 200 pt * 0.001 = $0.20/oz
    sig = np.zeros(len(df), dtype=np.int8)
    sig[2] = 1      # mở long
    sig[4] = -1     # đảo chiều -> đóng long

    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     fixed_lot=0.01, slippage_points=0.0, apply_spread=True)

    # 0.01 lot * 100 = 1 oz. Lệnh long đầu lỗ đúng $0.20.
    assert r.num_trades == 1
    assert r.gross_pnl_before_costs == pytest.approx(0.0, abs=1e-6), \
        "Trước phí, giá đi ngang thì PnL gộp phải bằng 0"
    assert r.total_costs == pytest.approx(0.20, abs=1e-6)


def test_tat_phi_thi_khong_mat_dong_nao():
    df = make_bars([2000.0] * 8, spread_points=200.0)
    sig = np.zeros(len(df), dtype=np.int8)
    sig[2], sig[4] = 1, -1
    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     fixed_lot=0.01, slippage_points=0.0, apply_spread=False)
    assert r.total_costs == 0.0
    assert r.final_equity == pytest.approx(10_000.0, abs=1e-6)


def test_truot_gia_tinh_ca_hai_chieu():
    df = make_bars([2000.0] * 8, spread_points=0.0)
    sig = np.zeros(len(df), dtype=np.int8)
    sig[2], sig[4] = 1, -1
    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     fixed_lot=0.01, slippage_points=10.0, apply_spread=False)
    # 10 pt * 0.001 = $0.01/oz mỗi chiều, 2 chiều = $0.02 trên 1 oz.
    assert r.total_costs == pytest.approx(0.02, abs=1e-9)


def test_phi_lon_hon_bien_dong_thi_lo_du_gia_di_dung_huong():
    """Bài học cốt lõi từ State_01: đúng hướng vẫn lỗ nếu phí vượt lợi thế."""
    closes = [2000.0, 2000.0, 2000.0, 2000.05, 2000.05, 2000.05]
    df = make_bars(closes, spread_points=200.0)   # spread $0.20 >> lãi $0.05
    sig = np.zeros(len(df), dtype=np.int8)
    sig[2] = 1
    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     fixed_lot=0.01, slippage_points=0.0, apply_spread=True)
    assert r.final_equity < 10_000.0


# ==============================================================================
# 3. NGỮ NGHĨA HOLD
# ==============================================================================
def test_hold_giu_vi_the_thi_khong_phat_sinh_lenh_moi():
    df = make_bars(np.linspace(2000.0, 2100.0, 12))
    sig = np.zeros(len(df), dtype=np.int8)
    sig[2] = 1      # còn lại toàn HOLD
    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     fixed_lot=0.01, slippage_points=0.0, apply_spread=False,
                     hold_means_flat=False)
    assert r.num_trades == 0, "Vị thế vẫn đang mở tới hết kỳ nên chưa chốt lệnh nào"
    assert r.final_equity > 10_000.0


def test_hold_dong_vi_the_thi_chot_lenh():
    df = make_bars(np.linspace(2000.0, 2100.0, 12))
    sig = np.zeros(len(df), dtype=np.int8)
    sig[2] = 1
    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     fixed_lot=0.01, slippage_points=0.0, apply_spread=False,
                     hold_means_flat=True)
    assert r.num_trades == 1


# ==============================================================================
# 4. PHÁT HIỆN CHÁY TÀI KHOẢN
# ==============================================================================
def test_chay_tai_khoan_duoc_phat_hien_va_dung_lai():
    """Lot pod tự tính đã làm cháy tài khoản thật ngày 2024-02-20 — phải bắt được."""
    closes = [2000.0, 2000.0, 2000.0, 1000.0, 500.0, 100.0]
    df = make_bars(closes)
    sig = np.zeros(len(df), dtype=np.int8)
    sig[2] = 1
    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     initial_capital=1_000.0, fixed_lot=5.0,
                     slippage_points=0.0, apply_spread=False)
    assert r.account_blown is True
    assert r.blown_at is not None
    assert r.final_equity == 0.0
    assert r.total_return_pct == -100.0
    assert r.max_drawdown_pct == pytest.approx(100.0, abs=0.01)


def test_khong_chay_thi_co_blown_bang_false():
    df = make_bars([2000.0] * 8)
    sig = np.zeros(len(df), dtype=np.int8)
    sig[2] = 1
    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     fixed_lot=0.01, slippage_points=0.0, apply_spread=False)
    assert r.account_blown is False
    assert r.blown_at is None


# ==============================================================================
# 5. CHỐT AN TOÀN DỮ LIỆU — CHỐNG LẶP LẠI THẢM HOẠ data_lake
# ==============================================================================
def test_tu_choi_gia_vang_kieu_data_lake():
    """
    `data_lake` có vàng "giảm" từ $2.649 xuống $96,60. Không ai kiểm tra, nên mọi
    báo cáo dựng trên đó vô nghĩa suốt nhiều tháng. Chốt này phải bắt được.
    """
    df = make_bars(np.linspace(2649.0, 96.6, 100))
    with pytest.raises(ValueError, match="không khả tín"):
        _assert_prices_plausible(df, "XAUUSDm")


def test_chap_nhan_gia_vang_that():
    df = make_bars(np.linspace(1875.0, 4286.0, 100))
    _assert_prices_plausible(df, "XAUUSDm")   # không được nổ


def test_tu_choi_gia_vang_qua_cao():
    df = make_bars(np.linspace(2000.0, 50_000.0, 100))
    with pytest.raises(ValueError, match="không khả tín"):
        _assert_prices_plausible(df, "XAUUSDm")


def test_tu_choi_nen_high_nho_hon_low():
    df = make_bars([2000.0] * 5)
    df.loc[2, "high"] = 1900.0
    df.loc[2, "low"] = 2100.0
    with pytest.raises(ValueError, match="high < low"):
        _assert_prices_plausible(df, "XAUUSDm")


def test_tu_choi_gia_dong_cua_am():
    df = make_bars([2000.0, 2000.0, -5.0, 2000.0, 2000.0])
    with pytest.raises(ValueError):
        _assert_prices_plausible(df, "XAUUSDm")


def test_chot_an_toan_bo_qua_symbol_khong_phai_vang():
    """Dải $500–$20.000 chỉ áp cho vàng; EURUSD ở 1.08 là bình thường."""
    df = make_bars(np.linspace(1.05, 1.12, 50))
    _assert_prices_plausible(df, "EURUSDm")


# ==============================================================================
# 6. CHUẨN SO SÁNH & KIỂM ĐỊNH LỢI THẾ
# ==============================================================================
def test_benchmark_mua_va_giu_tinh_dung():
    df = make_bars([2000.0] * 3 + [2100.0] * 3, spread_points=0.0)
    r = buy_and_hold_benchmark(df, SPEC, lookback=2, lot=0.01, initial_capital=10_000.0)
    # Vào ở open nến 2 = 2000, ra ở close cuối = 2100 -> +$100 trên 1 oz.
    assert r.final_equity == pytest.approx(10_100.0, abs=0.01)
    assert r.num_trades == 1


def test_kiem_dinh_loi_the_bat_duoc_truong_hop_khong_co_loi_the():
    """Tín hiệu ngẫu nhiên trên bước ngẫu nhiên phải cho p-value không đáng kể."""
    rng = np.random.default_rng(42)
    closes = 2000.0 + np.cumsum(rng.normal(0, 1.0, 3000))
    df = make_bars(closes, spread_points=200.0)
    sig = rng.choice([-1, 0, 1], size=len(df)).astype(np.int8)
    s = edge_significance(df, sig, SPEC, lookback=200, lot=0.01)
    assert s["has_significant_edge"] is False
    assert s["p_value"] > 0.05


def test_kiem_dinh_loi_the_bat_duoc_truong_hop_CO_loi_the():
    """Tín hiệu hoàn hảo (biết trước nến sau) phải cho lợi thế rất đáng kể."""
    rng = np.random.default_rng(7)
    closes = 2000.0 + np.cumsum(rng.normal(0, 1.0, 3000))
    df = make_bars(closes, spread_points=0.0)
    o = df.open.values
    sig = np.zeros(len(df), dtype=np.int8)
    for i in range(200, len(df) - 2):
        sig[i] = 1 if o[i + 2] > o[i + 1] else -1   # tiên tri, chỉ dùng để kiểm định
    s = edge_significance(df, sig, SPEC, lookback=200, lot=0.01)
    assert s["has_significant_edge"] is True
    assert s["p_value"] < 0.01
    assert s["mean_gross_pnl_per_trade"] > 0


def test_ket_qua_co_day_du_truong_phan_ra_chi_phi():
    df = make_bars(np.linspace(2000.0, 2050.0, 20), spread_points=200.0)
    sig = np.zeros(len(df), dtype=np.int8)
    sig[2], sig[8], sig[14] = 1, -1, 1
    r = run_backtest(df, sig, np.zeros(len(df)), SPEC, lookback=2,
                     fixed_lot=0.01, slippage_points=10.0, apply_spread=True)
    d = r.to_dict()
    for k in ("total_costs", "gross_pnl_before_costs", "num_trades", "sharpe",
              "max_drawdown_pct", "profit_factor", "account_blown", "years"):
        assert k in d, f"Thiếu trường {k}"
    assert "equity_curve" not in d, "Đường cong vốn không được vào JSON báo cáo"
    # Ròng = gộp - phí, theo đúng định nghĩa.
    net = r.final_equity - r.initial_capital
    assert net == pytest.approx(r.gross_pnl_before_costs - r.total_costs, abs=0.01)
