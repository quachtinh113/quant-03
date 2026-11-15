# ADR-003: Thanh lý toàn bộ vị thế khi chạm -12% hoặc `manual_emergency_shutdown`

- Trạng thái: **Đã duyệt và triển khai** (chưa chạy live; kiểm chứng bằng test double)
- Tầng: L4 Rủi ro (quyết định) + L5 Thực thi (đóng lệnh qua `CloseDirective`)
- Giải quyết: ADR Backlog mục 1

## Bối cảnh
`FederalMasterKillSwitch.manual_emergency_shutdown` (đường Nuclear Football trong `pipeline.run_one_cycle`) và `update_equity` (ngưỡng -12%
của `CentralRiskDesk`) gọi `_execute_emergency_liquidation`, nhưng hàm này chỉ chạy soft de-risking: dời SL lệnh đang lãi về entry±15 point,
**giữ nguyên lệnh lỗ**. Tên "emergency liquidation" không khớp hành vi; khi drawdown thật, lệnh lỗ vẫn mở.

## Quyết định (chủ hệ thống chọn phương án (a))
1. Thêm hàm thuần `l4_risk.evaluate_emergency_liquidation(positions)` -> `(plan, directives)`: một `CloseDirective` cho **mọi** vị thế (lãi và lỗ).
2. `_execute_emergency_liquidation` gọi `apply_emergency_liquidation`: khóa mở lệnh mới (`is_locked`, `freeze_until` +24h như cũ), đóng toàn bộ.
3. Lệnh đóng thất bại (kết quả `success=False` hoặc ném ngoại lệ): ghi log lỗi, `AlertDirective` (đường L5), **tiếp tục đóng các lệnh còn lại**.
   Quét lại **tối đa 1 lượt** cho ticket còn sót, chỉ khi broker còn báo vị thế đó đang mở. Sau đó `pipeline` vẫn `sys.exit(99)`.
4. `_legacy_inline_execute` (đường không có executor, ví dụ `update_equity`) bổ sung nhánh `CloseDirective`; nếu không, lệnh đóng sẽ bị bỏ qua im lặng.
5. **Giữ nguyên** `evaluate_soft_derisking` / `apply_soft_derisking` làm API cũ (test `test_quant_core_v9_risk_architecture.py` còn dùng); không còn nằm trên đường khẩn cấp.

## Phạm vi KHÔNG đổi
`NuclearKillSwitch` (L5), `PORTFOLIO_NUCLEAR_LIMIT` (`institutional_governance_rules.py`) và điểm -12% ở `l3_sizing` chưa được rà trong ADR này.

## Hệ quả và rủi ro còn lại
- Đóng hàng loạt ở giá thị trường: có trượt giá; thị trường đóng cửa (retcode 10018) thì lệnh sót vẫn mở, người vận hành phải kiểm tra tay.
- Ngoại lệ ném ra từ `close_position` chỉ được log ở L4 (không qua nhánh `on_failure`); cảnh báo cho trường hợp này do `pipeline` phát chung.
- `close_position` không gắn `comment` riêng (giữ chữ ký chung với `MT5LiveConnector.close_position(ticket)`).
- Mở khóa vẫn cần `unlock_federation` kèm token như cũ.

## Kiểm chứng
`tests/test_golden_emergency_derisking.py`: 3 kịch bản đổi (`manual_get_positions`, `manual_positions_attr`, `update_equity_red_with_broker`);
6 kịch bản `liquidate_*` mới (tất cả lãi/lỗ, một lệnh lỗi, ngoại lệ, quét lại thành công, ticket đã biến mất, rỗng) trên cả đường nội tuyến lẫn executor L5.
Các kịch bản `soft_*` và `manual_no_broker`, `update_equity_red_no_broker` giữ nguyên.
