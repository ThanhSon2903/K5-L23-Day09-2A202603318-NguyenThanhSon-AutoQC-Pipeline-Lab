# Báo cáo Day 09 — Nguyễn Thanh Sơn, 2A202603318
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
## 4.1. Chứng minh gate hoạt động
Em chạy pipeline với ngân sách review bằng 0 để kiểm tra trường hợp không có người duyệt:
`python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`
Kết quả thực tế:
- Tổng đầu vào: 224 ảnh, sau intake còn 202 ảnh, loại 22 ảnh.
- QC vòng 1: phát hiện 36 lỗi bắt buộc và 153 cảnh báo.
- Sửa tự động: thực hiện 35 thay đổi.
- QC vòng 2: còn 6 lỗi bắt buộc, hàng đợi review có 125 ảnh.
- Human review: ngân sách 0 ảnh, không có ảnh nào được người duyệt xử lý.
- Kết luận: REWORK vì còn 6 lỗi ERROR chưa được xử lý.
- Exit code: 20.
- Export: Không xuất dataset vào work/exp_nb.

Thử nghiệm chứng minh gate hoạt động đúng: khi không có lượt review và vẫn còn lỗi bắt buộc, pipeline không cho phép phát hành dataset mà yêu cầu quay lại bước review để xử lý.
## 4.2. Những điểm mù của AutoQC 
1. Box lỏng nhẹ (POSSIBLE_LOOSE_BOX)
- Trong 02_error_list_v1.csv có 28 dòng POSSIBLE_LOOSE_BOX. Một bounding box có thể vẫn chứa đúng đối tượng nhưng dư một phần nền xung quanh. Hệ thống có thể phát hiện các trường hợp bất thường rõ ràng, nhưng khó đánh giá chính xác box có quá rộng so với đối tượng hay không. Vì vậy, cần người kiểm tra trực tiếp trên ảnh.
2. Bỏ sót đối tượng (POSSIBLE_MISSING)
- Có 53 dòng POSSIBLE_MISSING trong báo cáo v1. Những đối tượng nhỏ, bị che khuất hoặc khó nhận diện có thể không được model phát hiện. Hệ thống có thể đưa ra cảnh báo nhưng vẫn cần người xem lại ảnh để xác định có thực sự thiếu annotation hay không.
3. Perceptual hash có thể nhầm ảnh khác nội dung
- Khi thử duplicates.phash_dist = 16, tôi kiểm tra bằng mắt và phát hiện hai cặp img_0011–img_0008 và img_0177–img_0113 bị đánh dấu là ảnh gần trùng dù nội dung cảnh khác nhau. Điều này cho thấy perceptual hash chỉ đo độ tương đồng về hình ảnh, không hiểu ngữ nghĩa của đối tượng và bối cảnh. Vì vậy, em chọn ngưỡng 14 để hạn chế false positive, chấp nhận bỏ sót một số ảnh tương tự.

## 5. Train: raw vs clean (tùy chọn)

**Chưa chạy tại thời điểm hoàn thiện báo cáo.**

Lý do: Tôi ưu tiên hoàn thành và kiểm tra pipeline AutoQC, calibration các ngưỡng và quy trình review nhãn trước. Phần huấn luyện so sánh raw và clean cần thêm thời gian chuẩn bị dữ liệu, cấu hình môi trường và chạy nhiều seed để kết quả có độ tin cậy.

Tôi dự kiến thực hiện phần này sau khi hoàn thành các bước kiểm tra cốt lõi. Hiện tại chưa có kết quả thực nghiệm nên chưa đưa ra kết luận về sự khác biệt chất lượng giữa hai biến thể.

## 6. Quyết định và ghi chú AI
## 6.1. Quyết định cuối 
- HOLD – Dataset chưa đủ điều kiện Release vì còn 38/202 ảnh có cảnh báo sau review, tương đương 18.81%, vượt ngưỡng Hold 10%.
- Để chuyển sang Release, cần tiếp tục review các ảnh còn cảnh báo, sửa hoặc xác minh annotation, chạy lại pipeline và đảm bảo không còn lỗi ERROR, tỷ lệ ảnh còn cảnh báo dưới ngưỡng cho phép.
## 6.2. Ghi chú sử dụng AI
- Prompt chính: Hướng dẫn xây dựng và kiểm tra các bước AutoQC, calibration hai ngưỡng và xử lý lỗi annotation.
- Kiểm code AI: Đọc lại code, chạy pytest, chạy pipeline và đối chiếu kết quả với các file báo cáo.
- Một lần AI sai: AI từng đề xuất phash_dist = 16, nhưng khi kiểm tra ảnh thực tế phát hiện hai cặp ảnh khác nội dung bị đánh dấu trùng. Tôi điều chỉnh xuống 14.
*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
