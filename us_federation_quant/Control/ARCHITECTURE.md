> **CẢNH BÁO VẬN HÀNH:** Khi deploy lên VPS live, bắt buộc copy `trial_ledger.jsonl` và `vault_data` từ `02_validation/` cũ sang `Project/data/` trước khi khởi động bot.

# Kiến trúc 6 tầng (mỗi tầng đúng 1 file)

Luồng chạy: `L1 Data → L2 Alpha → L3 Sizing → L4 Risk → L5 Execution → L6 Telemetry`.
Điểm vào duy nhất: `python Architecter/live_federation_runner.py`. Hợp đồng dữ liệu dùng chung: `Anpha/contracts.py` (một file).

| Tầng | File | Nội dung chính |
|---|---|---|
| L1 Data | `Anpha/l1_data.py` | cổng đọc dữ liệu: `symbol_spec`, `bars_with_fallback`, `history_deals` (→ `SymbolSpec`/`DealView`); adapter `MarketView`; bộ lọc phiên (HK50, giờ độc hại) |
| L2 Alpha | `Anpha/l2_alpha.py` | ML meta-labeling, formulaic alphas, MIT/Dalio, Congress/Senate/House, combined arms, **registry + pod chiến lược** |
| L3 Sizing | `Anpha/l3_sizing.py` | allocator QE/QT (Carver), ma trận lãi suất, Quad-Titan, quỹ thanh khoản; toán lot (`hard_risk_cap_lot`, `risk_adjusted_lot`); sizing lệnh vào hai giai đoạn (`size_entry` trước risk desk, `finalize_entry` sau risk desk) |
| L4 Risk | `Anpha/l4_risk.py` | **cổng `evaluate_risk(...)`** (trần lỗ, breakeven, profit ladder, two-tier, EOD, sweeper), Central Risk Desk + kill switch, VaR/CVaR, warrant/Supreme Court, HWM, fleet guard |
| L5 Execution | `Anpha/l5_execution.py` | `execute_directives`, `MT5ConnectionManager`, order state machine, trailing stop, router + thuật toán thực thi, MT5 live connector, TCA |
| L6 Telemetry | `Anpha/l6_telemetry.py` | audit logger, telemetry/heartbeat, Gemini router |

L4 chỉ SINH chỉ thị (`CloseDirective`, `ModifyDirective`, …); L5 thực thi và áp nhánh `on_success`/`on_failure`.
Phụ thuộc chéo duy nhất: L4 và L5 import `get_logger` từ L6 (logging là đáy của mọi tầng).

## Bố cục thư mục (5 thư mục trong `us_federation_quant/`, import `us_federation_quant.<Thư mục>.<module>`)
| Thư mục | Vai trò | Nội dung |
|---|---|---|
| `Anpha/` | **layer**: 6 tầng + hợp đồng | `l1_data … l6_telemetry`, `contracts.py`, `__init__.py`; thư mục rỗng `cacullatorl/`, `Maching_learrning/`, `New folder/` do chủ hệ thống tạo sẵn (chưa dùng) |
| `Architecter/` | **app**: ứng dụng chạy bot + vận hành | `live_federation_runner.py`, `pipeline.py`, `federation_hub.py`, `institutional_governance_rules.py`, `start_bot.bat`, `deploy/` (service, `.reg`), script Windows (`.ps1`/`.bat`), `.env.example`, `logs/`, `us_federation_quant.lock` |
| `Control/` | **control**: luật, quyết định, kiểm chứng | `config/` (hiến pháp YAML, lịch vĩ mô), `ADR/`, tài liệu này, `DEPLOY_CHECKLIST_6LAYERS.md`, `tests/` (gồm `golden/`) |
| `Emegercey/` | **emergency** (dành riêng, hiện RỖNG) | quản trị **drawdown trong ngày và trong tuần** và thao tác khẩn cấp khi sàn giật/lag lúc có tin lớn; chưa có mã. Mã liên quan hiện còn ở nơi khác: ngắt mạch DD ngày (tài khoản -2%, pod -1.5%) trong `Architecter/live_federation_runner.py`, HWM/re-anchoring tuần và thang DD + kill switch trong `Anpha/l4_risk.py`. **Chưa có giới hạn DD tuần riêng** (chỉ có re-anchoring HWM theo tuần) |
| `Project/` | **project**: nghiên cứu, công cụ, dữ liệu | `research/`, script audit, `update_live_whitelist.py`, `gold_oracle_trading_bot.py`, `diagnostics_smoke_test.py`, `requirements.txt`, `data/` (`vault_data/`, `trial_ledger.jsonl`), `.agents/`, bản sao lưu runner cũ |

- `Architecter/pipeline.py`: bản đồ điều phối một trang `run_one_cycle(rt, st, now_utc)` (đọc từ trên xuống qua 6 tầng; `CycleState`/`CycleResult` ở `Anpha/contracts.py`).
  Vòng `while _running`, xử lý lỗi và `sleep` nằm ở `USFederationQuantRuntime.run()`.
- Khởi chạy: `python live_federation_runner.py` trong `Architecter/start_bot.bat`, hoặc `python3 Architecter/live_federation_runner.py` (service systemd).
- Runner tính `_DIR` là thư mục gói `us_federation_quant/`: `.env`, `logs/`, file khóa ở `Architecter/`; `data/` ở `Project/`; `config/` ở `Control/`.
- Phụ thuộc ngược còn tồn tại (ghi nhận, chưa sửa): `Anpha/l4_risk` import `Architecter/institutional_governance_rules` (ADR Backlog mục 9).

## Config & dữ liệu
- `Control/config/constitution/*.yaml`, `Control/config/macro_calendar_cache.json`: config gốc, nội dung không đổi (kiểm bằng SHA-256).
- `Project/data/`: dữ liệu ghi lúc chạy (`vault_data/`, `trial_ledger.jsonl`). `Architecter/logs/`: log và state vận hành.

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
