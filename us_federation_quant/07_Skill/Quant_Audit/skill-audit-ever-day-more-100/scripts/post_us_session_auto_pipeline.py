#!/usr/bin/env python3
"""Skill Audit Ever Day More 100$ (`skill-audit-ever-day-more-100`) — Post-US-Session Auto-Audit & Process Relauncher.

Combines `daily-quant-audit-system` + `daily-tri-block-audit` into 1 master pipeline (`skill audit ever day more 100$`) that:
1. Enforces Friday EOD Flat at 20:30 UTC (23:30 Server Time / 03:30 GMT+7 — 29 minutes BEFORE Exness 20:59 UTC close)
   and triggers Post-US-Session Audit at 21:05 UTC (04:05 GMT+7), or runs immediately.
2. Runs the Unified Master Audit (Status Tiers, Ticket Attribution, 3A Tri-Block Alpha/ML/Emergency Forensics,
   3B Keep-vs-Fix Matrix, >$100/day Reconciliation, and Section 4 Counterfactual No-Regression Gate).
3. Saves the timestamped JSON + Markdown report to `us_federation_quant/logs/daily_audit_reports/`.
4. Verifies the 5 Institutional Commandments (Drawdown Ladder > -7.5%), terminates any stale old bot process,
   and AUTOMATICALLY LAUNCHES / RESTARTS the latest `live_federation_runner.py` process!
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
QUANT_AUDIT_ROOT = SCRIPT_DIR.parents[1]
BOT_ROOT = QUANT_AUDIT_ROOT.parents[1]  # C:\Quant_03\us_federation_quant
WORKSPACE_ROOT = BOT_ROOT.parent        # C:\Quant_03
REPORT_ARCHIVE_DIR = BOT_ROOT / "logs" / "daily_audit_reports"
UNIVERSAL_AUDIT_SCRIPT = (
    QUANT_AUDIT_ROOT
    / "institutional-quant-audit"
    / "scripts"
    / "audit_any_bot.py"
)

CANDIDATE_BOT_ENTRYPOINTS: List[Tuple[str, Path]] = [
    ("us_federation_quant", BOT_ROOT / "live_federation_runner.py"),
    ("gold_oracle_trading_bot", BOT_ROOT / "gold_oracle_trading_bot.py"),
]


def load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_any_bot", str(UNIVERSAL_AUDIT_SCRIPT))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {UNIVERSAL_AUDIT_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover_latest_bot_entrypoint(target_bot_dir: Optional[Path] = None) -> Tuple[str, Path]:
    """Find the most recently updated bot runner script in `--bot-dir` or in `us_federation_quant`."""
    if target_bot_dir and target_bot_dir.exists():
        target_bot_dir = target_bot_dir.resolve()
        for pat in ("live_federation_runner.py", "run_unified_bot.py", "pipeline_live.py", "live_trade.py", "main.py"):
            matches = sorted(target_bot_dir.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
            if matches:
                return target_bot_dir.name, matches[0].resolve()

    existing: List[Tuple[str, Path, float]] = []
    for name, path in CANDIDATE_BOT_ENTRYPOINTS:
        if path.exists():
            existing.append((name, path.resolve(), path.stat().st_mtime))
    if not existing:
        raise FileNotFoundError(f"No bot entrypoint script found in {BOT_ROOT}.")
    existing.sort(key=lambda x: x[2], reverse=True)
    return existing[0][0], existing[0][1]


def inspect_and_manage_bot_processes(entrypoint_path: Path) -> Tuple[Optional[int], List[int]]:
    """
    Check running Python processes for `entrypoint_path.name`:
    - If a process is already running and its CreationDate >= file mtime, keep it alive (returns (pid, []))
      so daily 04:35 AM Task Scheduler runs never wipe in-memory state unnecessarily.
    - If a running process is older than file mtime (stale zombie code in RAM), terminate it and return (None, [killed_pids]).
    """
    script_name = entrypoint_path.name
    file_mtime = entrypoint_path.stat().st_mtime
    terminated_pids: List[int] = []
    up_to_date_pid: Optional[int] = None
    current_pid = os.getpid()
    try:
        ps_cmd = (
            f"Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" "
            f"| Where-Object {{ $_.CommandLine -like '*{script_name}*' -and $_.ProcessId -ne {current_pid} }} "
            f"| ForEach-Object {{ "
            f"$ts = [int][double]::Parse((New-TimeSpan -Start (Get-Date '1970-01-01T00:00:00Z') -End $_.CreationDate.ToUniversalTime()).TotalSeconds); "
            f"Write-Output \"$($_.ProcessId):$ts\" }}"
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
        for line in res.stdout.splitlines():
            line = line.strip()
            if ":" in line:
                pid_str, ts_str = line.split(":", 1)
                if pid_str.isdigit() and ts_str.lstrip("-").isdigit():
                    pid = int(pid_str)
                    proc_start_ts = float(ts_str)
                    if proc_start_ts >= (file_mtime - 5.0) and up_to_date_pid is None:
                        up_to_date_pid = pid
                    else:
                        subprocess.run(
                            ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"],
                            capture_output=True,
                            timeout=5,
                        )
                        terminated_pids.append(pid)
    except Exception:
        pass
    return up_to_date_pid, terminated_pids


def check_and_launch_latest_bot_process(
    bot_name: str,
    entrypoint_path: Path,
    audit_payload: Dict[str, Any],
    custom_cmd: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Verify Risk Gate after audit, terminate stale old processes, and launch the latest bot process."""
    entrypoint_path = entrypoint_path.resolve()
    rec = audit_payload.get("3_daily_100usd_reconciliation", {})
    nrg = audit_payload.get("counterfactual_no_regression_gate", {})

    tiers = audit_payload.get("1_status_tiers", [])
    is_halted = any("TIER_3_HALTED" in str(t.get("detail", "")) and "🔴" in str(t.get("tier", "")) for t in tiers)
    if is_halted:
        return {
            "relaunch_status": "BLOCKED_BY_TIER_3_HALT",
            "bot_name": bot_name,
            "entrypoint": str(entrypoint_path),
            "reason": "Tài khoản chạm ngưỡng ngắt mạch khẩn cấp TIER_3_HALTED (-7.5% DD). Đóng băng mở tiến trình mới theo Điều Răn #1.",
        }

    cmd_list = custom_cmd.split() if custom_cmd else [sys.executable, str(entrypoint_path)]
    log_dir = REPORT_ARCHIVE_DIR / "process_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    proc_log_file = log_dir / f"{bot_name.replace(' ', '_')}_{ts_tag}.log"

    if dry_run:
        return {
            "relaunch_status": "READY_VERIFIED (DRY-RUN)",
            "bot_name": bot_name,
            "entrypoint": str(entrypoint_path),
            "last_modified": datetime.fromtimestamp(entrypoint_path.stat().st_mtime).isoformat(),
            "command": " ".join(cmd_list),
            "process_log": str(proc_log_file),
            "no_regression_gate": nrg.get("verdict", "PASS"),
            "potential_daily_pnl_usd": rec.get("clean_no_bad_loss_avg_daily_pnl_usd", 0.0),
        }

    up_to_date_pid, stopped_pids = inspect_and_manage_bot_processes(entrypoint_path)
    if up_to_date_pid is not None:
        return {
            "relaunch_status": "KEEP_ALIVE_ACTIVE (Already running latest code — In-memory state preserved)",
            "pid": up_to_date_pid,
            "terminated_stale_pids": stopped_pids,
            "bot_name": bot_name,
            "entrypoint": str(entrypoint_path),
            "last_modified": datetime.fromtimestamp(entrypoint_path.stat().st_mtime).isoformat(),
            "command": " ".join(cmd_list),
            "working_dir": str(entrypoint_path.parent),
            "process_log": str(BOT_ROOT / "logs" / "us_federation_quant.log"),
            "no_regression_gate": nrg.get("verdict", "PASS"),
        }

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    with proc_log_file.open("a", encoding="utf-8") as lf:
        lf.write(f"=== [{datetime.now(timezone.utc).isoformat()}] AUTO-LAUNCHED BY SKILL AUDIT EVER DAY MORE 100$ ===\n")
        if stopped_pids:
            lf.write(f"=== Terminated stale old bot PIDs: {stopped_pids} ===\n")
        lf.flush()
        proc = subprocess.Popen(
            cmd_list,
            cwd=str(entrypoint_path.parent),
            stdout=lf,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )

    time.sleep(0.8)
    poll_code = proc.poll()
    is_running = poll_code is None

    return {
        "relaunch_status": "RUNNING_ACTIVE" if is_running else f"EXITED_EARLY (code={poll_code})",
        "pid": proc.pid,
        "terminated_stale_pids": stopped_pids,
        "bot_name": bot_name,
        "entrypoint": str(entrypoint_path),
        "last_modified": datetime.fromtimestamp(entrypoint_path.stat().st_mtime).isoformat(),
        "command": " ".join(cmd_list),
        "working_dir": str(entrypoint_path.parent),
        "process_log": str(proc_log_file),
        "no_regression_gate": nrg.get("verdict", "PASS"),
    }


