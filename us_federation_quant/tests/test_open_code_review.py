"""
Kiểm thử Cổng Kiểm Toán Mã Nguồn Định Lượng trên phạm vi US Federation Quant.

LỊCH SỬ
-------
File này đã **chết từ trước ngày 21/09/2026**: nó import
`hedge_fund_os.audit.open_code_review_runner`, một cây thư mục đã bị dọn vào
`_backups/legacy_bots/`. Vì nằm ở `us_federation_quant/tests/` chứ không ở `tests/`
gốc, lệnh `pytest tests/` thường dùng không quét tới, nên lỗi không lộ ra.

Nay trỏ vào module đã khôi phục tại
`quant_research_hub/03_alpha_factory/open_code_review_auditor.py`.

PHÂN CÔNG KIỂM THỬ
------------------
File này chỉ kiểm định **cổng chạy trên mã sản xuất thật của Liên bang** — phần mà bản
gốc gọi là "production codebase quant gate", trước đây nhắm vào `hedge_fund_os/` và
`All_Fleet_Bot/`.

Kiểm thử từng luật (bí mật, nuốt ngoại lệ, chia cho 0, cô lập magic, nghịch đảo ma trận)
nằm ở `tests/test_restored_alpha_factory_modules.py` để tránh trùng lặp.
"""

import importlib
from pathlib import Path

import pytest

_OCR = importlib.import_module(
    "quant_research_hub.03_alpha_factory.open_code_review_auditor"
)
QuantCodeReviewAuditor = _OCR.QuantCodeReviewAuditor

_WORKSPACE = Path(__file__).resolve().parent.parent.parent
_FEDERATION = _WORKSPACE / "us_federation_quant"


@pytest.fixture(scope="module")
def federation_report():
    """Kiểm toán một lần, dùng lại cho mọi bài test trong file."""
    auditor = QuantCodeReviewAuditor(root_dir=_WORKSPACE)
    return auditor.audit_directory(_FEDERATION)


def test_federation_code_is_actually_scanned(federation_report):
    """Đề phòng luật loại trừ quá rộng khiến cổng 'qua' vì không quét gì cả."""
    assert federation_report.files_scanned > 20, (
        f"Chỉ quét được {federation_report.files_scanned} file trong us_federation_quant "
        f"— nghi danh sách loại trừ nuốt mất mã sản xuất."
    )


def test_no_hardcoded_credentials_in_production(federation_report):
    """
    Thông tin đăng nhập MT5 phải đọc từ biến môi trường. Tài khoản Exness thật nằm sau
    những khóa này — đây là hạng mục nghiêm trọng nhất của cả bộ kiểm toán.
    """
    leaks = [i for i in federation_report.issues
             if i.category == "SECRET_LEAK" and not i.in_test_code]
    assert not leaks, f"Nghi rò rỉ thông tin đăng nhập: {[str(i) for i in leaks]}"


def test_magic_numbers_go_through_the_registry(federation_report):
    """
    50 Tiểu bang dùng dải magic 260901–260950. Magic viết cứng không qua sổ đăng ký
    khiến hai bot cùng quản một vị thế — lệnh đóng của bot này đóng vị thế của bot kia.
    """
    collisions = [i for i in federation_report.issues
                  if i.category == "MAGIC_ISOLATION" and not i.in_test_code]
    assert not collisions, (
        f"Magic viết cứng trong mã sản xuất: {[str(i) for i in collisions]}"
    )


def test_production_quant_gate_passes(federation_report):
    """Cổng tổng: không có vấn đề nghiêm trọng nào trong mã sản xuất của Liên bang."""
    critical = [i for i in federation_report.critical if not i.in_test_code]
    assert federation_report.passed_quant_gate, (
        f"{len(critical)} vấn đề nghiêm trọng: {[str(i) for i in critical[:5]]}"
    )


def test_archive_tree_is_never_touched(federation_report):
    """
    `.claude/settings.json` cấm đọc `**/_backups/**`. Bộ kiểm toán phải tôn trọng ranh
    giới đó — bản gốc dùng glob không loại trừ và sẽ bò thẳng vào đấy.
    """
    for issue in federation_report.issues:
        assert "_backups" not in issue.file_path
