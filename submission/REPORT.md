# Báo cáo Day 09 — Nguyễn Thanh Sơn, 2A202603318

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
Pipeline kết luận **Hold**, Ban đầu có 224 ảnh, sau bước tiếp nhận dữ liệu loại 22 ảnh do ảnh hỏng còn lại 202 ảnh. Dataset `clean_v1` được xuất với 202 ảnh ở trạng thái bản nháp, chưa được phát hành.
Lý do chính: 
- Kích thước không đạt
- Trùng lặp hoặc rò rỉ tập test
- Sau khi mô phỏng review 80 ảnh, vẫn còn 38/202 ảnh có cảnh báo, tương ứng tỷ lệ 0.1881 (18.81%), vượt ngưỡng HOLD 0.1000 (10%). 

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| BAD_CLASS_ID |6 |Máy |Kiểm tra ID lớp không hợp lệ theo cấu hình. |
| BAD_CLASS_NAME |2 |Máy |Đối chiếu tên lớp với danh sách lớp chuẩn |
| BAD_FORMAT |3 |Máy |Phát hiện định dạng annotation sai |
| BAD_SIZE |3 |Máy |Kiểm tra IDPhát hiện ảnh sai kích thước quy định |
| BOX_HUGE |3 |Người |Cần xem box có bao quá nhiều vùng không cần thiết hay không |
| BOX_OUT_OF_IMAGE |8 |Máy |Có thể kiểm tra và xử lý tọa độ box vượt biên ảnh|
| BOX_TINY |6 |Người |Cần xem box nhỏ có thực sự bao đúng đối tượng không |
| BOX_ZERO |4 |Máy |Box có chiều rộng hoặc chiều cao bằng 0|
| CLASS_RARE |4 |Người |Cần xem lại các lớp hiếm để tránh bỏ sót hoặc gán sai|
| CORRUPT_IMAGE |2 |Máy |Phát hiện ảnh không đọc được và loại khỏi dữ liệu hoặc chiều cao bằng 0|
| DUP_BOX |7 |Máy |Phát hiện các bounding box trùng lặp |
| DUP_IMAGE_EXACT |8 |Máy |Phát hiện ảnh trùng hoàn toàn|
| DUP_IMAGE_NEAR |4 |Người |Cần xem ảnh gần giống có thực sự là bản trùng hay không|
| EMPTY_LABEL |12 |Người |Cần xác minh ảnh không có annotation có thực sự không chứa đối tượng|
| LEAK_TEST |5 |Máy |Phát hiện ảnh có nguy cơ trùng hoặc rò rỉ giữa tập dữ liệu|
| MISSING_LABEL_FILE |6 |Người |Cần bổ sung và gán nhãn cho ảnh chưa có file annotation |
| POSSIBLE_FALSE_POS |29 |Người |Cần xác minh dự đoán có phải đối tượng giả hay không|
| POSSIBLE_LOOSE_BOX |28 |Người |Cần kiểm tra box có quá rộng so với đối tượng không|
| POSSIBLE_MISSING |53 |Người |Cần kiểm tra có đối tượng nào bị bỏ sót nhãn không|
| POSSIBLE_WRONG_CLASS |18 |Người |Cần xác minh đối tượng có bị gán sai lớp không|

Vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?
- Review queue ưu tiên ảnh có mức độ rủi ro cao trước, dựa trên priority và các mã cảnh báo đi kèm. Ảnh thiếu file nhãn (NEEDS_LABEL) hoặc có nhiều nghi vấn ngữ nghĩa thường được ưu tiên cao hơn ảnh chỉ có cảnh báo đơn lẻ. Ví dụ, img_0020 có priority 11.524 với các nghi vấn POSSIBLE_MISSING, POSSIBLE_WRONG_CLASS và FIXED_DROP_LINE, nên được đưa lên đầu queue. Các ảnh có NEEDS_LABEL cũng được ưu tiên vì cần bổ sung annotation.
- Kết quả review với budget 80: Với ngân sách review 80 ảnh, con người đã xem 80 ảnh theo thứ tự ưu tiên trong queue. Các mã POSSIBLE_* là nghi vấn do hệ thống phát hiện, không đồng nghĩa tất cả đều là lỗi đã được xác nhận.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 14 |1.00 / 0.50 → 1.00 / 0.67 (DUP_IMAGE_NEAR) |Precision giữ nguyên 1.00, Recall tăng từ 0.50 lên 0.67, F1 tăng từ 0.67 lên 0.80. Chọn 14 để phát hiện thêm ảnh trùng gần đúng nhưng tránh hai cặp false positive xuất hiện ở ngưỡng 16 khi kiểm tra bằng mắt. Đánh đổi là bỏ sót một số ảnh tương tự mà ngưỡng 16 có thể phát hiện. 
| `second_opinion.conf` | 0.25 | 0.6 |WRONG_CLASS: 0.56 / 0.83 → 0.62 / 0.83; MISSING: 0.50 / 1.00 → 0.57 / 1.00 |Tăng confidence giúp cảnh báo đáng tin hơn, giữ Recall của hai nhóm lỗi trên. Không chọn 0.8 vì Recall POSSIBLE_MISSING giảm còn 0.75, dù Precision WRONG_CLASS tăng lên 1.00. |


## 4. Cửa chặn và điều pipeline KHÔNG bắt được
TODO(học viên): (a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) (b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

TODO(học viên): chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.

## 6. Quyết định và ghi chú AI
TODO(học viên): (a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? (b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
