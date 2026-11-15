# Checklist triển khai nhánh `Layer-didece` (kiến trúc 6 tầng) lên VPS

> Phạm vi: chuyển từ bản cũ sang nhánh `Layer-didece` **chỉ sau khi** qua Shadow/Demo 24h (mục C).
> Không merge vào `main` và không bật tài khoản live trước khi chủ hệ thống ký duyệt mục D.
> Mọi tiêu chí "đạt" bên dưới do người vận hành tự kiểm; bot chưa từng chạy trên MT5 thật với nhánh này (chỉ test double).

## 0. Sự thật cần biết trước khi bắt đầu
- Bot **không có cờ dry-run/shadow** trong `live_federation_runner.py` (đã tìm: không có `shadow`, `dry_run`). "Shadow Mode" ở đây = chạy **trên tài khoản DEMO** của cùng broker, bản cũ tiếp tục chạy live song song, hai bên không dùng chung thư mục `logs/`/`data/`.
- Kết nối MT5 đọc từ biến môi trường (`MT5_PATH`, `MT5_ACCOUNT`, `MT5_PASSWORD`, `MT5_SERVER`, `MT5_SUFFIX`) trong `.env`. Demo = đổi các biến này sang tài khoản demo. **Không in/commit `.env`; chỉ so hash.**
- Hành vi giao dịch đã đổi có chủ đích ở 3 ADR (xem `Control/ADR/`):
  - ADR-003: chạm -12% / `manual_emergency_shutdown` giờ **đóng toàn bộ vị thế** (trước đây chỉ dời SL lệnh lãi).
  - ADR-004: `symbol_info` lỗi hoặc `None` -> **bỏ pod** (trước đây kế thừa `sym_info` của pod trước).
  - ADR-005: lệnh vào có SL `None`/`NaN`/`inf`/`<= 0` bị **từ chối**.
- Lỗ hổng đã ghi nhận nhưng CHƯA sửa (ADR Backlog trong `ARCHITECTURE.md`): trần lỗ chồng chéo, two-tier 0.01L, phân bổ Carver dùng số ngẫu nhiên, gate giờ độc hại gần như không chạm tới, TP/SL đúng phía chưa kiểm.

## A. Dữ liệu và trạng thái (làm TRƯỚC khi khởi động)
- [ ] Dừng bản cũ đúng cách (không kill giữa lúc đang đóng lệnh); xác nhận không còn tiến trình `python ... live_federation_runner` cũ.
- [ ] Sao lưu toàn bộ thư mục bản cũ (zip có ngày) ra nơi ngoài VPS. Ghi lại đường lui (mục E).
- [ ] **Copy `trial_ledger.jsonl` từ `02_validation/` cũ sang `us_federation_quant/data/trial_ledger.jsonl`.** Bản mới đọc đúng đường dẫn này; thiếu file thì sổ đếm thử nghiệm bắt đầu lại từ 0 (mất bộ đếm n_trials).
- [ ] **Copy thư mục `vault_data` từ `02_validation/` cũ sang `us_federation_quant/data/vault_data/`.**
- [ ] Đối chiếu sau copy: so số dòng/kích thước/hash SHA-256 của `trial_ledger.jsonl` và danh sách file `vault_data` giữa nguồn và đích.
- [ ] Lưu ý ràng buộc tên thư mục: L4 dựng đường dẫn dữ liệu từ `.../us_federation_quant/data/...`; **thư mục gói phải tên đúng `us_federation_quant`** (VPS Linux: `/home/quant/Quant_03/us_federation_quant`).
- [ ] State vận hành nằm ở `logs/` (`two_tier_exit_state.json`, HWM, heartbeat). Nếu muốn giữ đỉnh vốn (HWM) và state two-tier của bản cũ, **copy file tương ứng từ `logs/` cũ sang `logs/` mới trước khi chạy**; không copy thì HWM khởi tạo lại từ equity hiện tại (drawdown ladder tính từ mốc mới).
- [ ] Tạo `.env` trên VPS từ bản cũ (copy file, không dán nội dung vào chat/log); kiểm hash `.env` trước/sau chỉ bằng SHA-256.
- [ ] Hash 4 file đã biết để phát hiện sửa nhầm: `configs/constitution/article_1_max_drawdown.yaml`, `article_2_var_limits.yaml`, `data/macro_calendar_cache.json`, `scripts/deploy/us_federation_quant.service`. Giá trị tham chiếu (12 ký tự đầu): `85b21a0633fa`, `2efe71c94710`, `8c753f2025b9`.

