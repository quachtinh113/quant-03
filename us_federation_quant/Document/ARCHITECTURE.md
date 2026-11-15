> **CẢNH BÁO VẬN HÀNH:** Khi deploy lên VPS live, bắt buộc copy `trial_ledger.jsonl` và `vault_data` từ `02_validation/` cũ sang `data/` trước khi khởi động bot.

# Kiến trúc 6 tầng (mỗi tầng đúng 1 file)

Luồng chạy: `L1 Data → L2 Alpha → L3 Sizing → L4 Risk → L5 Execution → L6 Telemetry`.
Điểm vào duy nhất: `python live_federation_runner.py`. Hợp đồng dữ liệu dùng chung: `contracts.py` (một file).

| Tầng | File | Nội dung chính |
|---|---|---|
| L1 Data | `layers/l1_data.py` | cổng đọc dữ liệu: `symbol_spec`, `bars_with_fallback`, `history_deals` (→ `SymbolSpec`/`DealView`); adapter `MarketView`; bộ lọc phiên (HK50, giờ độc hại) |
| L2 Alpha | `layers/l2_alpha.py` | ML meta-labeling, formulaic alphas, MIT/Dalio, Congress/Senate/House, combined arms, **registry + pod chiến lược** |
| L3 Sizing | `layers/l3_sizing.py` | allocator QE/QT (Carver), ma trận lãi suất, Quad-Titan, quỹ thanh khoản |
| L4 Risk | `layers/l4_risk.py` | **cổng `evaluate_risk(...)`** (trần lỗ, breakeven, profit ladder, two-tier, EOD, sweeper), Central Risk Desk + kill switch, VaR/CVaR, warrant/Supreme Court, HWM, fleet guard |
| L5 Execution | `layers/l5_execution.py` | `execute_directives`, `MT5ConnectionManager`, order state machine, trailing stop, router + thuật toán thực thi, MT5 live connector, TCA |
| L6 Telemetry | `layers/l6_telemetry.py` | audit logger, telemetry/heartbeat, Gemini router |

L4 chỉ SINH chỉ thị (`CloseDirective`, `ModifyDirective`, …); L5 thực thi và áp nhánh `on_success`/`on_failure`.
Phụ thuộc chéo duy nhất: L4 và L5 import `get_logger` từ L6 (logging là đáy của mọi tầng).

## Bố cục thư mục
- `Document/`: các module gốc của gói (`contracts.py`, `federation_hub.py`, `live_federation_runner.py`, `institutional_governance_rules.py`,
  script audit/vận hành, `.ps1`/`.bat`, `.env.example`, `requirements.txt`, tài liệu này). Import theo `us_federation_quant.Document.<module>`.
- `layers/`, `config/`, `data/`, `logs/`, `deploy/`, `research/`, `tests/` nằm ở `us_federation_quant/`; `start_bot.bat` vẫn ở gốc gói.
- Khởi chạy: `python Document\live_federation_runner.py` (trong `start_bot.bat`) hoặc `python3 Document/live_federation_runner.py` (service).
- Runner tính `_DIR` là thư mục `us_federation_quant/` (không phải `Document/`): `.env`, `logs/` (HWM, state), `config/`, `data/` giữ nguyên vị trí.

## Config & dữ liệu
- `config/constitution/*.yaml`, `config/macro_calendar_cache.json`: config gốc, nội dung không đổi (kiểm bằng SHA-256).
- `data/`: dữ liệu ghi lúc chạy (`vault_data/`, `trial_ledger.jsonl`). `logs/`: log và state vận hành.
- Bộ skill/quy tắc cho agent đã chuyển ra `../.agents/` (ngoài gói).

## Ánh xạ thư mục cũ → tầng mới
| Cũ | Mới |
|---|---|
| `01_alpha/` | `l2_alpha` |
| `02_validation/` | `l4_risk` |
| `03_portfolio/federal_reserve/` | `l3_sizing` |
| `03_portfolio/the_50_states/` | `l2_alpha` |
| `04_execution/`, `execution_layer/` | `l5_execution` |
| `05_risk/the_fourth_estate/`, `core/high_water_mark`, `core/fleet_guard` | `l4_risk` |
| `core/{order_state_machine,mt5_connection_manager}` | `l5_execution` |
| `core/{audit_logger,fleet_telemetry,gemini_router}` | `l6_telemetry` |
| `05_risk/the_constitution/*.yaml`, `core/macro_calendar_cache.json` | `config/` |

Đã xóa (không ai dùng): `judicial_audit_backtest_overfitting`, `macro_news_engine`, `telegram_ops_bot`, `fed_monetary_engine`.
Khôi phục khi cần: `git show HEAD:us_federation_quant/<đường-dẫn-cũ>`.

Mỗi khối trong file tầng có tiêu đề `# ==== <đường-dẫn-cũ> ====` để truy nguyên nguồn gốc. Các tên `logger__<module>` và
`<Tên>__pod` là kết quả của việc đổi tên khi trùng tên cấp module lúc gộp.

## Nợ kỹ thuật cần mở ADR (sau khi chia xong 6 tầng)
Các mục dưới đây là hành vi được GIỮ NGUYÊN trong lúc tái cấu trúc; mỗi mục cần chủ hệ thống quyết định riêng (đổi hành vi giao dịch).

1. **`manual_emergency_shutdown` / `update_equity` chạm ngưỡng -12% không đóng lệnh.** Tên là "emergency liquidation" nhưng mã chỉ
   chạy soft de-risking: dời SL về entry±15 point cho lệnh đang LÃI, giữ nguyên lệnh LỖ, đóng băng tín hiệu mới 24 giờ.
   (golden: `tests/test_golden_emergency_derisking.py`.)
2. **Trần lỗ cứng chồng chéo:** `forex_portfolio` ($15) không loại NAS100/DJ30/SP500 nên đè lên trần chỉ số ($60); GBPCHF/UK100
   bị hai trần $15 phủ lên nhau; `.replace("M","")` xóa mọi chữ M trong tên mã. (golden: `tests/test_golden_l5_hard_caps.py`.)
3. **Two-tier exit:** vị thế 0.01L vừa dời SL về hòa vốn vừa rơi xuống khóa lãi $15 trong cùng một lượt; đóng partial thất bại vẫn
   rơi xuống khóa lãi và không ghi state. (golden: `tests/test_golden_l4_exits.py`.)
4. **Chưa có chốt SL/TP bắt buộc ở L5** (`submit_order_intent`); `fleet_guard` được khởi tạo nhưng không ai gọi.
5. **`scan_and_route_state_proposals` (~480 dòng) chưa có golden**; test hiện có của nó fail từ baseline.
6. **`scan_and_route_state_proposals` dùng lại `sym_info` của pod vòng lặp trước khi `mt5.symbol_info` ném ngoại lệ.** Gate `trade_mode`
   nuốt ngoại lệ và không gán `sym_info`; các bước sau (`point`, `trade_stops_level`, `spread`, `digits`) dùng giá trị còn sót từ pod
   trước (hoặc `NameError` nếu là pod đầu tiên), có thể đặt lệnh với `digits` của mã khác. Đang được giữ nguyên bằng giá trị đánh dấu
   `l1_data.UNSET`. (golden: `tests/test_golden_trade_mode_gate.py`.)
