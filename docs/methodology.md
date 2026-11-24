# Phương pháp (bản rút gọn)

Không phải lời khuyên đầu tư. Dự báo mang tính xác suất và có thể sai.

## Chỉ báo tổng hợp (composites)
Nhiều chỉ báo cùng nhóm được chuẩn hóa (z-score), gộp theo trọng số, rồi xếp hạng phân vị chỉ dùng dữ liệu đã biết tại thời điểm dự báo. Nếu thiếu nguồn, trọng số được tính lại và độ phủ (coverage) được ghi rõ.

## Mức so sánh cơ bản (baselines)
Mọi mô hình được so với bước đi ngẫu nhiên (random walk) và khí hậu học (climatology, tỷ lệ tăng lịch sử). Kỹ năng = 1 - Brier mô hình / Brier mức so sánh; lớn hơn 0 nghĩa là vượt mức so sánh.

## Hiệu chỉnh (calibration)
Xác suất được kiểm tra bằng điểm Brier trên các mốc không chồng lấn, báo cáo số mốc độc lập (n_eff). Không dùng dữ liệu tương lai; số liệu được lấy theo phiên bản và độ trễ công bố thực tế.

## Nhãn độ tin cậy
- Cao / Trung bình: mô hình vượt cả hai mức so sánh ngoài mẫu.
- Thấp: mô hình chưa vượt mức so sánh. Nhãn này luôn được áp dụng trong trường hợp đó.

## Tầm thời gian
Ngắn hạn (1-3 tháng) công bố xác suất tăng P(tăng). Trung hạn (6-12 tháng) công bố khoảng lợi suất (p10, p50, p90), không công bố một xác suất duy nhất.

## Giới hạn
- Mẫu nhỏ, n_eff thấp: xác suất có thể lệch nhiều.
- Số liệu có thể bị điều chỉnh và công bố chậm.
- Dữ liệu giấy phép nội bộ chỉ dùng trong mô hình, trang web chỉ hiển thị tín hiệu.
- Văn bản được tạo từ mẫu cố định theo số liệu của mô hình, không dùng mô hình ngôn ngữ.

Nguồn: một phần dữ liệu từ FRED (Federal Reserve Bank of St. Louis).
