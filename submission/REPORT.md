# Báo cáo Day 09 — Phan Thanh Hào, 2A202603165

## 1. Kết luận trước
Pipeline kết luận: **HOLD** (mã thoát: 10). Lô dữ liệu đầu vào gồm **224 ảnh thô** $\rightarrow$ loại 21 ảnh lỗi ở bước intake (hỏng, kích thước nhỏ, trùng lặp, rò rỉ tập test) $\rightarrow$ nhận **203 ảnh** sạch vào pipeline $\rightarrow$ xuất bản nháp **203 ảnh** tại `submission/export/clean_v1/`.
Lý do chính: Toàn bộ 36 lỗi bắt buộc (ERROR) đã được máy sửa tự động hoặc người duyệt xử lý (`n_errors = 0`), tuy nhiên sau khi người duyệt sử dụng hết ngân sách tối đa 80 ảnh, tỉ lệ ảnh còn cảnh báo ngữ nghĩa (`WARN`) chưa được duyệt là **21.67%** (44/203 ảnh), vượt quá ngưỡng cho phép của dự án (**10.00%**). Do đó dữ liệu chưa thể phát hành và được giữ lại để tiếp tục xem xét.

## 2. Lỗi và phân việc
Thống kê từ `02_error_list_v1` (tổng số lỗi phát hiện trước khi sửa: 224 lỗi trên 203 ảnh):

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| BAD_FORMAT | 3 dòng | Máy | Dòng lỗi cú pháp, thiếu cột số hoặc chứa NaN; máy xóa dòng an toàn (`drop_line`). |
| BAD_CLASS_ID | 6 dòng | Máy | ID lớp lạ ngoài khoảng 0..3 (93, -1, 7, 4); máy xóa dòng an toàn (`drop_line`). |
| BOX_ZERO | 4 dòng | Máy | Kích thước $w \le 0$ hoặc $h \le 0$, không có ý nghĩa hình học; máy xóa dòng (`drop_line`). |
| BOX_OUT_OF_IMAGE | 8 dòng | Máy | Box tràn ra ngoài mép ảnh quá ngưỡng dung sai; máy tự cắt tọa độ về $[0, 1]$ (`clip_box`). |
| DUP_BOX | 7 dòng | Máy | Trùng lặp hình học cùng lớp ($IoU > 0.9$); máy xóa box xuất hiện sau (`drop_line`). |
| BAD_CLASS_NAME | 2 lỗi | Máy | Tên lớp trong `data.yaml` viết sai quy chuẩn ('Person', 'Bus'); máy ghi lại đúng chuẩn dự án (`rename_classes`). |
| DUP_IMAGE_EXACT | 8 ảnh | Máy | Trùng từng byte với ảnh đã có (MD5 trùng); máy loại bỏ ảnh và nhãn trùng (`remove_image`). |
| DUP_IMAGE_NEAR | 3 ảnh | Máy | Trùng gần đúng do nén/resize ($pHash \le 8$); máy loại bỏ ảnh và nhãn (`remove_image`). |
| LEAK_TEST | 5 ảnh | Máy | Trùng với ảnh trong kho test/val; máy loại bỏ ngay để tránh rò rỉ dữ liệu (`remove_image`). |
| CORRUPT_IMAGE | 2 ảnh | Máy | File ảnh hỏng không load được; máy loại bỏ (`remove_image`). |
| BAD_SIZE | 3 ảnh | Máy | Độ phân giải quá nhỏ (cạnh ngắn $< 250$px); máy loại bỏ (`remove_image`). |
| MISSING_LABEL_FILE | 6 ảnh | Người | Ảnh chưa có file nhãn; máy không thể tự bịa nhãn nên ghi nhận `needs_label` và ưu tiên chuyển người gán. |
| POSSIBLE_MISSING | 68 box | Người | Model checker phát hiện vật thể rõ ($conf \ge 0.5$) nhưng nhãn thiếu; người kiểm tra để bổ sung nhãn. |
| POSSIBLE_LOOSE_BOX | 31 box | Người | Box nhãn vẽ lỏng hoặc lệch ($0.3 \le IoU < 0.5$); người chỉnh lại viền sát đối tượng. |
| POSSIBLE_WRONG_CLASS | 18 box | Người | Nhãn bị gán nhầm lớp hợp lệ (vd: nhầm giữa car và truck); người xem ảnh để xác nhận lớp đúng. |
| POSSIBLE_FALSE_POS | 25 box | Người | Box nhãn không khớp dự đoán nào của checker ($conf \ge 0.1$); người xem có phải gán nhầm nền. |
| EMPTY_LABEL | 12 ảnh | Người | File nhãn rỗng (ảnh nền); người kiểm tra lại xem có bỏ sót nhãn không. |
| BOX_TINY | 6 box | Người | Kích thước box quá nhỏ ($< 12$px); người đối chiếu guideline xem có cần gán hay không. |
| BOX_HUGE | 3 box | Người | Box chiếm $> 95\%$ diện tích ảnh; người kiểm tra xem có bị vẽ bao trùm toàn cảnh. |
| CLASS_RARE | 4 lỗi | Người | Cảnh báo cấp dataset: phân bố lớp quá ít mẫu, cần quản lý dự án xem xét bổ sung. |

