---
trigger: always_on
---

# Quy tắc tự động thực thi (Autonomous Execution Policy)

1. **Tự động chạy lệnh không cần hỏi lại** đối với toàn bộ nhóm lệnh an toàn:
   - Kiểm thử & phân tích: `pytest`, `python -m pytest`, `python -m py_compile`, `grep`, `Select-String`, `Get-ChildItem`.
   - Thao tác Git an toàn: `git status`, `git diff`, `git log`, `git mv`, `git add`, `git commit`, `git push origin Layer-didece`.
   - Chỉnh sửa mã nguồn trong `layers/`, `core/`, `tests/`, `docs/`, `scripts/`, `configs/` khi đã có kế hoạch được duyệt.

2. **Tự động xác minh (Self-Verification Loop):**
   - Sau mỗi lần sửa code hoặc di chuyển file, tự động chạy `pytest tests/ -q` để kiểm tra. Nếu pass đúng baseline (181 pass / 14 fail), tự động tiến hành bước tiếp theo cho đến khi hoàn tất toàn bộ yêu cầu của user rồi mới báo cáo một lần duy nhất.

3. **Danh sách đỏ (Bắt buộc dừng lại hỏi — Không bao giờ tự ý chạy):**
   - Khởi chạy bot giao dịch tiền thật (`live`) hoặc mở kết nối MT5 đặt lệnh thật (`live_federation_runner.py` trên tài khoản thật).
   - Đọc, ghi đè hoặc commit file `.env` thật.
   - Các lệnh phá hủy lịch sử: `git reset --hard`, `git push --force`, `rm -rf` trên `data/` hoặc `logs/`.
