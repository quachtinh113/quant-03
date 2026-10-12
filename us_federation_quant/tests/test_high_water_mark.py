"""
Kiểm thử High-Water Mark Tracker & thang drawdown thể chế.

MỖI CA DƯỚI ĐÂY LÀ MỘT LỖI ĐÃ GẶP THẬT — 2026-09-26
---------------------------------------------------
`live_federation_runner.py` nạp `(equity - balance) / balance` vào thang drawdown.
Đó là lãi/lỗ trôi nổi của lệnh đang mở, không phải drawdown từ đỉnh. Tài khoản
có thể lỗ 30% từ đỉnh mà chỉ số đó vẫn bằng 0 khi không còn lệnh mở, nên
kill-switch -7.5% không bao giờ kích hoạt.

`test_lo_da_chot_van_kich_hoat_kill_switch` là ca hồi quy trực tiếp cho lỗi đó.
"""

import importlib
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from us_federation_quant.core.high_water_mark import (  # noqa: E402
    HighWaterMarkTracker,
    HighWaterMarkState,
)

_titan = importlib.import_module("us_federation_quant.04_federal_reserve.quad_titan_engine")
WallStreetPodDefense = _titan.WallStreetPodDefense


@pytest.fixture
def tracker(tmp_path):
    """Tracker ghi vào thư mục tạm, không đụng logs/ thật."""
    return HighWaterMarkTracker(bot_id="test_bot", logs_dir=str(tmp_path))


# ==============================================================================
# 1. HÀNH VI CƠ BẢN CỦA ĐỈNH VỐN
# ==============================================================================
def test_lan_dau_tien_la_dinh_va_drawdown_bang_khong(tracker):
    st = tracker.update(10_000.0)
    assert st.high_water_mark_usd == 10_000.0
    assert st.drawdown_fraction == 0.0
    assert st.is_new_peak is True
    assert st.is_at_peak is True


def test_equity_tang_thi_nang_dinh(tracker):
    tracker.update(10_000.0)
    st = tracker.update(12_500.0)
    assert st.high_water_mark_usd == 12_500.0
    assert st.drawdown_fraction == 0.0
    assert st.is_new_peak is True


def test_equity_giam_thi_KHONG_ha_dinh(tracker):
    tracker.update(10_000.0)
    st = tracker.update(9_000.0)
    assert st.high_water_mark_usd == 10_000.0, "Đỉnh không được hạ theo equity"
    assert st.drawdown_fraction == pytest.approx(-0.10)
    assert st.drawdown_pct == pytest.approx(-10.0)
    assert st.is_new_peak is False
    assert st.is_at_peak is False


def test_drawdown_tinh_tu_dinh_chu_khong_phai_tu_diem_truoc(tracker):
    tracker.update(10_000.0)
    tracker.update(12_000.0)   # đỉnh mới
    st = tracker.update(11_100.0)
    # Từ đỉnh 12,000 -> 11,100 là -7.5%, KHÔNG phải +11% so với 10,000.
    assert st.drawdown_fraction == pytest.approx(-0.075)


def test_drawdown_luon_am_hoac_bang_khong(tracker):
    for eq in [10_000.0, 12_000.0, 11_000.0, 15_000.0, 14_999.99, 20_000.0]:
        st = tracker.update(eq)
        assert st.drawdown_fraction <= 0.0, f"Drawdown phải <= 0, gặp {st.drawdown_fraction}"


