# BÁO CÁO KIỂM TOÁN HIỆU SUẤT & BẢO VỆ LỢI NHUẬN THỰC CHIẾN (LIVE AUDIT)
*Thời điểm kiểm toán: 2026-11-17 05:01:10 GMT+7 | Tài khoản: Exness MT5 #463960823*

---

## 1. SỨC KHỎE TIẾN TRÌNH & ĐỈNH VỐN (SYSTEM & EQUITY HEALTH)
* **Tiến trình Bot:** `PID 5224` | Uptime: `0:03:44` | RAM: `67.2 MB` (Ngưỡng an toàn < 250MB) | Trạng thái: **HEALTHY / RUNNING**
* **Khóa độc quyền (Mutex Lock):** `us_federation_quant.lock` đang được giữ độc quyền bởi PID 5224.
* **Độ trễ Ping máy chủ Exness:** `26.4 ms` (Rất thấp, đạt chuẩn giao dịch HFT/Quant).
* **Số dư (Balance):** `$7,520.24 USD`
* **Tài sản ròng (Equity):** `$7,536.34 USD` (Lãi trôi nổi: `+$16.10 USD`)
* **Đỉnh vốn (High-Water Mark):** `$7,542.38 USD`
* **Mức sụt giảm vốn hiện tại (Current Drawdown):** **-0.08%** (Gần như zero drawdown).

---

## 2. NGHIỆM THU HIỆU QUẢ BẢN VÁ MỚI (POST-PATCH ATTRIBUTION)

### A. Tiến độ Mục tiêu +$100.00/Ngày:
* **Realized PnL (24h qua):** `+$6.18 USD` (16 lệnh đã đóng)
* **Locked Profit (Lợi nhuận đã khóa trên lệnh mở):** `+$4.50 USD` (Vị thế `USTEC` SELL 0.05L đã khóa SL dương tại +$4.50)
* **Tổng Effective PnL tích lũy:** **`+$10.68 USD`**
* **Tỷ lệ hoàn thành mục tiêu ngày:** **`10.7%`** (Hệ thống vừa hot-reload lúc 04:57, đang trong giai đoạn tích lũy đầu ngày).

### B. Tỷ lệ Thu hoạch Lợi nhuận (Edge Capture Ratio - ECR):
* **Tỷ lệ thoát non (< +$1.50):** Giảm mạnh từ **`65.9%`** trước nâng cấp xuống còn **`40.0%`** (4/10 lệnh thắng).
* **Số lệnh chạm Tầng 2 (`+$4.50+`):** `2 lệnh` (Bao gồm `AUDJPY +$4.84` và `USTEC` hiện đang chạy `+$11.58`).
* **Số lệnh chạm Tầng 3 (`+$10.00+`):** `1 lệnh` (`USTEC` đạt đỉnh `+$12.21`, đang được bảo vệ ở Tầng 2 để tiến vào Tầng 3).

### C. Chuẩn hóa Khối lượng (Elite Alpha Universe):
* `AUDUSD` / `NZDUSD`: Capped ATR ở `28.0 pips` -> Lot chuẩn định cỡ ở `0.04L` (Ngân sách rủi ro $11.25).
* `USDCHF`: Định cỡ chuẩn ở `0.03L`.
* `EURJPY` / `EURAUD`: Đang vận hành ở `0.02L - 0.05L`.
* `GBPCHF`: Đã bị kiềm chế ở `0.04L` (Loại bỏ triệt để tình trạng nhồi 0.08L).

---

## 3. BẢNG BẢO VỆ VỊ THẾ ĐANG MỞ (REAL-TIME POSITION GUARD)

| Ticket | Cặp GD | Lệnh / Lot | Giá Mở | Giá Hiện Tại | Stop Loss (SL) | Rủi ro tại SL (USD) | Lãi Hiện Tại | Trạng Thái Bậc Thang |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `#2863465984` | **USTEC** | **SELL 0.05L** | 27461.56 | 27229.99 | **27371.56** | **+$4.50 (ĐÃ KHÓA LÃI)** | **+$11.58** | **TIER 2 RUNNER (Khóa +$4.50)** |
| `#2861866358` | **EURAUD** | BUY 0.02L | 1.63055 | 1.63212 | 1.62968 | -$1.17 | **+$2.12** | Chờ chạm T1 (Trig +$4.00) |
| `#2864437858` | **EURGBP** | SELL 0.05L | 0.83445 | 0.83422 | 0.83521 | -$5.01 | **+$1.52** | Chờ chạm T1 (Trig +$4.00) |
| `#2864270179` | **GBPCHF** | BUY 0.04L | 1.10741 | 1.10753 | 1.10559 | -$8.67 | **+$0.57** | An toàn dưới Cap $14.50 |
| `#2864298359` | **EURJPY** | SELL 0.05L | 175.370 | 175.356 | 175.723 | -$11.07 | **+$0.44** | An toàn dưới Cap $14.50 |
| `#2864567673` | **EURUSD** | SELL 0.01L | 1.09984 | 1.09980 | 1.10196 | -$2.12 | **+$0.04** | An toàn dưới Cap $14.50 |
| `#2864584475` | **USDCAD** | BUY 0.05L | 1.42977 | 1.42972 | 1.42824 | -$5.35 | -$0.17 | An toàn dưới Cap $14.50 |

* **Kiểm tra Hard Risk Cap:** 100% vị thế mở có rủi ro tại SL `<= -$14.50 USD` (Mức rủi ro cao nhất là EURJPY `-$11.07`).
* **Cảnh báo Cụm Tiền Tệ (Currency Cluster Risk):**
  * `USD`: 2 lệnh Long (`EURUSD` Sell + `USDCAD` Buy) $\rightarrow$ Đạt trần tối đa 2 vị thế (Tuân thủ nghiêm ngặt).
  * `JPY`: 1 lệnh Long (`EURJPY` Sell) $\rightarrow$ Đạt trần tối đa 1 vị thế (Tuân thủ nghiêm ngặt).
  * `EUR`: Net Short (1 Long `EURAUD` đối ứng 3 Short `EURJPY`, `EURGBP`, `EURUSD`) $\rightarrow$ Phân tán rủi ro tốt.

---

## 4. KẾT LUẬN & CHỈ ĐẠO
* Hệ thống đang ở trạng thái **`HEALTHY & PROFITABLE`**.
* Không có bất kỳ lỗi thực thi nào trên broker MT5.
* **Quy tắc bất biến:** Không thay đổi tham số Alpha hoặc ML model vì cỡ mẫu sau vá đang tích lũy và vận hành chuẩn xác theo thiết kế toán học.
