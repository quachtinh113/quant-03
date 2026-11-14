> **CẢNH BÁO VẬN HÀNH:** Khi deploy lên VPS live, bắt buộc copy `trial_ledger.jsonl` và `vault_data` từ `02_validation/` cũ sang `data/` trước khi khởi động bot.

# Kiến trúc 6 tầng (mỗi tầng đúng 1 file)

Luồng chạy: `L1 Data → L2 Alpha → L3 Sizing → L4 Risk → L5 Execution → L6 Telemetry`.
Điểm vào duy nhất: `python live_federation_runner.py`. Hợp đồng dữ liệu dùng chung: `contracts.py` (một file).

| Tầng | File | Nội dung chính |
|---|---|---|
| L1 Data | `layers/l1_data.py` | adapter MT5 → `MarketView`; bộ lọc phiên (HK50, giờ độc hại) |
| L2 Alpha | `layers/l2_alpha.py` | ML meta-labeling, formulaic alphas, MIT/Dalio, Congress/Senate/House, combined arms, **registry + pod chiến lược** |
| L3 Sizing | `layers/l3_sizing.py` | allocator QE/QT (Carver), ma trận lãi suất, Quad-Titan, quỹ thanh khoản |
| L4 Risk | `layers/l4_risk.py` | **cổng `evaluate_risk(...)`** (trần lỗ, breakeven, profit ladder, two-tier, EOD, sweeper), Central Risk Desk + kill switch, VaR/CVaR, warrant/Supreme Court, HWM, fleet guard |
| L5 Execution | `layers/l5_execution.py` | `execute_directives`, `MT5ConnectionManager`, order state machine, trailing stop, router + thuật toán thực thi, MT5 live connector, TCA |
| L6 Telemetry | `layers/l6_telemetry.py` | audit logger, telemetry/heartbeat, Gemini router |

L4 chỉ SINH chỉ thị (`CloseDirective`, `ModifyDirective`, …); L5 thực thi và áp nhánh `on_success`/`on_failure`.
Phụ thuộc chéo duy nhất: L4 và L5 import `get_logger` từ L6 (logging là đáy của mọi tầng).

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