# ==============================================================================
# 2. BỀN VỮNG QUA LẦN KHỞI ĐỘNG LẠI — LÝ DO CHÍNH PHẢI GHI XUỐNG ĐĨA
# ==============================================================================
def test_restart_KHONG_xoa_drawdown_dang_co(tmp_path):
    """
    Nếu HWM chỉ nằm trong RAM, restart sẽ đặt đỉnh về equity hiện tại và xoá sạch
    drawdown — vô hiệu hoá thang bậc đúng lúc cần nó nhất. Restart sau một chuỗi
    lỗ là tình huống thường gặp nhất.
    """
    t1 = HighWaterMarkTracker(bot_id="b", logs_dir=str(tmp_path))
    t1.update(10_000.0)
    t1.update(9_200.0)          # đang lỗ -8% từ đỉnh

    t2 = HighWaterMarkTracker(bot_id="b", logs_dir=str(tmp_path))   # restart
    st = t2.update(9_200.0)
    assert st.high_water_mark_usd == 10_000.0, "Đỉnh phải sống sót qua restart"
    assert st.drawdown_fraction == pytest.approx(-0.08)


def test_bot_id_khac_nhau_khong_dung_chung_dinh(tmp_path):
    HighWaterMarkTracker(bot_id="bot_a", logs_dir=str(tmp_path)).update(50_000.0)
    st = HighWaterMarkTracker(bot_id="bot_b", logs_dir=str(tmp_path)).update(10_000.0)
    assert st.high_water_mark_usd == 10_000.0


def test_file_trang_thai_hong_thi_khoi_tao_lai_chu_khong_crash(tmp_path):
    f = tmp_path / "high_water_mark_b.json"
    f.write_text("{ day khong phai JSON hop le", encoding="utf-8")
    t = HighWaterMarkTracker(bot_id="b", logs_dir=str(tmp_path))
    st = t.update(10_000.0)
    assert st.high_water_mark_usd == 10_000.0


def test_hwm_am_trong_file_bi_tu_choi(tmp_path):
    f = tmp_path / "high_water_mark_b.json"
    f.write_text(json.dumps({"high_water_mark_usd": -5.0}), encoding="utf-8")
    t = HighWaterMarkTracker(bot_id="b", logs_dir=str(tmp_path))
    assert t.high_water_mark_usd is None
    assert t.update(8_000.0).high_water_mark_usd == 8_000.0


def test_file_luu_doc_lai_duoc_va_dung_so(tracker):
    tracker.update(10_000.0)
    tracker.update(9_500.0)
    data = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert data["high_water_mark_usd"] == 10_000.0
    assert data["equity_usd"] == 9_500.0
    assert data["drawdown_fraction"] == pytest.approx(-0.05)
    assert data["bot_id"] == "test_bot"


# ==============================================================================
# 3. TRƯỜNG HỢP BIÊN
# ==============================================================================
def test_equity_bang_khong_la_chay_tai_khoan(tracker):
    tracker.update(10_000.0)
    st = tracker.update(0.0)
    assert st.drawdown_fraction == -1.0
    assert st.drawdown_pct == -100.0
    assert st.high_water_mark_usd == 10_000.0, "Cháy tài khoản không được hạ đỉnh"


def test_equity_am_khong_lam_crash(tracker):
    tracker.update(10_000.0)
    st = tracker.update(-250.0)
    assert st.drawdown_fraction == -1.0


def test_reset_dung_khi_nap_rut_von(tracker):
    tracker.update(10_000.0)
    tracker.update(9_000.0)
    st = tracker.reset(20_000.0)      # nạp thêm vốn
    assert st.high_water_mark_usd == 20_000.0
    assert st.drawdown_fraction == 0.0


