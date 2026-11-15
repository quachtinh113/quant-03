# ADR-004: Gate `trade_mode` fail-closed, không kế thừa `sym_info` của pod trước

- Trạng thái: **Đã duyệt và triển khai** (chưa chạy live)
- Tầng: L1 Dữ liệu (`l1_data.trade_mode_gate`) + vòng pod của `scan_and_route_state_proposals`
- Giải quyết: ADR Backlog mục 6

## Bối cảnh
Gate cũ nuốt mọi ngoại lệ của `mt5.symbol_info` và coi như qua. Biến `sym_info` không được gán, nên các bước sau (`point`, `trade_stops_level`,
`spread`, `digits`) dùng giá trị còn sót từ pod trước (hoặc `NameError` ở pod đầu tiên): có thể đặt lệnh với `digits` của mã khác.

## Quyết định
- `trade_mode_gate(symbol)` trả `(True, None)` khi `symbol_info` là `None`, `trade_mode` khác FULL, **hoặc bất kỳ ngoại lệ nào** (kể cả thiếu hằng số `SYMBOL_TRADE_MODE_FULL`).
- Runner luôn gán `sym_info` từ gate và `continue` khi `skip`. Xóa `l1_data.UNSET` và nhánh giữ giá trị cũ.

## Hệ quả
Lỗi MT5 thoáng qua làm pod đó bỏ lỡ một lượt quét (60s) thay vì vào lệnh với dữ liệu sai. Không đổi hành vi khi MT5 hoạt động bình thường.

## Kiểm chứng
`tests/test_golden_trade_mode_gate.py`: 2 kịch bản đổi (`unit_symbol_info_raises_fail_closed`, `unit_full_const_missing_fail_closed`: từ "qua" sang "bỏ pod"),
1 kịch bản mới xuyên `scan` (`scan_gate_blocks_when_symbol_info_raises`: không gọi `is_market_open`/`get_rates`). Các kịch bản còn lại và G1 không đổi.
