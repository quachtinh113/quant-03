> **CẢNH BÁO VẬN HÀNH:** Khi deploy lên VPS live, bắt buộc copy `trial_ledger.jsonl` và `vault_data` từ `02_validation/` cũ sang `data/` trước khi khởi động bot.

# Kiến trúc 6 tầng (mỗi tầng đúng 1 file)

Luồng chạy: `L1 Data → L2 Alpha → L3 Sizing → L4 Risk → L5 Execution → L6 Telemetry`.
Điểm vào duy nhất: `python core/live_federation_runner.py` (hoặc `start_bot.bat`). Hợp đồng dữ liệu dùng chung: `layers/contracts.py` (một file).

| Tầng | File | Nội dung chính |
|---|---|---|
| L1 Data | `layers/l1_data.py` | cổng đọc dữ liệu: `symbol_spec`, `bars_with_fallback`, `history_deals` (→ `SymbolSpec`/`DealView`); adapter `MarketView`; bộ lọc phiên (HK50, giờ độc hại) |
| L2 Alpha | `layers/l2_alpha.py` | ML meta-labeling, formulaic alphas, MIT/Dalio, Congress/Senate/House, combined arms, **registry + pod chiến lược** |
| L3 Sizing | `layers/l3_sizing.py` | allocator QE/QT (Carver), ma trận lãi suất, Quad-Titan, quỹ thanh khoản; toán lot (`hard_risk_cap_lot`, `risk_adjusted_lot`); sizing lệnh vào hai giai đoạn (`size_entry` trước risk desk, `finalize_entry` sau risk desk) |
| L4 Risk | `layers/l4_risk.py` | **cổng `evaluate_risk(...)`** (trần lỗ, breakeven, profit ladder, two-tier, EOD, sweeper), Central Risk Desk + kill switch, VaR/CVaR, warrant/Supreme Court, HWM, fleet guard |
| L5 Execution | `layers/l5_execution.py` | `execute_directives`, `MT5ConnectionManager`, order state machine, trailing stop, router + thuật toán thực thi, MT5 live connector, TCA |
| L6 Telemetry | `layers/l6_telemetry.py` | audit logger, telemetry/heartbeat, Gemini router |

L4 chỉ SINH chỉ thị (`CloseDirective`, `ModifyDirective`, …); L5 thực thi và áp nhánh `on_success`/`on_failure`.
Phụ thuộc chéo duy nhất: L4 và L5 import `get_logger` từ L6 (logging là đáy của mọi tầng).

## Bố cục thư mục (Chuẩn Quỹ Định Lượng Hoàn Chỉnh - Institutional Standard)
| Thư mục | Vai trò | Nội dung |
|---|---|---|
| `layers/` | **layer**: 6 tầng định lượng + hợp đồng | `l1_data … l6_telemetry`, `contracts.py`, `__init__.py` |
| `core/` | **core**: bộ điều phối hệ thống + runner | `live_federation_runner.py`, `pipeline.py`, `federation_hub.py`, `institutional_governance_rules.py`, `__init__.py` |
| `configs/` | **configs**: cấu hình & hiến pháp | `constitution/*.yaml` (Hiến pháp max DD, VaR), `.env.example` |
| `docs/` | **docs**: tài liệu kiến trúc & quyết định | `ARCHITECTURE.md`, `DEPLOY_CHECKLIST_6LAYERS.md`, `adr/` (ADR-003, ADR-004, ADR-005) |
| `tests/` | **tests**: toàn bộ test suite | 34 files test (gồm `golden/`) phát hiện và kiểm thử độc lập |
| `research/` | **research**: mô hình backtest & nghiên cứu | 10 script backtest (36 tháng, 50 states, cross-asset matrix) |
| `scripts/` | **scripts**: tiện ích vận hành & kiểm toán | `deploy/` (service, `.reg`), `ops_windows/` (.ps1, .bat), `audit/` (các script audit & diagnostics) |
| `data/` | **data**: dữ liệu bền vững | `vault_data/`, `trial_ledger.jsonl`, `macro_calendar_cache.json` |
| `logs/` | **logs**: logs & trạng thái runtime | `us_federation_quant.log`, `*.json`, `*.db`, `*.lock` (gitignored) |

- `core/pipeline.py`: bản đồ điều phối một trang `run_one_cycle(rt, st, now_utc)` (đọc từ trên xuống qua 6 tầng; `CycleState`/`CycleResult` ở `layers/contracts.py`).
  Vòng `while _running`, xử lý lỗi và `sleep` nằm ở `USFederationQuantRuntime.run()`.
- Khởi chạy: `start_bot.bat` ở root thư mục gói, hoặc `python core/live_federation_runner.py`, hoặc service systemd `scripts/deploy/us_federation_quant.service`.
- Runner tính `_DIR` là thư mục gói `us_federation_quant/`: `.env` ở root `us_federation_quant/`; `logs/` ở `us_federation_quant/logs/`; `data/` ở `us_federation_quant/data/`; `configs/` ở `us_federation_quant/configs/`.
- Phụ thuộc ngược còn tồn tại (ghi nhận, chưa sửa): `layers/l4_risk` import `core/institutional_governance_rules` (ADR Backlog mục 9).

## Config & dữ liệu
- `configs/constitution/*.yaml`: config gốc, nội dung không đổi (kiểm bằng SHA-256).
- `data/macro_calendar_cache.json`: cache lịch vĩ mô.
- `data/`: dữ liệu ghi lúc chạy (`vault_data/`, `trial_ledger.jsonl`). `logs/`: log và state vận hành.