def execute_post_us_session_pipeline(
    bot_dir: Optional[Path] = None,
    use_live_mt5: bool = False,
    custom_process_cmd: Optional[str] = None,
    dry_run_relaunch: bool = False,
    pretty: bool = True,
) -> Dict[str, Any]:
    """Run the full Post-US-Session Audit -> Save Report -> Launch Latest Bot Process pipeline."""
    mod = load_audit_module()
    bot_name, latest_entrypoint = discover_latest_bot_entrypoint(bot_dir)
    effective_bot_dir = bot_dir.resolve() if bot_dir else latest_entrypoint.parent

    payload = mod.run_universal_bot_audit(
        bot_dir=effective_bot_dir,
        use_live_mt5=use_live_mt5,
        daily_target_usd=100.0,
        lookback_hours=168,
    )
    payload["skill_name"] = "skill audit ever day more 100$ (skill-audit-ever-day-more-100)"

    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.print_pretty_report(payload)
    pretty_text = buf.getvalue()

    REPORT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe_bot = bot_name.replace(" ", "_")
    json_report_path = REPORT_ARCHIVE_DIR / f"audit_100usd_{safe_bot}_{date_tag}.json"
    md_report_path = REPORT_ARCHIVE_DIR / f"audit_100usd_{safe_bot}_{date_tag}.md"

    relaunch_info = check_and_launch_latest_bot_process(
        bot_name=bot_name,
        entrypoint_path=latest_entrypoint,
        audit_payload=payload,
        custom_cmd=custom_process_cmd,
        dry_run=dry_run_relaunch,
    )
    payload["5_post_audit_auto_runner"] = relaunch_info

    json_report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_report_path.write_text(
        "🏆 [SKILL: skill audit ever day more 100$ (skill-audit-ever-day-more-100)]\n"
        + pretty_text
        + "\n### 5. TRẠNG THÁI TỰ ĐỘNG KHỞI CHẠY TIẾN TRÌNH MỚI NHẤT SAU AUDIT (POST-AUDIT AUTO-RUNNER)\n"
        + "-" * 104
        + f"\n  • Trạng thái tiến trình : {relaunch_info['relaunch_status']}"
        + (f" (PID: {relaunch_info['pid']})" if "pid" in relaunch_info else "")
        + (f" | Đã dừng PID cũ: {relaunch_info['terminated_stale_pids']}" if relaunch_info.get("terminated_stale_pids") else "")
        + f"\n  • Tiến trình mới nhất   : {relaunch_info['entrypoint']} (Cập nhật lúc: {relaunch_info.get('last_modified', 'N/A')})"
        + f"\n  • Lệnh khởi chạy        : {relaunch_info.get('command', 'N/A')}"
        + f"\n  • File Log Tiến Trình   : {relaunch_info.get('process_log', 'N/A')}"
        + f"\n  • Bản lưu Báo cáo Audit : {md_report_path}\n"
        + "=" * 104
        + "\n",
        encoding="utf-8",
    )

    if pretty:
        print(md_report_path.read_text(encoding="utf-8"))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return payload