## B. Đường dẫn khởi chạy (điểm vào mới: `core/live_federation_runner.py` hoặc `start_bot.bat`)
- [ ] `git fetch && git checkout Layer-didece` trên VPS (không merge `main`).
- [ ] **Windows:** `start_bot.bat` ở root thư mục gói gọi `python core\live_federation_runner.py` và `scripts\ops_windows\ensure_mt5_gui.ps1`. Mở file xác nhận, không còn đường dẫn cũ.
- [ ] **Task watchdog Windows:** `scripts/ops_windows/setup_windows_watchdog_task.ps1` và `scripts/ops_windows/create_startup_shortcut.ps1` trỏ tới `C:\Quant_03\us_federation_quant\start_bot.bat`.
- [ ] **Linux systemd:** `scripts/deploy/us_federation_quant.service` có `ExecStart=.../python3 core/live_federation_runner.py`, `WorkingDirectory=/home/quant/Quant_03/us_federation_quant`. Sau khi cập nhật: `sudo systemctl daemon-reload`, rồi `systemctl status` và kiểm `journalctl` không báo `ModuleNotFoundError`.
- [ ] Mã thoát 99 (Nuclear Football) vẫn khiến `start_bot.bat` dừng và chờ người; xác nhận không có watchdog nào khác tự khởi động lại bot khi mã 99.
- [ ] Smoke trước khi chạy: từ gói, `python -c "import us_federation_quant.core.live_federation_runner"` không lỗi; `pytest tests/ -q` cho kết quả **đúng 181 pass / 14 fail như baseline** (14 test fail có từ trước).

## C. Shadow Mode / Demo 24h đầu tiên
Điều kiện: tài khoản **DEMO**, cùng broker/server/suffix với live; bản cũ vẫn chạy live ở máy/thư mục khác. Ghi mốc thời gian bắt đầu.

**C1. Khởi động và L6 (telemetry)**
- [ ] Log khởi động có dòng "ELITE WHITELIST ACTIVE", "ML ENGINE ACTIVE", "PHIÊN MỚI ... Benchmark Equity"; không có traceback.
- [ ] `Architecter/logs/us_federation_quant.log` được ghi liên tục; `Architecter/logs/heartbeat_us_federation_quant.json` cập nhật mỗi ~60s (vòng chậm).
- [ ] `Architecter/logs/fleet_audit.jsonl` (đường dẫn do `FleetHeartbeat` dựng từ `LOG_DIR`) **được tạo và mỗi dòng là JSON hợp lệ**: `python -c "import json;[json.loads(l) for l in open('logs/fleet_audit.jsonl',encoding='utf-8')]"`. Chưa kiểm chứng sự kiện nào ghi vào file này; nếu file không xuất hiện/rỗng sau 24h có lệnh, ghi nhận là phát hiện mới và báo lại, không bỏ qua.
- [ ] Vòng nhanh 3s chạy đều (log timeline/dashboard), không có chuỗi `sleep(5)` lỗi lặp lại.

**C2. Hành vi giao dịch so với bản cũ (đối chiếu, không kỳ vọng giống từng lệnh)**
- [ ] Mọi lệnh mở trên demo đều có SL và TP vật lý trong terminal MT5.
- [ ] So số lệnh/khối lượng/giờ vào với bản cũ cùng ngày: khác biệt phải giải thích được bằng ADR-003/004/005 hoặc bằng phân bổ Carver ngẫu nhiên (mục 7 ADR Backlog); khác biệt không giải thích được thì **dừng triển khai**.
- [ ] Không có lệnh nào vượt trần lỗ cứng ($15 forex, $60 chỉ số) tại SL.

**C3. ADR-004: `sym_info` fail-closed**
- [ ] Ghi nhận (log) các lượt pod bị bỏ do gate `trade_mode` khi thị trường đóng/nghỉ lễ; xác nhận pod đó **không** đặt lệnh.
- [ ] Thử có kiểm soát: trên demo, ngắt MT5 terminal ngắn (hoặc dùng mã ngoài giờ giao dịch) trong khi bot quét; kỳ vọng: pod bị bỏ, không có lệnh với `digits`/`point` sai, bot tự kết nối lại (reconnect retry) và quét tiếp.
- [ ] Không có `NameError` liên quan `sym_info` trong log.

