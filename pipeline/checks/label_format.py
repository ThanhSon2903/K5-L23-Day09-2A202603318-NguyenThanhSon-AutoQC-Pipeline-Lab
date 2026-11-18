
"""CHECK 2 — Validate YOLO label format and bounding boxes."""

from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    issues = []
    settings = cfg["label_format"]

    overflow_tol = settings["overflow_tol"]
    dup_box_iou = settings["dup_box_iou"]
    min_box_px = settings["min_box_px"]
    max_box_frac = settings["max_box_frac"]

    # Duyệt từng file nhãn
    for label_file in ds.label_files():
        stem = label_file.stem
        lines = ds.read_label_lines(stem)

        if lines is None:
            continue

        # Lưu các box hợp lệ trước đó để kiểm tra trùng lặp
        previous_boxes = []

        # Duyệt từng dòng, line_number bắt đầu từ 1
        for line_number, text in lines:

            # 1. Kiểm tra định dạng YOLO
            try:
                class_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BAD_FORMAT",
                    image=stem,
                    line=line_number,
                    message=f"Định dạng YOLO không hợp lệ: {e}"
                ))
                continue

            # 2. Kiểm tra class ID
            if not 0 <= class_id < len(ds.classes):
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BAD_CLASS_ID",
                    image=stem,
                    line=line_number,
                    message=f"Class ID {class_id} không hợp lệ"
                ))
                continue

            # 3. Kiểm tra box rỗng
            if w <= 0 or h <= 0:
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BOX_ZERO",
                    image=stem,
                    line=line_number,
                    message=f"Bounding box có kích thước không hợp lệ: w={w}, h={h}"
                ))
                continue

            box = (cx, cy, w, h)

            # 4. Kiểm tra bounding box vượt khỏi ảnh
            x_min = cx - w / 2
            x_max = cx + w / 2
            y_min = cy - h / 2
            y_max = cy + h / 2

            overflow = max(
                0.0,
                -x_min,
                x_max - 1.0,
                -y_min,
                y_max - 1.0
            )

            if overflow > overflow_tol:
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BOX_OUT_OF_IMAGE",
                    image=stem,
                    line=line_number,
                    message=f"Bounding box vượt khỏi ảnh: overflow={overflow:.6f}",
                    extra={"overflow": overflow}
                ))

            # 5. Kiểm tra box trùng với dòng trước đó
            for prev_class, prev_box in previous_boxes:
                if prev_class == class_id:
                    iou = iou_xywh(box, prev_box)

                    if iou > dup_box_iou:
                        issues.append(Issue(
                            check="label_format",
                            severity=ERROR,
                            code="DUP_BOX",
                            image=stem,
                            line=line_number,
                            message=f"Box trùng với box trước đó, IoU={iou:.4f}"
                        ))
                        break

            previous_boxes.append((class_id, box))

            # Lấy kích thước ảnh (width, height)
            size = ds.image_size(stem)

            if size is not None:
                image_width, image_height = size

                # 6. Kiểm tra box quá nhỏ
                short_side = min(
                    w * image_width,
                    h * image_height
                )

                if short_side < min_box_px:
                    issues.append(Issue(
                        check="label_format",
                        severity=WARN,
                        code="BOX_TINY",
                        image=stem,
                        line=line_number,
                        message=f"Box quá nhỏ: cạnh ngắn={short_side:.2f}px"
                    ))

            # 7. Kiểm tra box quá lớn
            if w * h > max_box_frac:
                issues.append(Issue(
                    check="label_format",
                    severity=WARN,
                    code="BOX_HUGE",
                    image=stem,
                    line=line_number,
                    message=f"Box chiếm diện tích quá lớn: {w * h:.4f}"
                ))

    return issues
