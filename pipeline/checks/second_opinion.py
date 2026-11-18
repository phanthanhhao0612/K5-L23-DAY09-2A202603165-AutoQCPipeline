"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    if preds is None:
        preds = {}

    so_cfg = cfg["second_opinion"]
    conf_thresh = so_cfg["conf"]
    min_area_px = so_cfg["min_area_px"]
    fp_conf = so_cfg["fp_conf"]
    iou_missing = so_cfg["iou_missing"]
    iou_match = so_cfg["iou_match"]
    iou_loose = so_cfg["iou_loose"]

    n_classes = len(ds.classes)
    issues = []

    for img_p in ds.image_files():
        stem = img_p.stem

        # Bỏ qua ảnh nếu không có trong preds hoặc không có file nhãn
        if stem not in preds:
            continue
        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue

        raw_preds = preds.get(stem, [])
        img_size = ds.image_size(stem)
        img_w, img_h = img_size if img_size else (0, 0)

        # Lọc các dòng nhãn hợp lệ (giữ số dòng gốc)
        valid_labels = []  # list of (line_no, cls, (cx, cy, w, h))
        for line_no, raw_line in raw_lines:
            try:
                cls, cx, cy, w, h = parse_yolo_line(raw_line)
            except ValueError:
                continue
            if 0 <= cls < n_classes and w > 0 and h > 0:
                valid_labels.append((line_no, cls, (cx, cy, w, h)))

        # 1. Lọc dự đoán P (conf >= conf_thresh VÀ area_px >= min_area_px)
        P = []
        for r in raw_preds:
            p_cls, p_conf, p_cx, p_cy, p_w, p_h = r
            area_px = (p_w * img_w) * (p_h * img_h)
            if p_conf >= conf_thresh and area_px >= min_area_px:
                P.append(r)

        # Kiểm tra từng dự đoán trong P
        for r in P:
            p_cls, p_conf, p_cx, p_cy, p_w, p_h = r
            p_box = (p_cx, p_cy, p_w, p_h)

            # Tìm các candidate nhãn có IoU >= iou_missing
            cands = []
            for line_no, l_cls, l_box in valid_labels:
                iou = iou_xywh(p_box, l_box)
                if iou >= iou_missing:
                    cands.append((line_no, l_cls, l_box, iou))

            if not cands:
                # Không có candidate nào -> POSSIBLE_MISSING
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_MISSING", stem,
                    f"model dự đoán {ds.classes[p_cls]} (conf={p_conf:.2f}) nhưng nhãn thiếu",
                    line=None, extra={"conf": float(p_conf)}
                ))
            else:
                same_class = [c for c in cands if c[1] == p_cls]
                if same_class:
                    best_same_iou = max(c[3] for c in same_class)
                    if best_same_iou < iou_loose:
                        issues.append(Issue(
                            "second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                            f"box nhãn lỏng/lệch so với model (IoU={best_same_iou:.2f} < {iou_loose})",
                            line=None, extra={"iou": round(float(best_same_iou), 4), "conf": float(p_conf)}
                        ))
                    # Nếu best_same_iou >= iou_loose thì không cờ gì
                else:
                    diff_class = [c for c in cands if c[1] != p_cls]
                    if diff_class:
                        best_diff_iou = max(c[3] for c in diff_class)
                        if best_diff_iou >= iou_match:
                            issues.append(Issue(
                                "second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                                f"model dự đoán lớp {ds.classes[p_cls]} (conf={p_conf:.2f}), nhãn gán lớp khác (IoU={best_diff_iou:.2f})",
                                line=None, extra={"conf": float(p_conf), "iou": round(float(best_diff_iou), 4)}
                            ))

        # 2. Kiểm tra POSSIBLE_FALSE_POS trên từng dòng nhãn hợp lệ
        # Lọc các dự đoán có conf >= fp_conf (không lọc diện tích)
        P_fp = [
            (r[0], r[1], (r[2], r[3], r[4], r[5]))
            for r in raw_preds
            if r[1] >= fp_conf
        ]

        for line_no, l_cls, l_box in valid_labels:
            has_matching_pred = any(iou_xywh(l_box, p_box) >= iou_missing for _, _, p_box in P_fp)
            if not has_matching_pred:
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                    f"box nhãn dòng {line_no} không khớp dự đoán nào của model",
                    line=line_no, extra={}
                ))

    return issues