Hàng đợi `05_review_queue.csv` xếp các ảnh lên đầu dựa theo tổng điểm trọng số ưu tiên: các ảnh chưa có nhãn (`NEEDS_LABEL`, trọng số 10) và các ảnh máy vừa can thiệp cắt/xóa dòng (`FIXED_DROP_LINE`, `FIXED_CLIP_BOX`) kết hợp với các lỗi ngữ nghĩa nghiêm trọng (`POSSIBLE_WRONG_CLASS` trọng số 3, `POSSIBLE_MISSING` trọng số 2) có độ tự tin cao được đưa lên đầu hàng đợi.
Với ngân sách 80 ảnh, người duyệt mô phỏng đã xử lý: 6/6 ảnh thiếu nhãn (`NEEDS_LABEL`), 18/18 ảnh nhầm lớp (`POSSIBLE_WRONG_CLASS`), 51 ảnh thiếu nhãn vật thể (`POSSIBLE_MISSING`), 11 ảnh nhãn rỗng (`EMPTY_LABEL`), 11 ảnh box lỏng (`POSSIBLE_LOOSE_BOX`), 12 ảnh nghi gán nhầm nền (`POSSIBLE_FALSE_POS`), và toàn bộ các ảnh từng bị máy can thiệp dòng.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 8 | DUP_IMAGE_NEAR: P: 1.00 $\rightarrow$ 1.00, R: 0.50 $\rightarrow$ 0.67 (F1: 0.67 $\rightarrow$ 0.80) | Ngưỡng 2 quá khắt khe, bỏ sót 50% ảnh trùng gần đúng (ảnh resize/nén nhẹ). Tăng lên 8 giúp tăng Recall lên 67% mà Precision vẫn đạt 1.00. Không chọn $\ge 16$ vì khoảng cách Hamming quá rộng sẽ coi các ảnh khác nhau là trùng lặp. |
| `second_opinion.conf` | 0.25 | 0.50 | POSSIBLE_MISSING: P: 0.50 $\rightarrow$ 0.57, R: 1.00 $\rightarrow$ 1.00 (F1: 0.67 $\rightarrow$ 0.73) | Ngưỡng 0.25 khiến model checker sinh nhiều dự đoán nhiễu (báo động giả), làm loãng hàng đợi duyệt. Tăng lên 0.50 giúp tăng Precision từ 50% lên 57% trong khi vẫn giữ Recall 100% cho các trường hợp thiếu nhãn, giảm tải hiệu quả cho người duyệt. |

**Một chỗ calibration có thể đánh lừa bạn:**
Tập calibration `data/calib/` chỉ có 39 ảnh với các lỗi được chèn nhân tạo cố ý. Nếu chỉ nhìn vào bảng sweep để tối ưu F1 tuyệt đối trên tập calib, bạn có thể chọn `phash_dist = 16` (F1 đạt 0.91 trên calib); tuy nhiên khi áp dụng vào tập dữ liệu thực tế (203 ảnh COCO), khoảng cách 16 sẽ khiến các bức ảnh đường phố khác nhau có tông màu và bố cục tương tự bị gộp nhầm thành ảnh trùng và bị xóa oan. Tương tự, nếu tăng `conf` lên 0.8 để tối ưu WRONG_CLASS (F1 0.91 trên calib) thì Recall của MISSING sẽ sụt giảm nghiêm trọng từ 100% xuống 75%, làm lọt nhiều lỗi thiếu nhãn trên thực tế.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
- **(a) Chứng minh gate chặn đúng:**
  Khi chạy thử nghiệm với cờ `--budget 0`:
  `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`
  Do không có ngân sách cho người duyệt, 6 ảnh thiếu nhãn (`NEEDS_LABEL`) không được ai gán nhãn, dẫn đến 6 lỗi bắt buộc `MISSING_LABEL_FILE` còn nguyên trong vòng QC 3 (`n_errors = 6`). Cửa chặn gate đã lập tức ra quyết định **REWORK**, tiến trình kết thúc với mã thoát **20**, và pipeline hoàn toàn **KHÔNG xuất** dữ liệu ra `work/exp_nb`.
