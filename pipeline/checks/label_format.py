"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    fmt_cfg = cfg["label_format"]
    overflow_tol = fmt_cfg["overflow_tol"]
    min_box_px = fmt_cfg["min_box_px"]
    max_box_frac = fmt_cfg["max_box_frac"]
    dup_box_iou = fmt_cfg["dup_box_iou"]
    n_classes = len(ds.classes)

    issues = []

    for lf in ds.label_files():
        stem = lf.stem
        lines = ds.read_label_lines(stem)
        if not lines:
            continue

        img_size = ds.image_size(stem)
        seen_boxes = []  # list of (cls, (cx, cy, w, h))

        for line_no, raw_line in lines:
            try:
                cls, cx, cy, w, h = parse_yolo_line(raw_line)
            except ValueError:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, f"dòng không đúng 5 cột số: '{raw_line}'", line=line_no))
                continue

            if not (0 <= cls < n_classes):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls} không nằm trong 0..{n_classes - 1}", line=line_no))
                continue

            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, f"kích thước w={w}, h={h} <= 0", line=line_no))
                continue

            # Kiểm tra tràn ảnh (BOX_OUT_OF_IMAGE)
            x1 = cx - w / 2.0
            x2 = cx + w / 2.0
            y1 = cy - h / 2.0
            y2 = cy + h / 2.0
            overflow = max(0.0, -x1, x2 - 1.0, -y1, y2 - 1.0)
            if overflow > overflow_tol:
                issues.append(Issue(
                    "label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                    f"box tràn ảnh (mức tràn {overflow:.4f} > tol {overflow_tol})",
                    line=line_no, extra={"overflow": overflow}
                ))

            # Kiểm tra trùng lặp box (DUP_BOX) với dòng TRƯỚC ĐÓ cùng lớp
            curr_box = (cx, cy, w, h)
            is_dup = any(prev_cls == cls and iou_xywh(curr_box, prev_box) > dup_box_iou for prev_cls, prev_box in seen_boxes)
            if is_dup:
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, f"trùng lặp box lớp {cls}", line=line_no))

            seen_boxes.append((cls, curr_box))

            # Cảnh báo: BOX_TINY
            if img_size is not None:
                short_side_px = min(w * img_size[0], h * img_size[1])
                if short_side_px < min_box_px:
                    issues.append(Issue(
                        "label_format", WARN, "BOX_TINY", stem,
                        f"cạnh ngắn {short_side_px:.1f}px < {min_box_px}px",
                        line=line_no
                    ))

            # Cảnh báo: BOX_HUGE
            if w * h > max_box_frac:
                issues.append(Issue(
                    "label_format", WARN, "BOX_HUGE", stem,
                    f"diện tích {w * h:.3f} > {max_box_frac}",
                    line=line_no
                ))

    return issues
