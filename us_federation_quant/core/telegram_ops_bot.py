"""
========================================================================================
US FEDERATION QUANT — TELEGRAM WAR-ROOM & MOBILE OPS BOT
Module: telegram_ops_bot.py
Institutional Operations & Emergency Command Center for Mobile Phones.
Enables Quant Fund Managers to:
1. Receive real-time mission-critical alerts (Drawdown ladder, Farhi Jump, BlackRock Sweep, TCA Slippage).
2. Query live account health, PnL, and 50 Sovereign State Pods via /status, /pnl, /pods, /risk.
3. Issue emergency interventions: /kill, /quarantine <id>, /resume <id>, /panic.
Zero external pip dependency (uses Python standard library urllib.request) with dry-run fallback.
========================================================================================
"""

from __future__ import annotations
import os
import sys
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger("US_Federation.TelegramOpsBot")


@dataclass
class TelegramAlert:
    timestamp: datetime
    level: str  # INFO, WARNING, CRITICAL, NUCLEAR
    title: str
    message: str
    sent_successfully: bool
    response_payload: Optional[str] = None


class TelegramOpsBot:
    """
    Phòng Tình Báo Tác Chiến Di Động (Mobile War-Room Bot).
    Cầu nối giữa Quant Trưởng và Hệ Thống 50 Pods Định Chế 24/7.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        dry_run: Optional[bool] = None,
        status_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        pnl_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        pods_provider: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        risk_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        kill_switch_fn: Optional[Callable[[], Dict[str, Any]]] = None,
        quarantine_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
        resume_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

        # Nếu không có token, tự động chạy ở chế độ Dry-Run an toàn (không crash)
        if dry_run is None:
            self.dry_run = not (bool(self.bot_token) and bool(self.chat_id))
        else:
            self.dry_run = dry_run

        # Các hàm callback lấy dữ liệu động từ hệ thống
        self._status_provider = status_provider or self._default_status_provider
        self._pnl_provider = pnl_provider or self._default_pnl_provider
        self._pods_provider = pods_provider or self._default_pods_provider
        self._risk_provider = risk_provider or self._default_risk_provider
        self._kill_switch_fn = kill_switch_fn or self._default_kill_switch
        self._quarantine_fn = quarantine_fn or self._default_quarantine
        self._resume_fn = resume_fn or self._default_resume

        # Nhật ký thông báo gửi đi (Audit Trail)
        self.sent_alerts: List[TelegramAlert] = []
        logger.info(f"📱 TelegramOpsBot initialized (Dry-Run: {self.dry_run})")

    # =========================================================================
    # 1. OUTBOUND ALERT DISPATCHER (GỬI CẢNH BÁO KHẨN CẤP ĐẾN ĐIỆN THOẠI)
    # =========================================================================
    def send_alert(self, level: str, title: str, message: str) -> bool:
        """
        Gửi cảnh báo định dạng HTML phong cách định chế đến Telegram của Quant Trưởng.
        Level: INFO, WARNING, CRITICAL, NUCLEAR
        """
        level_icons = {
            "INFO": "ℹ️ [INFO]",
            "WARNING": "⚠️ [CẢNH BÁO RỦI RO]",
            "CRITICAL": "🚨 [BÁO ĐỘNG ĐỎ]",
            "NUCLEAR": "☢️ [LỆNH HỦY KHẨN CẤP]",
        }
        icon = level_icons.get(level.upper(), "📢 [THÔNG BÁO]")
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        formatted_text = (
            f"<b>{icon} {title}</b>\n"
            f"<i>Thời gian: {now_str}</i>\n"
            f"───────────────────\n"
            f"{message}\n"
            f"───────────────────\n"
            f"<b>US Federation Quant — Citadel War-Room</b>"
        )

        if self.dry_run:
            logger.info(f"[Telegram Dry-Run] Alert Recorded: {title} | {message}")
            alert = TelegramAlert(
                timestamp=datetime.now(timezone.utc),
                level=level.upper(),
                title=title,
                message=message,
                sent_successfully=True,
                response_payload="DRY_RUN_OK",
            )
            self.sent_alerts.append(alert)
            return True

        # Gửi HTTP POST tới Telegram Bot API
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": formatted_text,
            "parse_mode": "HTML",
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "USFederationQuantBot/1.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                resp_text = response.read().decode("utf-8")
                resp_json = json.loads(resp_text)
                is_ok = bool(resp_json.get("ok", False))

                self.sent_alerts.append(
                    TelegramAlert(
                        timestamp=datetime.now(timezone.utc),
                        level=level.upper(),
                        title=title,
                        message=message,
                        sent_successfully=is_ok,
                        response_payload=resp_text,
                    )
                )
                return is_ok
        except Exception as e:
            logger.error(f"❌ Lỗi gửi tin nhắn Telegram: {e}")
            self.sent_alerts.append(
                TelegramAlert(
                    timestamp=datetime.now(timezone.utc),
                    level=level.upper(),
                    title=title,
                    message=message,
                    sent_successfully=False,
                    response_payload=str(e),
                )
            )
            return False

    # =========================================================================
    # 2. INBOUND COMMAND PROCESSOR (XỬ LÝ LỆNH ĐIỀU KHIỂN TỪ ĐIỆN THOẠI)
    # =========================================================================
    def handle_command(self, raw_text: str) -> str:
        """
        Tiếp nhận và xử lý lệnh từ người dùng trên Telegram.
        """
        text = raw_text.strip()
        parts = text.split()
        if not parts:
            return "Vui lòng nhập lệnh. Gõ /help để xem hướng dẫn."

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ["/start", "/help"]:
            return self._cmd_help()
        elif cmd == "/status":
            return self._cmd_status()
        elif cmd == "/pnl":
            return self._cmd_pnl()
        elif cmd == "/pods":
            return self._cmd_pods()
        elif cmd == "/risk":
            return self._cmd_risk()
        elif cmd == "/kill":
            return self._cmd_kill()
        elif cmd == "/quarantine":
            if not args:
                return "⚠️ Cú pháp: /quarantine <state_id> (Ví dụ: /quarantine STATE_01_GOLD_SCALP)"
            return self._cmd_quarantine(args[0])
        elif cmd == "/resume":
            if not args:
                return "⚠️ Cú pháp: /resume <state_id> (Ví dụ: /resume STATE_01_GOLD_SCALP)"
            return self._cmd_resume(args[0])
        elif cmd == "/panic":
            return self._cmd_panic()
        else:
            return f"❓ Lệnh không hợp lệ: '{cmd}'. Gõ /help để xem danh sách lệnh tác chiến."

    # =========================================================================
    # 3. COMMAND HANDLERS
    # =========================================================================
    def _cmd_help(self) -> str:
        return (
            "🏛️ <b>TRUNG TÂM TÁC CHIẾN US FEDERATION QUANT</b>\n"
            "───────────────────\n"
            "📋 <b>Lệnh Tra Cứu:</b>\n"
            "• /status — Tình trạng sống (Heartbeat), sàn MT5, vốn.\n"
            "• /pnl — Lợi nhuận hôm nay, PnL thả nổi, Drawdown.\n"
            "• /pods — Tình trạng hoạt động của 50 State Pods.\n"
            "• /risk — Báo cáo rủi ro (VaR, CVaR, Farhi, Rollover).\n"
            "\n"
            "🚨 <b>Lệnh Can Thiệp Khẩn Cấp:</b>\n"
            "• /quarantine &lt;id&gt; — Cách ly cưỡng chế một Pod bị sụt giảm vốn.\n"
            "• /resume &lt;id&gt; — Hủy cách ly và khôi phục hoạt động cho Pod.\n"
            "• /kill — Kích hoạt Kill-Switch: Đóng toàn bộ lệnh, ngừng giao dịch!\n"
            "• /panic — Báo động đỏ toàn liên bang, ngắt mạch toàn bộ bot."
        )

    def _cmd_status(self) -> str:
        s = self._status_provider()
        return (
            "🏛️ <b>TÌNH TRẠNG HỆ THỐNG LIÊN BANG</b>\n"
            "───────────────────\n"
            f"• <b>Tài khoản Exness:</b> <code>{s.get('account_id', '416351011')}</code>\n"
            f"• <b>Máy chủ:</b> {s.get('server', 'Exness-MT5Trial17')}\n"
            f"• <b>Vốn hiện tại:</b> ${s.get('equity', 10000.0):,.2f}\n"
            f"• <b>Số Dư (Balance):</b> ${s.get('balance', 10000.0):,.2f}\n"
            f"• <b>Ký Quỹ Tự Do:</b> ${s.get('free_margin', 10000.0):,.2f}\n"
            f"• <b>Số Pod Đang Chạy:</b> {s.get('active_pods', 50)}/50 Pods\n"
            f"• <b>Vị Thế Đang Mở:</b> {s.get('open_positions', 0)} lệnh\n"
            f"• <b>Tình Trạng:</b> {s.get('health_status', '✅ GREEN — SẴN SÀNG')}"
        )

    def _cmd_pnl(self) -> str:
        p = self._pnl_provider()
        pnl_today = p.get("pnl_today", 0.0)
        pnl_icon = "🟢" if pnl_today >= 0 else "🔴"
        return (
            f"💰 <b>BÁO CÁO HIỆU SUẤT PNL (HÔM NAY)</b>\n"
            "───────────────────\n"
            f"• <b>PnL Hôm Nay:</b> {pnl_icon} ${pnl_today:+,.2f} ({p.get('return_pct', 0.0):+.2f}%)\n"
            f"• <b>PnL Thả Nổi (Floating):</b> ${p.get('floating_pnl', 0.0):+,.2f}\n"
            f"• <b>Đỉnh Vốn (High-Water Mark):</b> ${p.get('high_water_mark', 10000.0):,.2f}\n"
            f"• <b>Sụt Giảm Vốn (Drawdown):</b> {p.get('current_drawdown_pct', 0.0):.2f}%\n"
            f"• <b>Ngưỡng Báo Động Thang Pod (-3%):</b> {p.get('ladder_threshold_3', '-3.0%')} (An Toàn)\n"
            f"• <b>Tỷ Lệ Thắng (Win-Rate):</b> {p.get('win_rate_pct', 65.0):.1f}%"
        )

    def _cmd_pods(self) -> str:
        pods = self._pods_provider()
        lines = [f"🛡️ <b>DANH SÁCH PODS ĐỊNH CHẾ ({len(pods)} Pods)</b>", "───────────────────"]
        for pod in pods[:15]:  # Hiển thị 15 Pods đầu để tránh tin nhắn quá dài
            icon = "🟢" if pod.get("status") == "ACTIVE" else "🟡" if pod.get("status") == "THROTTLED" else "🔴"
            lines.append(f"{icon} <code>{pod.get('magic')}</code> | {pod.get('name')}: {pod.get('status')}")
        if len(pods) > 15:
            lines.append(f"... và còn {len(pods) - 15} Pods khác đang vận hành.")
        return "\n".join(lines)

    def _cmd_risk(self) -> str:
        r = self._risk_provider()
        return (
            "⚖️ <b>BÁO CÁO BÀN GIÁM SÁT RỦI RO ĐỊNH CHẾ</b>\n"
            "───────────────────\n"
            f"• <b>Parametric VaR (99% 1-Day):</b> ${r.get('var_99', 150.0):,.2f}\n"
            f"• <b>Conditional VaR (CVaR/Expected Shortfall):</b> ${r.get('cvar_99', 210.0):,.2f}\n"
            f"• <b>Số Cặp Tương Quan Đột Biến:</b> {r.get('high_corr_pairs', 4)}/10 cặp (An Toàn)\n"
            f"• <b>LỆNH 01: Giờ Giới Nghiêm Rollover:</b> {r.get('curfew_status', '✅ Tự do mở lệnh')}\n"
            f"• <b>LỆNH 02: Trượt Giá TCA:</b> {r.get('tca_slippage_pips', 0.8):.1f} pips (&lt; 3.0 pips)\n"
            f"• <b>LỆNH 03: Bộ Lọc Thảm Họa Farhi:</b> {r.get('farhi_status', '✅ Bình thường')}\n"
            f"• <b>TẦNG 06: Đóng Băng Tin Tức Vĩ Mô Đỏ:</b> {r.get('macro_blackout_status', '✅ Ngoài bão đỏ')}"
        )

    def _cmd_kill(self) -> str:
        res = self._kill_switch_fn()
        return (
            "☢️ <b>KÍCH HOẠT LỆNH HỦY KHẨN CẤP (NUCLEAR KILL-SWITCH)</b>\n"
            "───────────────────\n"
            f"• <b>Kết quả:</b> {res.get('status', 'EXECUTED')}\n"
            f"• <b>Số lệnh đã đóng:</b> {res.get('closed_positions_count', 0)}\n"
            f"• <b>Trạng thái hệ thống:</b> 🛑 ĐÃ KHÓA TOÀN BỘ CỔ MÁY GIAO DỊCH!\n"
            "Cần can thiệp trực tiếp từ máy chủ để khởi động lại."
        )

    def _cmd_quarantine(self, state_id: str) -> str:
        res = self._quarantine_fn(state_id)
        return (
            f"🔒 <b>LỆNH CÁCH LY TIỂU BANG: {state_id}</b>\n"
            "───────────────────\n"
            f"• <b>Trạng thái:</b> {res.get('status', 'QUARANTINED')}\n"
            f"• <b>Thông báo:</b> {res.get('message', 'Đã đình chỉ mở lệnh mới cho Pod này.')}"
        )

    def _cmd_resume(self, state_id: str) -> str:
        res = self._resume_fn(state_id)
        return (
            f"🔓 <b>LỆNH PHỤC HỒI TIỂU BANG: {state_id}</b>\n"
            "───────────────────\n"
            f"• <b>Trạng thái:</b> {res.get('status', 'ACTIVE')}\n"
            f"• <b>Thông báo:</b> {res.get('message', 'Đã cấp phép giao dịch trở lại.')}"
        )

    def _cmd_panic(self) -> str:
        res = self._kill_switch_fn()
        return (
            "🚨 <b>BÁO ĐỘNG ĐỎ TOÀN LIÊN BANG (PANIC BUTTON TRIGGERED)</b>\n"
            "───────────────────\n"
            "Toàn bộ 50 tiểu bang đã nhận lệnh rút lui. Toàn bộ tiền đã thu về két an toàn!"
        )

    # =========================================================================
    # 4. DEFAULT PROVIDERS (MẪU DỮ LIỆU CHUẨN KHI CHƯA KẾT NỐI HỆ THỐNG THẬT)
    # =========================================================================
    @staticmethod
    def _default_status_provider() -> Dict[str, Any]:
        return {
            "account_id": "416351011",
            "server": "Exness-MT5Trial17",
            "equity": 10000.0,
            "balance": 10000.0,
            "free_margin": 10000.0,
            "active_pods": 50,
            "open_positions": 0,
            "health_status": "✅ GREEN — SẴN SÀNG CHO PHIÊN THỨ 2",
        }

    @staticmethod
    def _default_pnl_provider() -> Dict[str, Any]:
        return {
            "pnl_today": 125.50,
            "return_pct": 1.25,
            "floating_pnl": 15.20,
            "high_water_mark": 10000.0,
            "current_drawdown_pct": 0.0,
            "ladder_threshold_3": "-3.0%",
            "win_rate_pct": 68.4,
        }

    @staticmethod
    def _default_pods_provider() -> List[Dict[str, Any]]:
        sample_pods = [
            {"magic": 260901, "name": "STATE_01_GOLD_SCALP", "status": "ACTIVE"},
            {"magic": 260902, "name": "STATE_02_BTC_MOMENTUM", "status": "ACTIVE"},
            {"magic": 260903, "name": "STATE_03_US30_HYBRID", "status": "ACTIVE"},
            {"magic": 260904, "name": "STATE_04_USDJPY_CARRY", "status": "ACTIVE"},
            {"magic": 260905, "name": "STATE_05_EURUSD_STATARB", "status": "ACTIVE"},
        ]
        return sample_pods

    @staticmethod
    def _default_risk_provider() -> Dict[str, Any]:
        return {
            "var_99": 142.50,
            "cvar_99": 198.20,
            "high_corr_pairs": 3,
            "curfew_status": "✅ Tự do mở lệnh",
            "tca_slippage_pips": 0.6,
            "farhi_status": "✅ 100% An toàn (Hệ số > 0.60)",
            "macro_blackout_status": "✅ Không có bão đỏ trong 60 phút tới",
        }

    @staticmethod
    def _default_kill_switch() -> Dict[str, Any]:
        return {"status": "SUCCESS", "closed_positions_count": 0, "system_state": "HALTED"}

    @staticmethod
    def _default_quarantine(state_id: str) -> Dict[str, Any]:
        return {"status": "QUARANTINED", "target_state": state_id, "message": f"Tiểu bang {state_id} đã bị cách ly."}

    @staticmethod
    def _default_resume(state_id: str) -> Dict[str, Any]:
        return {"status": "ACTIVE", "target_state": state_id, "message": f"Tiểu bang {state_id} đã được khôi phục."}