- **(b) Hai điểm mù của pipeline:**
  1. *Box lỏng nhẹ hoặc lệch viền tinh vi:* Nếu người gán nhãn vẽ box hơi rộng hoặc lệch một chút nhưng $IoU$ với dự đoán của checker vẫn $\ge 0.5$ (ngưỡng `iou_loose`), pipeline coi như nhãn đã bao phủ đối tượng và hoàn toàn không đưa ra cảnh báo nào.
  2. *Lỗi nhầm lẫn mà cả người và model checker đều mắc phải:* Ví dụ một chiếc xe tải nhỏ (pickup/van) bị người gán nhãn thành `car` và mô hình YOLO26L cũng dự đoán là `car` với độ tự tin cao. Do có sự đồng thuận giữa nhãn và model, lỗi sai ngữ nghĩa này trở thành điểm mù hoàn toàn đối với pipeline tự động.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Thực nghiệm huấn luyện công bằng: mô hình khởi tạo `yolo26n.pt`, 20 epochs, batch 16, imgsz 640, chạy trên Google Colab T4 GPU với 2 seed (0 và 1), cùng tập validation (`data/gold_val`, 40 ảnh) và cùng tập test độc lập (`data/test`, 100 ảnh có nhãn người).

Bảng kết quả từ `submission/results/comparison.md`:

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 203 | 2 | 0.695 ± 0.010 | 0.482 ± 0.007 | 0.726 ± 0.005 | 0.619 ± 0.016 |

Chênh lệch mAP50 (clean − raw) = **-0.031**.

**So sánh chênh lệch với độ nhiễu và kết luận trung thực:**
Chênh lệch mAP50 giữa hai biến thể là -0.031 (-3.1%), lớn hơn độ lệch chuẩn giữa các seed (0.010 ở clean và 0.000 ở raw). Kết luận trung thực: **Không thể vội vàng khẳng định "clean kém hơn raw" hay "clean tốt hơn raw"**, vì sự chênh lệch này đến từ các yếu tố bản chất sau:
1. *Hiệu ứng rò rỉ dữ liệu (Data Leakage) ở tập raw:* Trong lô raw ban đầu có 5 ảnh bị rò rỉ từ tập test/val (`LEAK_TEST`). Khi huấn luyện trên `raw`, mô hình đã ghi nhớ các đặc trưng của những ảnh bị rò rỉ này, khiến điểm mAP50 trên tập test bị thổi phồng một cách không trung thực. Ở biến thể `clean`, pipeline đã loại bỏ triệt để 5 ảnh rò rỉ này nên điểm số phản ánh đúng năng lực tổng quát hóa thực tế của mô hình.
2. *Số lượng ảnh huấn luyện bị giảm:* Biến thể `clean` đã loại bỏ 21 ảnh lỗi (từ 224 xuống 203 ảnh, giảm ~9.4% dữ liệu). Trong điều kiện tập dữ liệu quá nhỏ (~200 ảnh) và chỉ train 20 epoch ngắn, việc mất đi gần 10% ảnh có thể làm giảm nhẹ khả năng học bao phủ đối tượng.
3. *Quy mô tập test quá nhỏ (100 ảnh):* Trên 100 ảnh, việc mô hình bỏ sót hoặc dự đoán lệch chỉ 2–3 bounding box đã có thể làm thay đổi mAP từ 2–3%.
4. *Biến thể clean vẫn đang ở trạng thái HOLD:* Do ngân sách người duyệt chỉ có 80 ảnh, vẫn còn 44 ảnh trong `clean_v1` tồn tại cảnh báo ngữ nghĩa chưa được xử lý triệt để.

*Việc tiếp theo:* Cần cấp thêm ngân sách để người duyệt hoàn tất 44 ảnh còn lại để đạt chuẩn Release chính thức, và mở rộng tập test lên $\ge 500$ ảnh để giảm thiểu phương sai đánh giá trước khi huấn luyện mô hình production.

## 6. Quyết định và ghi chú AI
- **(a) Quyết định cuối cùng:** **HOLD**.
  Để lô dữ liệu này đủ điều kiện chuyển thành **RELEASE**, dự án cần cấp thêm ngân sách duyệt người cho 44 bức ảnh còn cảnh báo trong `submission/reports/07_error_list_v3.csv`. Sau khi người duyệt hoàn tất kiểm tra 44 ảnh này, tỉ lệ cảnh báo sẽ giảm xuống dưới ngưỡng 10%, và cửa chặn sẽ tự động cho phép Release dữ liệu chính thức.
- **(b) Ghi chú sử dụng AI:**
  - *Prompt chính:* Yêu cầu viết các hàm kiểm tra định dạng dòng YOLO (`label_format`), bộ tự động sửa lỗi an toàn (`autofix`), cây quyết định cửa chặn (`gate`), và logic so khớp IoU với model checker (`second_opinion`).
  - *Cách kiểm tra code AI:* Kiểm thử bằng toàn bộ 79 ca test của `pytest` (bao gồm các ca biên đặc biệt như dòng NaN, box tràn biên âm, ảnh hỏng, dòng trống giữ nguyên số dòng), sau đó chạy đối chiếu với các sweep calibration và dữ liệu thực tế.
  - *Một lần AI sai:* Khi xử lý một dòng vừa bị tràn ảnh `BOX_OUT_OF_IMAGE` vừa bị trùng `DUP_BOX`, phiên bản code đầu tiên của AI vừa clip box vừa drop dòng gây xung đột bản ghi; sau đó đã được sửa lại để ưu tiên `drop_line` duy nhất theo đúng yêu cầu đề bài.
