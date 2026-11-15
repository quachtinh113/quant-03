# ADR-005: Chốt SL cứng bắt buộc tại `l5_execution.submit_order_intent`

- Trạng thái: **Đã duyệt và triển khai** (chưa chạy live)
- Tầng: L5 Thực thi
- Giải quyết: ADR Backlog mục 4 (phần SL; TP và SL đúng phía giá chưa nằm trong phạm vi)

## Bối cảnh
`submit_order_intent` không kiểm tra SL: đường vào lệnh mới hoặc lỗi tính toán có thể gửi lệnh không SL, vi phạm điều răn "Broker-side SL/TP".

## Quyết định
Ngay đầu hàm, **trước** `state_machine.create_order`: nếu `intent.sl` là `None`, không phải số hữu hạn (`NaN`/`inf`), hoặc `<= 0`:
ghi log `critical`, `intent.warrant.revoke(reason=...)`, trả `None`. Không tạo order state, không gọi `open_market_order`. Cùng hợp đồng trả về với nhánh broker từ chối.

## Hệ quả
Một SL tính ra `<= 0` (ví dụ giá rất thấp) sẽ bị từ chối thay vì gửi đi. Với dữ liệu hợp lệ hiện tại, đường vào lệnh không đổi.

## Kiểm chứng
`tests/test_golden_order_submission.py`: 7 kịch bản mới (`adr5_*`: None, 0, âm, NaN, inf, SELL+None bị từ chối; SL nhỏ hợp lệ vẫn qua). 10 kịch bản cũ không đổi.
