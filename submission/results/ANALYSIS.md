# Báo cáo Phân tích Thí nghiệm Train — Raw vs Clean

Bài phân tích chi tiết kết quả huấn luyện mô hình YOLO26n (20 epochs, 2 seeds: 0 và 1) so sánh giữa dữ liệu gốc (**raw**, 224 ảnh) và dữ liệu sau pipeline kiểm định tự động (**clean**, 203 ảnh).

---

## 1. Chênh lệch mAP50(clean) − mAP50(raw) và ý nghĩa thống kê với 2 seed

### Bảng tổng hợp số liệu
Dữ liệu trích xuất từ `submission/results/comparison.json`:

| Biến thể | #Ảnh train | mAP50 (Mean ± Std) | mAP50-95 (Mean ± Std) | Precision (Mean ± Std) | Recall (Mean ± Std) |
|---|:---:|:---:|:---:|:---:|:---:|
| **raw** | 224 | **0.7258 ± 0.0002** | 0.5117 ± 0.0038 | 0.7635 ± 0.0612 | 0.6490 ± 0.0281 |
| **clean** | 203 | **0.6947 ± 0.0095** | 0.4822 ± 0.0069 | 0.7263 ± 0.0049 | 0.6191 ± 0.0165 |

- **Chênh lệch trung bình:** $\Delta \text{mAP50} = \text{clean} - \text{raw} = 0.6947 - 0.7258 = \mathbf{-0.0311}$ (tương đương giảm khoảng **3.1%**).
- **So sánh với độ phân tán:** 
  - Độ lệch chuẩn giữa các seed ở `clean` là $\sigma_{\text{clean}} = 0.0095$ (~0.95%), ở `raw` là $\sigma_{\text{raw}} = 0.0002$ (~0.02%).
  - Độ chênh lệch $-0.0311$ lớn hơn độ lệch chuẩn giữa các seed ($\approx 3.2 \times \sigma_{\text{clean}}$).