**C4. ADR-005: chốt SL**
- [ ] Chạy `tests/test_golden_order_submission.py` (7 kịch bản `adr5_*`) xanh. Trên demo không cố ý tạo SL xấu; nếu log xuất hiện `[HARD SL REQUIRED]` thì điều tra nguồn SL (ví dụ giá rất thấp làm SL <= 0).

**C5. ADR-003: thử `manual_emergency_shutdown` TRÊN DEMO (bắt buộc, chỉ demo)**
- [ ] Xác nhận lần nữa tài khoản đang kết nối là DEMO (số tài khoản/server) trước khi thử. **Tuyệt đối không thử trên live.**
- [ ] Mở sẵn vài vị thế demo gồm cả lãi và lỗ, nhiều mã, ít nhất một mã đã ngoài giờ giao dịch (để gặp lệnh đóng thất bại).
- [ ] Kích hoạt đường khẩn cấp theo cách test an toàn (ví dụ script riêng gọi `kill_switch.manual_emergency_shutdown(reason, broker_connector=mt5_mgr, executor=...)` trên demo; **không** hạ ngưỡng -12% trong config sản xuất).
- [ ] Kỳ vọng: log `[EMERGENCY LIQUIDATION ACTIVATED]`, đóng **cả lệnh lãi lẫn lỗ**; lệnh đóng lỗi có log lỗi + cảnh báo, các lệnh còn lại vẫn được đóng; có 1 lượt quét lại cho ticket sót; `is_locked=True` và không mở lệnh mới trong 24h; sau đó tiến trình thoát mã 99 (nếu đi qua `pipeline`).
- [ ] Sau thử nghiệm: kiểm tra terminal MT5 không còn vị thế sót; nếu còn, ghi nguyên nhân (retcode). **Lưu ý đã biết:** ngoại lệ ném ra từ `close_position` chỉ có log lỗi, không có cảnh báo riêng.
- [ ] Mở khóa bằng `unlock_federation(token)` hoặc khởi động lại với state sạch trước khi tiếp tục theo dõi; ghi lại đã làm gì.

**C6. Tiêu chí kết thúc 24h**
- [ ] Không có crash/restart ngoài ý muốn; không traceback lặp; heartbeat không đứt quá 5 phút.
- [ ] Không có lệnh không SL/TP; không lệnh với tham số mã sai.
- [ ] Mục C2 không có khác biệt vô lý. Ghi kết quả vào báo cáo ngắn (ngày, commit, số lệnh, bất thường).

## D. Cổng duyệt chuyển live (chủ hệ thống tự quyết)
- [ ] Báo cáo Shadow 24h đạt toàn bộ mục C; các bất thường (nếu có) đã có người nhận xử lý.
- [ ] Chủ hệ thống duyệt rõ ràng việc đổi sang `Layer-didece` trên tài khoản live (không tự động).
- [ ] Thời điểm chuyển: ngoài giờ giao dịch (cuối tuần/ngoài phiên), không có vị thế mở đang cần quản lý; nếu có vị thế mở từ bản cũ, quyết định trước ai quản lý chúng (state two-tier/HWM đã copy ở mục A).
- [ ] Sau khi chuyển: theo dõi sát giờ đầu (vòng 60s đầu tiên, lần quét đầu, lệnh đầu tiên phải có SL/TP).

## E. Đường lui
- [ ] Giữ nguyên thư mục + `.env` + `data/` + `logs/` của bản cũ (đã sao lưu ở mục A); không xóa trong ít nhất 1 tuần.
- [ ] Quay lại bản cũ: dừng bot mới (mã thoát/`systemctl stop`), `git checkout` về nhánh/commit cũ hoặc trỏ lại thư mục cũ, đảm bảo `data/` và `logs/` khớp thời điểm dừng, khởi động lại bằng entrypoint cũ.
- [ ] Nếu đã thanh lý khẩn cấp (mã 99): **không** tự khởi động lại; kiểm tra tài khoản, nguyên nhân drawdown, rồi mới mở khóa.

## F. Việc còn mở sau triển khai (không chặn Shadow 24h)
- ADR Backlog mục 2, 3, 7, 8 và phần TP/SL đúng phía của mục 4 (xem `ARCHITECTURE.md`).
- `NuclearKillSwitch` (L5) và `PORTFOLIO_NUCLEAR_LIMIT` chưa được rà theo ADR-003.
- Dashboard (`print_constitutional_dashboard`, `log_timeline_status`) chưa chuyển sang L6.
