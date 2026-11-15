"""Golden đường dẫn (Bước 1 của đợt tổ chức lại 5 thư mục): đóng băng MỌI đường dẫn hệ thống mà mã dựng từ vị trí file.

Ghi: LOG_DIR, file khóa tiến trình, đường dẫn .env, ledger/vault/HWM/idempotency/heartbeat/ngân sách AI/registry cách ly/log file,
cùng các điểm vào bên ngoài (start_bot.bat, service, script watchdog) và sự tồn tại của file cấu hình.
Mọi đường dẫn chuẩn hóa thành chuỗi POSIX TƯƠNG ĐỐI so với thư mục repo (cha của gói `us_federation_quant`).
Không ghi file, không mkdir, không mở SQLite, không đọc .env: mọi thứ có tác dụng phụ đều bị vô hiệu bằng patch.
Sinh fixture từ cấu trúc TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_paths_resolve.py
Sau khi di chuyển, fixture phải được so với bảng đổi tiền tố đã duyệt (xem báo cáo), không tự sinh lại mù quáng.
"""
import builtins
import json
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import us_federation_quant.core.live_federation_runner as runner
import us_federation_quant.core.institutional_governance_rules as gov
import us_federation_quant.layers.l3_sizing as l3
import us_federation_quant.layers.l4_risk as l4
import us_federation_quant.layers.l6_telemetry as l6

PKG = Path(runner.__file__).resolve().parent.parent          # thư mục gói us_federation_quant (cấu trúc cũ: cha của Document/)
REPO = PKG.parent
GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "paths.json")
_real_open = builtins.open


def _rel(p):
    if p is None:
        return None
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return "OUTSIDE_REPO:" + str(p)


def _guard_open(file, mode="r", *a, **k):
    if any(c in str(mode) for c in "wax+"):
        raise AssertionError(f"test không được ghi file: {file}")
    return _real_open(file, mode, *a, **k)


def _no_side_effects():
    """patch: không mkdir, không makedirs, không SQLite, không ghi file; Path.exists -> False để các _load_* bỏ qua việc đọc."""
    return [patch.object(Path, "mkdir", lambda *a, **k: None),
            patch("os.makedirs", lambda *a, **k: None),
            patch("sqlite3.connect", return_value=MagicMock()),
            patch("builtins.open", _guard_open),
            patch.object(Path, "exists", lambda self: False)]


def _under_patches(fn):
    ps = _no_side_effects()
    for p in ps:
        p.start()
    try:
        return fn()
    finally:
        for p in reversed(ps):
            p.stop()


def _defaults():
    out = {}
    out["l4.ColdStorageOOSVault.vault_dir"] = _rel(l4.ColdStorageOOSVault().vault_dir)
    out["l4.ImmutableTrialLedger.ledger_file_path"] = _rel(l4.ImmutableTrialLedger().ledger_file_path)
    out["l4.HighWaterMarkTracker.state_file"] = _rel(l4.HighWaterMarkTracker(bot_id="b").state_file)
    out["l4.HighWaterMarkTracker.state_file(logs_dir=LOG_DIR)"] = _rel(l4.HighWaterMarkTracker(bot_id="b", logs_dir=str(runner.LOG_DIR)).state_file)
    out["l4.IdempotencyRegistry.db_path(default)"] = _rel(l4.IdempotencyRegistry().db_path)
    out["l4.SupremeCourtCircuitBreakerManager.registry_path"] = _rel(l4.SupremeCourtCircuitBreakerManager().registry_path)
    out["gov.HamiltonColdVaultManager.ledger_path"] = _rel(gov.HamiltonColdVaultManager().ledger_path)
    hb = l6.FleetHeartbeat(bot_id="b")
    out["l6.FleetHeartbeat(default).heartbeat_file"] = _rel(hb.heartbeat_file)
    out["l6.FleetHeartbeat(default).audit_log_file"] = _rel(hb.audit_log_file)
    hb2 = l6.FleetHeartbeat(bot_id="b", logs_dir=str(runner.LOG_DIR))
    out["l6.FleetHeartbeat(LOG_DIR).heartbeat_file"] = _rel(hb2.heartbeat_file)
    out["l6.FleetHeartbeat(LOG_DIR).audit_log_file"] = _rel(hb2.audit_log_file)
    out["l6.GeminiSmartRouter.budget_tracker.budget_file"] = _rel(l6.GeminiSmartRouter().budget_tracker.budget_file)
    return out


