// turbo-all
# WORKFLOW: LIVE PROFIT & RISK AUDIT (+100$/DAY INVARIANT)

Quy trình tự động hóa kiểm toán định lượng thời gian thực cho hệ thống `us_federation_quant` trên tài khoản Exness MT5 `#463960823`.

## BƯỚC 1: SỨC KHỎE TIẾN TRÌNH & ĐỈNH VỐN
1. Kiểm tra tiến trình `live_federation_runner.py`:
   - Xác nhận file khóa độc quyền `us_federation_quant.lock` đang được giữ bởi đúng `PID`.
   - Giám sát Uptime, RAM usage (< 250 MB), và độ trễ Ping tới Broker (< 60 ms).
2. Kiểm tra tài khoản MT5:
   - Truy xuất `Balance`, `Equity`, `Floating PnL`.
   - Tính toán `Drawdown` so với `High-Water Mark` ($7,542.38). Cảnh báo nếu DD vượt quá 1.5%.

## BƯỚC 2: ĐỐI SOÁT HIỆU NĂNG & TIẾN ĐỘ +100$/NGÀY
1. Tính tổng `Effective PnL` = `Realized PnL 24h` + `Locked Profit` (lợi nhuận đã khóa ở các lệnh mở).
2. So sánh tiến độ với mục tiêu:
   $$\text{Progress \%} = \frac{\text{Effective PnL}}{100.00} \times 100\%$$
3. Đo lường tỷ lệ `Edge Capture Ratio` (ECR):
   - Đảm bảo tỷ lệ thoát non (< $1.50) duy trì dưới 45%.
   - Ghi nhận số lệnh chạm Tier 2 (+$4.50+) và Tier 3 (+$10.00+).
4. Kiểm tra khối lượng mở mới:
   - Các cặp Elite Alpha (`AUDUSD`, `NZDUSD`, `USDCHF`, `EURAUD`, `EURJPY`, `UK100`) đạt quy mô `0.03L - 0.05L`.
   - `GBPCHF` bị kiềm chế ở mức `<= 0.04L`.

## BƯỚC 3: BẢO VỆ VỊ THẾ ĐANG MỞ & KHÓA LÃI TỰ ĐỘNG
1. Giám sát Bậc thang Khóa lãi 3 Tầng:
   - Floating PnL >= +$14.50: Khóa SL tại +$10.00 (Tier 3).
   - Floating PnL >= +$8.50: Khóa SL tại +$4.50 (Tier 2).
   - Floating PnL >= +$4.00 (hoặc +$4.80 trong Golden Hours 13:00 - 17:00 UTC): Khóa SL tại Entry + 1.0 pip / +$1.20 (Tier 1).
   - Nếu phát hiện lệnh đủ điều kiện chưa được Broker cập nhật SL, tự động gửi `TRADE_ACTION_SLTP` ngay lập tức.
2. Kiểm tra Universal Hard Risk Cap:
   - Đảm bảo rủi ro tại Stop Loss của 100% vị thế `<= -$14.50 USD`.
3. Kiểm tra rủi ro cụm tiền tệ (`Currency Cluster Limit`):
   - JPY <= 1 vị thế cùng chiều.
   - USD <= 2 vị thế cùng chiều (trừ khi có vị thế đã Free-Ride).

```bash
python C:\Quant_03\us_federation_quant\run_live_audit.py
```