## Ánh xạ thư mục cũ → tầng mới
| Cũ | Mới |
|---|---|
| `01_alpha/` | `layers/l2_alpha.py` |
| `02_validation/` | `layers/l4_risk.py` |
| `03_portfolio/federal_reserve/` | `layers/l3_sizing.py` |
| `03_portfolio/the_50_states/` | `layers/l2_alpha.py` |
| `04_execution/`, `execution_layer/` | `layers/l5_execution.py` |
| `05_risk/the_fourth_estate/`, `core/high_water_mark`, `core/fleet_guard` | `layers/l4_risk.py` |
| `core/{order_state_machine,mt5_connection_manager}` | `layers/l5_execution.py` |
| `core/{audit_logger,fleet_telemetry,gemini_router}` | `layers/l6_telemetry.py` |
| `05_risk/the_constitution/*.yaml` | `configs/constitution/*.yaml` |
| `core/macro_calendar_cache.json` | `data/macro_calendar_cache.json` |

Đã xóa (không ai dùng): `judicial_audit_backtest_overfitting`, `macro_news_engine`, `telegram_ops_bot`, `fed_monetary_engine`.
Khôi phục khi cần: `git show HEAD:us_federation_quant/<đường-dẫn-cũ>`.

Mỗi khối trong file tầng có tiêu đề `# ==== <đường-dẫn-cũ> ====` để truy nguyên nguồn gốc. Các tên `logger__<module>` và
`<Tên>__pod` là kết quả của việc đổi tên khi trùng tên cấp module lúc gộp.

## Nợ kỹ thuật cần mở ADR (sau khi chia xong 6 tầng)
Các mục dưới đây là hành vi được GIỮ NGUYÊN trong lúc tái cấu trúc; mỗi mục cần chủ hệ thống quyết định riêng (đổi hành vi giao dịch).

1. ✅ **ĐÃ XỬ LÝ — ADR-003** (`ADR/ADR-003-emergency-full-liquidation.md`). Trước đây: **`manual_emergency_shutdown` / `update_equity` chạm ngưỡng -12% không đóng lệnh.** Tên là "emergency liquidation" nhưng mã chỉ
   chạy soft de-risking: dời SL về entry±15 point cho lệnh đang LÃI, giữ nguyên lệnh LỖ, đóng băng tín hiệu mới 24 giờ.
   (golden: `tests/test_golden_emergency_derisking.py`.)
2. **Trần lỗ cứng chồng chéo:** `forex_portfolio` ($15) không loại NAS100/DJ30/SP500 nên đè lên trần chỉ số ($60); GBPCHF/UK100
   bị hai trần $15 phủ lên nhau; `.replace("M","")` xóa mọi chữ M trong tên mã. (golden: `tests/test_golden_l5_hard_caps.py`.)
3. **Two-tier exit:** vị thế 0.01L vừa dời SL về hòa vốn vừa rơi xuống khóa lãi $15 trong cùng một lượt; đóng partial thất bại vẫn
   rơi xuống khóa lãi và không ghi state. (golden: `tests/test_golden_l4_exits.py`.)
4. ◐ **SL: ĐÃ XỬ LÝ — ADR-005** (`ADR/ADR-005-mandatory-hard-sl.md`); TP và SL đúng phía giá vẫn mở. Trước đây: **Chưa có chốt SL/TP bắt buộc ở L5** (`submit_order_intent`); `fleet_guard` được khởi tạo nhưng không ai gọi.
5. ✅ **Đã có golden G1** (`tests/test_golden_scan_pipeline.py`, 62 kịch bản). Test cũ của hàm này vẫn fail từ baseline (chưa xử lý).
6. ✅ **ĐÃ XỬ LÝ — ADR-004** (`ADR/ADR-004-fail-closed-symbol-info.md`). Trước đây: **`scan_and_route_state_proposals` dùng lại `sym_info` của pod vòng lặp trước khi `mt5.symbol_info` ném ngoại lệ.** Gate `trade_mode`
   nuốt ngoại lệ và không gán `sym_info`; các bước sau (`point`, `trade_stops_level`, `spread`, `digits`) dùng giá trị còn sót từ pod
   trước (hoặc `NameError` nếu là pod đầu tiên), có thể đặt lệnh với `digits` của mã khác. (Đã bỏ giá trị đánh dấu `l1_data.UNSET`.) (golden: `tests/test_golden_trade_mode_gate.py`.)
7. **Phân bổ Carver trong `scan_and_route_state_proposals` dùng lợi suất giả ngẫu nhiên** (`np.random.normal`, 40 nến, mỗi lần quét): quota/IDM
   thay đổi không tất định giữa các lần quét. Golden phải cố định seed. (golden: `tests/test_golden_scan_pipeline.py`.)
8. **Gate giờ độc hại ngay trước khi gửi lệnh gần như không thể chạm tới**: vòng quét đã `return` sớm ở cùng tập `TOXIC_HOURS`; chỉ khác khi
   giờ UTC chuyển qua mốc 0/6/18/23 giữa chừng một lần quét.
9. **Phụ thuộc ngược tầng -> app:** `Anpha/l4_risk` import `Architecter/institutional_governance_rules` (cùng `federation_hub` ở chiều ngược lại). Giữ nguyên trong đợt tổ chức lại 5 thư mục; cần quyết định chuyển module quản trị vào `Anpha/` hay đảo phụ thuộc.