def _setup_logger_file():
    handlers = []

    class _FH:
        def __init__(self, filename, *a, **k):
            handlers.append(filename)
            self.level = 0
            self.formatter = None

        def setLevel(self, *a): pass
        def setFormatter(self, *a): pass
        def handle(self, *a): pass
        def acquire(self): pass
        def release(self): pass
        def close(self): pass
        def flush(self): pass
        def emit(self, *a): pass
        def filter(self, *a): return True

    import logging
    old = l6._logger
    snap = {n: (lg, list(lg.handlers), lg.level, lg.propagate) for n, lg in logging.root.manager.loggerDict.items()
            if isinstance(lg, logging.Logger)}
    root_snap = (list(logging.root.handlers), logging.root.level)
    l6._logger = None
    try:
        with patch("logging.FileHandler", _FH), patch("logging.handlers.RotatingFileHandler", _FH, create=True), \
             patch("logging.handlers.TimedRotatingFileHandler", _FH, create=True):
            try:
                l6.setup_logger()
            except Exception:
                pass
    finally:
        l6._logger = old
        # khôi phục TOÀN BỘ logger: không để handler giả rò sang test khác
        for name, lg in list(logging.root.manager.loggerDict.items()):
            if isinstance(lg, logging.Logger):
                if name in snap:
                    lg.handlers[:] = snap[name][1]
                    lg.setLevel(snap[name][2])
                    lg.propagate = snap[name][3]
                else:
                    lg.handlers[:] = []
        logging.root.handlers[:] = root_snap[0]
        logging.root.setLevel(root_snap[1])
    return [_rel(h) for h in handlers]


def _entrypoints():
    """Các điểm vào bên ngoài: chỉ lấy dòng nhắc đường dẫn gói (để theo dõi khi di chuyển)."""
    out = {}
    pat = re.compile(r"(core|live_federation_runner|start_bot|ensure_mt5_gui|us_federation_quant[/\\])", re.I)
    for rel in ("start_bot.bat", "scripts/deploy/us_federation_quant.service",
                "scripts/ops_windows/setup_windows_watchdog_task.ps1", "scripts/ops_windows/create_startup_shortcut.ps1",
                "scripts/ops_windows/run_as_admin_optimize.bat"):
        f = PKG / rel
        lines = []
        if f.exists():
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                s = ln.strip()
                if pat.search(s) and not s.lower().startswith(("rem", "::", "#")):
                    lines.append(s)
        out[rel] = lines
    return out


def _current():
    cur = {}
    cur["runner._DIR"] = _rel(runner._DIR)
    cur["runner._WORKSPACE"] = _rel(runner._WORKSPACE)
    cur["runner.LOG_DIR"] = _rel(runner.LOG_DIR)
    cur["runner._LOCK_FILE_PATH"] = _rel(runner._LOCK_FILE_PATH)
    cur["runner.dotenv_path(_DIR/.env)"] = _rel(runner._DIR / ".env")
    cur["l4._DIR"] = _rel(l4._DIR)
    cur["l4.LOG_DIR"] = _rel(l4.LOG_DIR)
    cur["l4._QUARANTINE_REGISTRY_PATH"] = _rel(l4._QUARANTINE_REGISTRY_PATH)
    cur["gov._VAULT_LEDGER_PATH"] = _rel(gov._VAULT_LEDGER_PATH)
    cur["l3.workspace(parent^3 of l3_sizing.py)"] = _rel(Path(l3.__file__).resolve().parent.parent.parent)
    cur["constructor_defaults"] = _under_patches(_defaults)
    cur["l6.setup_logger(default).log_file"] = _under_patches(_setup_logger_file)
    cur["config_files_exist"] = {p: (PKG / p).exists() for p in (
        "configs/constitution/article_1_max_drawdown.yaml", "configs/constitution/article_2_var_limits.yaml",
        "data/macro_calendar_cache.json")}
    cur["data_dir_exists"] = {"data": (PKG / "data").is_dir(), "data/vault_data": (PKG / "data" / "vault_data").is_dir()}
    cur["entrypoints"] = _entrypoints()
    return cur


def test_generate_or_match_golden():
    current = json.loads(json.dumps(_current(), sort_keys=True, default=str))
    if os.environ.get("GENERATE_GOLDEN") == "1":
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        json.dump(current, open(GOLDEN, "w", encoding="utf-8"), indent=1, ensure_ascii=False, sort_keys=True)
        pytest.skip("golden đã được sinh")
    golden = json.load(open(GOLDEN, encoding="utf-8"))
    for k in golden:
        assert current[k] == golden[k], f"golden lệch ở: {k}"
    assert set(current) == set(golden)
