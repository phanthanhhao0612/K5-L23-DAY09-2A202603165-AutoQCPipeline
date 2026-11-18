"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |
"""
from collections import defaultdict
from pathlib import Path

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMG_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def fix(ds, issues, cfg):
    err_issues = [i for i in issues if i.severity == ERROR]
    fixes = []

    # 1. Xoá ảnh + nhãn bị lỗi đầu vào (DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE)
    removed_stems = set()
    for iss in err_issues:
        if iss.code.startswith("DUP_IMAGE_") or iss.code in REMOVE_IMG_CODES:
            stem = iss.image
            if stem not in removed_stems:
                removed_stems.add(stem)
                img_path = ds.image_path(stem)
                if img_path and img_path.exists():
                    img_path.unlink()
                lbl_path = ds.label_path(stem)
                if lbl_path.exists():
                    lbl_path.unlink()
                fixes.append({
                    "image": stem,
                    "line": "",
                    "action": "remove_image",
                    "before": img_path.name if img_path else stem,
                    "after": "(đã xoá)",
                })

    # 2. Đổi tên class trong data.yaml nếu có BAD_CLASS_NAME
    has_bad_class_name = any(iss.code == "BAD_CLASS_NAME" for iss in err_issues)
    if has_bad_class_name and ds.yaml_path.exists():
        try:
            content = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        except Exception:
            content = {}
        old_names = content.get("names", "")
        content["names"] = {i: name for i, name in enumerate(cfg["classes"])}
        ds.yaml_path.write_text(yaml.safe_dump(content, sort_keys=False, allow_unicode=True), encoding="utf-8")
        fixes.append({
            "image": "data.yaml",
            "line": "",
            "action": "rename_classes",
            "before": str(old_names),
            "after": str(cfg["classes"]),
        })

    # 3. Thiếu nhãn (MISSING_LABEL_FILE) -> chuyển người gán (needs_label)
    needs_label_seen = set()
    for iss in err_issues:
        if iss.code == "MISSING_LABEL_FILE" and iss.image not in removed_stems:
            if iss.image not in needs_label_seen:
                needs_label_seen.add(iss.image)
                fixes.append({
                    "image": iss.image,
                    "line": "",
                    "action": "needs_label",
                    "before": "(không có file)",
                    "after": "chuyển người gán",
                })

    # 4. Sửa lỗi trên từng dòng của file nhãn
    # Gom issues theo (stem, line)
    line_issues_by_stem = defaultdict(lambda: defaultdict(list))
    for iss in err_issues:
        if iss.image in removed_stems or iss.image in ("data.yaml", "<dataset>"):
            continue
        if iss.line is not None and (iss.code in DROP_CODES or iss.code == "BOX_OUT_OF_IMAGE"):
            line_issues_by_stem[iss.image][iss.line].append(iss.code)

    for stem, lines_map in line_issues_by_stem.items():
        lbl_path = ds.label_path(stem)
        if not lbl_path.exists():
            continue

        raw_lines = lbl_path.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines = []

        for line_idx, raw_line in enumerate(raw_lines):
            line_no = line_idx + 1
            codes = lines_map.get(line_no, [])

            if not codes:
                if raw_line.strip():
                    new_lines.append(raw_line)
                continue

            # Ưu tiên drop_line nếu có bất kỳ mã drop nào
            must_drop = any(c in DROP_CODES for c in codes)

            if must_drop:
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": raw_line,
                    "after": "",
                })
                continue

            # Nếu chỉ có BOX_OUT_OF_IMAGE -> clip_box
            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    cls, cx, cy, w, h = parse_yolo_line(raw_line)
                    x1 = cx - w / 2.0
                    x2 = cx + w / 2.0
                    y1 = cy - h / 2.0
                    y2 = cy + h / 2.0

                    nx1 = max(0.0, min(1.0, x1))
                    nx2 = max(0.0, min(1.0, x2))
                    ny1 = max(0.0, min(1.0, y1))
                    ny2 = max(0.0, min(1.0, y2))

                    nw = nx2 - nx1
                    nh = ny2 - ny1
                    ncx = (nx1 + nx2) / 2.0
                    ncy = (ny1 + ny2) / 2.0

                    if nw <= 0 or nh <= 0:
                        fixes.append({
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": raw_line,
                            "after": "",
                        })
                    else:
                        clipped_line = f"{cls} {ncx:.6g} {ncy:.6g} {nw:.6g} {nh:.6g}"
                        new_lines.append(clipped_line)
                        fixes.append({
                            "image": stem,
                            "line": line_no,
                            "action": "clip_box",
                            "before": raw_line,
                            "after": clipped_line,
                        })
                except ValueError:
                    # Nếu dòng không parse được thì drop_line
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": raw_line,
                        "after": "",
                    })

        lbl_path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

    return fixes