# ==============================================================================
# 4. TÍCH HỢP VỚI THANG DRAWDOWN — CA HỒI QUY CHO LỖI THẬT
# ==============================================================================
@pytest.mark.parametrize("equity,dd_mong_doi,trang_thai_mong_doi,kill_mong_doi", [
    (10_000.0,  0.000, "NORMAL_ACTIVE",             False),
    (9_800.0,  -0.020, "NORMAL_ACTIVE",             False),
    (9_700.0,  -0.030, "DELEVERAGE_50_PERCENT",     False),
    (9_600.0,  -0.040, "DELEVERAGE_50_PERCENT",     False),
    (9_500.0,  -0.050, "QUARANTINE_LOCKED",         False),
    (9_300.0,  -0.070, "QUARANTINE_LOCKED",         False),
    (9_250.0,  -0.075, "NUCLEAR_KILL_SWITCH_ACTIVE", True),
    (9_000.0,  -0.100, "NUCLEAR_KILL_SWITCH_ACTIVE", True),
])
def test_thang_drawdown_kich_hoat_dung_bac(tracker, equity, dd_mong_doi,
                                           trang_thai_mong_doi, kill_mong_doi):
    tracker.update(10_000.0)
    st = tracker.update(equity)
    assert st.drawdown_fraction == pytest.approx(dd_mong_doi)
    _, pod_status, nuclear = WallStreetPodDefense.enforce_drawdown_ladder(st.drawdown_fraction)
    assert pod_status == trang_thai_mong_doi
    assert nuclear is kill_mong_doi


def test_lo_da_chot_van_kich_hoat_kill_switch(tracker):
    """
    HỒI QUY CHO LỖI THẬT: với `(equity - balance) / balance`, một tài khoản đã lỗ
    chốt 10% từ đỉnh mà KHÔNG còn lệnh mở sẽ có equity == balance, tức chỉ số cũ
    bằng 0 và kill-switch im lặng. Đo từ HWM thì nó phải nổ.
    """
    tracker.update(10_000.0)          # đỉnh
    balance = equity = 9_000.0        # đã chốt lỗ, không còn lệnh mở

    chi_so_cu = (equity - balance) / balance
    assert chi_so_cu == 0.0
    _, _, kill_cu = WallStreetPodDefense.enforce_drawdown_ladder(min(0.0, chi_so_cu))
    assert kill_cu is False, "Đây chính là lỗi: cách cũ không thấy lỗ đã chốt"

    st = tracker.update(equity)
    assert st.drawdown_fraction == pytest.approx(-0.10)
    _, pod_status, kill_moi = WallStreetPodDefense.enforce_drawdown_ladder(st.drawdown_fraction)
    assert kill_moi is True, "Cách mới PHẢI kích hoạt kill-switch"
    assert pod_status == "NUCLEAR_KILL_SWITCH_ACTIVE"


def test_chuoi_lo_tich_luy_qua_nhieu_lenh_van_bi_bat(tracker):
    """Lỗ nhỏ lặp lại nhiều lần vẫn phải cộng dồn thành drawdown từ đỉnh."""
    tracker.update(10_000.0)
    eq = 10_000.0
    kill_fired = False
    for _ in range(20):
        eq -= 50.0                     # mỗi lệnh lỗ $50, chốt ngay
        st = tracker.update(eq)
        _, _, kill = WallStreetPodDefense.enforce_drawdown_ladder(st.drawdown_fraction)
        if kill:
            kill_fired = True
            break
    assert kill_fired, "20 lệnh lỗ $50 = -10% từ đỉnh, phải kích hoạt kill-switch"
    assert eq == pytest.approx(9_250.0), "Phải nổ đúng tại bậc -7.5%"


def test_hoi_phuc_roi_lo_lai_do_tu_dinh_cao_nhat(tracker):
    tracker.update(10_000.0)
    tracker.update(9_500.0)           # -5%
    tracker.update(11_000.0)          # đỉnh mới
    st = tracker.update(10_175.0)     # -7.5% tính từ 11,000
    assert st.drawdown_fraction == pytest.approx(-0.075)
    _, _, kill = WallStreetPodDefense.enforce_drawdown_ladder(st.drawdown_fraction)
    assert kill is True, "Đỉnh mới cao hơn nên ngưỡng tuyệt đối cũng cao hơn"


def test_state_la_immutable(tracker):
    st = tracker.update(10_000.0)
    assert isinstance(st, HighWaterMarkState)
    with pytest.raises(Exception):
        st.high_water_mark_usd = 999.0  # type: ignore[misc]