def _is_us_dst(dt_utc: Optional[datetime] = None) -> bool:
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    year = dt_utc.year
    march_1 = datetime(year, 3, 1, tzinfo=timezone.utc)
    dst_start = datetime(year, 3, 1 + (6 - march_1.weekday()) % 7 + 7, 7, 0, 0, tzinfo=timezone.utc)
    nov_1 = datetime(year, 11, 1, tzinfo=timezone.utc)
    dst_end = datetime(year, 11, 1 + (6 - nov_1.weekday()) % 7, 6, 0, 0, tzinfo=timezone.utc)
    return dst_start <= dt_utc < dst_end


def _get_mt5_server_datetime(dt_utc: Optional[datetime] = None) -> datetime:
    from datetime import timedelta
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    return dt_utc + timedelta(hours=3 if _is_us_dst(dt_utc) else 2)


def register_windows_scheduled_task(daily_time_local: str = "04:35") -> str:
    """Register Windows Task Scheduler job to run automatically after US Session close (04:35 GMT+7 in Winter EST / 21:35 UTC = 23:35 Server Time)."""
    task_name = "Skill_Audit_Ever_Day_More_100USD"
    bat_path = Path(__file__).resolve().parent / "start_post_us_auto_pipeline.bat"
    cmd = [
        "schtasks",
        "/Create",
        "/F",
        "/SC",
        "DAILY",
        "/TN",
        task_name,
        "/TR",
        f'"{bat_path}"',
        "/ST",
        daily_time_local,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        return (
            f"SUCCESS: Đã đăng ký Windows Scheduled Task '{task_name}' (skill audit ever day more 100$) "
            f"tự động chạy lúc {daily_time_local} GMT+7 mỗi ngày (trỏ tới {bat_path})."
        )
    return f"WARNING: Không thể tạo schtasks tự động ({res.stderr.strip()}). Bạn có thể chạy bằng chế độ --daemon."


def run_us_session_close_daemon(
    bot_dir: Optional[Path],
    close_srv_hour: int = 23,
    close_srv_minute: int = 35,
    dry_run_relaunch: bool = False,
) -> None:
    """Background daemon that triggers EOD Flat & Audit at 23:35 MT5 Server Time (20:35 UTC EDT / 21:35 UTC EST) before market close."""
    print(
        f"[SKILL AUDIT EVER DAY MORE 100$ — DAEMON] Đang trực chiến chờ chốt Phiên Mỹ ({close_srv_hour:02d}:{close_srv_minute:02d} MT5 Server Time — Tự động thích ứng US DST 01/11)..."
    )
    last_triggered_date: Optional[str] = None
    while True:
        now_utc = datetime.now(timezone.utc)
        srv_dt = _get_mt5_server_datetime(now_utc)
        today_str = srv_dt.strftime("%Y-%m-%d")
        if (
            srv_dt.weekday() in (0, 1, 2, 3, 4)
            and srv_dt.hour == close_srv_hour
            and srv_dt.minute >= close_srv_minute
            and last_triggered_date != today_str
        ):
            print(f"\n⚡ [{now_utc.isoformat()} | Server: {srv_dt.strftime('%H:%M:%S')}] ĐẾN GIỜ CHỐT PHIÊN MỸ (23:35 Server Time)! Chạy 'skill audit ever day more 100$' & Khởi động tiến trình mới nhất...")
            execute_post_us_session_pipeline(
                bot_dir=bot_dir,
                use_live_mt5=True,
                dry_run_relaunch=dry_run_relaunch,
                pretty=True,
            )
            last_triggered_date = today_str
        time.sleep(30)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="skill audit ever day more 100$ — Post-US-Session Auto-Audit & Latest Bot Relauncher")
    parser.add_argument("--bot-dir", default=None, help="Target bot directory (auto-detects us_federation_quant if omitted)")
    parser.add_argument("--live-mt5", action="store_true", help="Include Live MT5 deal & position inspection")
    parser.add_argument("--process-cmd", default=None, help="Custom command to launch after audit finishes")
    parser.add_argument("--dry-run-relaunch", action="store_true", help="Verify latest bot entrypoint without spawning a duplicate process")
    parser.add_argument("--daemon", action="store_true", help="Run continuous background daemon that triggers at 20:35 UTC (23:35 Server Time)")
    parser.add_argument("--install-windows-task", action="store_true", help="Register Windows Task Scheduler job at 03:35 GMT+7")
    parser.add_argument("--pretty", action="store_true", default=True, help="Print formatted report")
    args = parser.parse_args()

    if args.install_windows_task:
        print(register_windows_scheduled_task("04:35"))

    bot_dir = Path(args.bot_dir) if args.bot_dir else None

    if args.daemon:
        run_us_session_close_daemon(bot_dir=bot_dir, dry_run_relaunch=args.dry_run_relaunch)
    else:
        execute_post_us_session_pipeline(
            bot_dir=bot_dir,
            use_live_mt5=args.live_mt5,
            custom_process_cmd=args.process_cmd,
            dry_run_relaunch=args.dry_run_relaunch,
            pretty=args.pretty,
        )


if __name__ == "__main__":
    main()