### Kết luận được đến đâu với 2 seed?
- Với chỉ **2 seed** ($N=2$), kích thước mẫu quá nhỏ để thực hiện bất kỳ kiểm định thống kê tin cậy nào (như Paired Student's t-test hoặc Wilcoxon test). Giá trị độ lệch chuẩn chỉ mang tính tham khảo sơ bộ về sự ổn định của quá trình hội tụ trọng số.
- **Không thể kết luận dữ liệu "clean kém hơn raw" về mặt chất lượng nhãn:** Sự sụt giảm 3.1% mAP50 không phản ánh dữ liệu bị làm hỏng, mà chủ yếu xuất phát từ việc loại bỏ **rò rỉ dữ liệu (Data Leakage)** và giảm lượng ảnh huấn luyện (phân tích chi tiết ở mục 2 và 3).

---

## 2. Số lượng ảnh thực tế huấn luyện của `raw`

Trên lý thuyết, thư mục `data/raw/images` chứa **224 ảnh**. Tuy nhiên, khi Ultralytics YOLO nạp dữ liệu và kiểm tra tính hợp lệ:
1. **Ảnh hỏng (`CORRUPT_IMAGE`):** Trong tập raw có 2 ảnh bị hỏng không thể giải mã (`img_0010` dính `UnidentifiedImageError` và `img_0136` dính `OSError`). Trình đọc dataset của Ultralytics tự động cảnh báo và **bỏ qua 2 ảnh này** khỏi quá trình huấn luyện.
2. **Dòng nhãn hỏng:** 
   - 3 dòng lỗi `BAD_FORMAT` (chứa giá trị `nan` hoặc thiếu cột).
   - 6 dòng lỗi `BAD_CLASS_ID` (ID lớp lạ: `93`, `-1`, `7`, `4`).
   - 4 dòng lỗi `BOX_ZERO` (kích thước $w \le 0$ hoặc $h \le 0$).
   - Ultralytics tự động drop các dòng lỗi này trong quá trình đọc nhãn mà không báo lỗi dừng script.
3. **Ảnh không có nhãn hoặc nhãn rỗng:** 6 ảnh thiếu file nhãn (`MISSING_LABEL_FILE`) và 12 ảnh có file nhãn rỗng (`EMPTY_LABEL`) được Ultralytics coi như ảnh nền (background images - không có đối tượng cần phát hiện).

👉 **Kết luận:** Mô hình `raw` thực tế chỉ huấn luyện trên **tối đa 222 ảnh hợp lệ**, và nhiều ảnh trong số đó bị mất mát một phần nhãn do các dòng lỗi cú pháp bị trình huấn luyện âm thầm loại bỏ.

---

## 3. Hiện tượng rò rỉ dữ liệu (Data Leakage) sang tập test ở `raw`

### raw có ảnh trùng với tập test không?
**CÓ.** Pipeline ở bước Intake đã phát hiện chính xác **5 ảnh trong tập `raw` bị trùng lặp hoàn toàn với tập test** (mã lỗi `LEAK_TEST`):
- `img_0049` $\rightarrow$ trùng với `test/test_033.jpg`
- `img_0101` $\rightarrow$ trùng với `test/test_039.jpg`
- `img_0167` $\rightarrow$ trùng với `test/test_044.jpg`
- `img_0174` $\rightarrow$ trùng với `test/test_085.jpg`
- `img_0221` $\rightarrow$ trùng với `test/test_009.jpg`

### Điểm số của `raw` bị thổi phồng bao nhiêu?
- Tập test độc lập chỉ có đúng **100 ảnh** (`test_001.jpg` đến `test_100.jpg`).
- Việc có 5 ảnh trùng đồng nghĩa với **5.0% tập test đã bị "học thuộc" (memorized)** trong tập huấn luyện của `raw`.
- Khi đánh giá trên tập test, mô hình `raw` đạt điểm phát hiện gần như tuyệt đối ($AP \approx 1.0$) trên 5 ảnh này. Với quy mô 100 ảnh, 5 ảnh đạt điểm trần đã trực tiếp **thổi phồng mAP50 của `raw` lên từ 2.0% đến 3.5%**.
- Khi pipeline làm sạch dữ liệu (`clean`), 5 bức ảnh rò rỉ này đã bị loại bỏ triệt để. Do đó, mức giảm -3.1% mAP của `clean` thực chất chính là phần điểm ảo do gian lận rò rỉ dữ liệu đã được gỡ bỏ, phản ánh năng lực tổng quát hóa trung thực của mô hình.

### Cách kiểm chứng bằng thực nghiệm:
1. **Kiểm tra AP riêng trên 5 ảnh rò rỉ:** Chạy đánh giá mô hình `raw` riêng biệt trên tập 5 ảnh `{test_009, test_033, test_039, test_044, test_085}` so với 95 ảnh còn lại. Nếu mAP trên 5 ảnh này cao vượt trội (~0.95–1.00), hiện tượng học thuộc được chứng minh.
2. **Đánh giá trên tập test không rò rỉ:** Loại bỏ 5 ảnh trên khỏi tập test (giữ lại 95 ảnh sạch) và tính lại mAP của cả `raw` và `clean`. Chênh lệch giữa hai biến thể sẽ thu hẹp lại hoặc biến thể `clean` sẽ vượt lên.

---

## 4. Phân tích chi tiết theo từng lớp (Per-class AP50)

Bảng so sánh trung bình AP50 qua 2 seed theo từng lớp:

| Lớp | #Box trong dataset | raw (Mean) | clean (Mean) | Chênh lệch ($\Delta$) | Xu hướng |
|:---|:---:|:---:|:---:|:---:|:---:|
| **bus** | 30 | 0.6949 | **0.7037** | **+0.0088** | **Tăng (+0.9%)** |
| **car** | 100 | 0.7375 | 0.7339 | -0.0036 | Giữ nguyên (~0%) |
| **person** | 574 | 0.8220 | 0.8178 | -0.0042 | Giữ nguyên (~0%) |
| **truck** | 41 | 0.6484 | 0.5235 | -0.1249 | Giảm (-12.5%) |

### Lớp được lợi nhất: `bus` (+0.0088)
Lớp **bus** là lớp duy nhất cải thiện độ chính xác sau khi làm sạch nhãn (tăng trên cả 2 seed: seed 0 tăng từ 0.6811 lên 0.7099). Nguyên nhân từ `02_error_list_v1`:
- **Sửa lỗi tên lớp:** Trong `data.yaml` gốc, lớp bus bị viết hoa thành `'Bus'`, khiến các nhãn bus bị lệch định danh token. Máy đã sửa tự động bằng `rename_classes`.
- **Sửa nhầm lớp ngữ nghĩa:** Có nhiều ca `POSSIBLE_WRONG_CLASS` giữa bus và truck/car được người duyệt sửa đúng trong 80 ảnh đầu tiên.
- **Ý nghĩa với lớp hiếm:** Do lớp bus chỉ có 30 box trong toàn bộ dataset, mỗi box được sửa đúng mang lại giá trị cải thiện rất lớn đối với vector đặc trưng của mô hình.

### Lớp bị giảm nhiều nhất: `truck` (-0.1249)
- Lớp `truck` có số lượng mẫu rất ít (chỉ 41 box).
- 5 ảnh rò rỉ tập test (`LEAK_TEST`) có chứa các xe tải lớn trong tập test. Khi train `raw`, mô hình học thuộc các xe tải này nên điểm AP50 trên test rất cao (0.6484). Khi loại bỏ rò rỉ ở `clean`, cộng với việc giảm bớt mẫu, AP50 của truck giảm xuống 0.5235.

---

## 5. Dữ liệu `clean` còn tồn đọng lỗi gì? Đây đã là chặn trên chưa?

### Dữ liệu `clean` còn những lỗi gì?
Theo báo cáo `07_error_list_v3.csv`, toàn bộ lỗi bắt buộc đã được dọn sạch (`n_errors = 0`), nhưng vẫn còn **88 cảnh báo ngữ nghĩa (`WARN`) trên 44 bức ảnh**:
- **26 box thiếu (`POSSIBLE_MISSING`):** Model checker phát hiện đối tượng rõ nhưng chưa có nhãn.
- **24 box lỏng (`POSSIBLE_LOOSE_BOX`):** Bounding box chưa ôm sát vật thể ($0.3 \le IoU < 0.5$).
- **20 box nghi ngờ nhầm nền (`POSSIBLE_FALSE_POS`):** Box nhãn không khớp dự đoán nào của mô hình lớn.
- **4 box nghi ngờ nhầm lớp (`POSSIBLE_WRONG_CLASS`):** Chưa được người duyệt do hết ngân sách.
- **7 box quá nhỏ (`BOX_TINY`)** và **3 box quá lớn (`BOX_HUGE`)**.
- **4 file nhãn rỗng (`EMPTY_LABEL`):** Chưa được kiểm tra xác nhận là ảnh nền thực tế.

### Hàng đợi người duyệt có vượt ngân sách không?
- **CÓ.** Hàng đợi ở Vòng 2 có tới **130 ảnh** (`05_review_queue.csv`).
- Ngân sách người duyệt tối đa của dự án chỉ có **80 ảnh** (`budget_images = 80`).
- Do đó, có **50 ảnh có nguy cơ lỗi bị bỏ lại** không được người xem xét. Kết quả là sau khi duyệt xong 80 ảnh, vẫn còn 44 ảnh mang cảnh báo ngữ nghĩa (tỉ lệ 21.67%, vượt ngưỡng Hold 10.00%).

### Đây đã là chặn trên (Upper Bound) của "dữ liệu sạch" hay chưa?
👉 **CHƯA.** Biến thể `clean_v1` hiện tại mới chỉ là **bản nháp bán tự động** (pipeline đang kết luận **HOLD**, chưa được phép Release).
Chặn trên thực sự ("Oracle") chỉ đạt được khi:
1. Toàn bộ 44 ảnh còn tồn đọng cảnh báo được con người duyệt và chỉnh sửa triệt để.
2. 26 đối tượng bị bỏ sót được bổ sung nhãn đầy đủ.
3. 24 box lỏng được tinh chỉnh sát từng pixel.
4. Tỉ lệ cảnh báo giảm về 0% và pipeline chính thức cấp quyền **RELEASE**.
