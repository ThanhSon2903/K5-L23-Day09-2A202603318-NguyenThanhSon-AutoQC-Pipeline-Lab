
"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).

Test: pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa.
Model checker chỉ đưa ra cảnh báo WARN để người review xác nhận.
"""

from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def _issue(code, stem, message, extra=None, line=None):
    """Tạo Issue cho second_opinion."""
    return Issue(
        "second_opinion",
        WARN,
        code,
        stem,
        message,
        line=line,
        extra=extra or {},
    )


def _prediction_iou(pred, label):
    """IoU giữa prediction và label.

    pred:  [class_id, conf, cx, cy, w, h]
    label: (class_id, cx, cy, w, h)
    """
    return iou_xywh(
        (pred[2], pred[3], pred[4], pred[5]),
        (label[1], label[2], label[3], label[4]),
    )


def run(ds, cfg, preds=None):
    """So sánh prediction của checker với nhãn dataset."""

    settings = cfg["second_opinion"]

    conf_threshold = settings["conf"]
    min_area_px = settings["min_area_px"]
    fp_conf = settings["fp_conf"]

    iou_missing = settings["iou_missing"]
    iou_match = settings["iou_match"]
    iou_loose = settings["iou_loose"]

    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    issues = []

    # Lấy danh sách file nhãn để bỏ qua ảnh không có label.
    label_stems = {path.stem for path in ds.label_files()}

    # Duyệt ảnh theo thứ tự dataset.
    for image_path in ds.image_files():
        stem = image_path.stem

        # Bỏ qua ảnh không có prediction hoặc file nhãn.
        if stem not in preds or stem not in label_stems:
            continue

        # Kích thước ảnh: (width, height).
        image_size = ds.image_size(stem)
        if not image_size:
            continue

        width, height = image_size

        # Lấy nhãn hợp lệ, không bao gồm các dòng hỏng.
        try:
            labels = ds.valid_boxes(stem)
        except (ValueError, TypeError):
            labels = []

        # Phân loại prediction:
        # valid_preds dùng cho MISSING / LOOSE / WRONG_CLASS.
        # fp_preds dùng cho FALSE_POS.
        valid_preds = []
        fp_preds = []

        for raw_pred in preds[stem]:
            try:
                class_id = int(raw_pred[0])
                confidence = float(raw_pred[1])

                cx = float(raw_pred[2])
                cy = float(raw_pred[3])
                box_w = float(raw_pred[4])
                box_h = float(raw_pred[5])

                pred = (
                    class_id,
                    confidence,
                    cx,
                    cy,
                    box_w,
                    box_h,
                )

                # FALSE_POS chỉ lọc theo fp_conf.
                if confidence >= fp_conf:
                    fp_preds.append(pred)

                # Các lỗi còn lại lọc cả confidence và diện tích.
                area_px = box_w * width * box_h * height

                if (
                    confidence >= conf_threshold
                    and area_px >= min_area_px
                ):
                    valid_preds.append(pred)

            except (ValueError, TypeError, IndexError):
                continue

        # --------------------------------------------------
        # PHẦN 1: MISSING / LOOSE_BOX / WRONG_CLASS
        # --------------------------------------------------

        for pred in valid_preds:
            pred_class = pred[0]
            confidence = pred[1]

            # Tìm tất cả nhãn có IoU >= iou_missing.
            candidates = []

            for label in labels:
                try:
                    iou = _prediction_iou(pred, label)
                except (ValueError, TypeError, IndexError):
                    continue

                if iou >= iou_missing:
                    candidates.append((label, iou))

            # (1) Không có candidate -> POSSIBLE_MISSING.
            if not candidates:
                issues.append(
                    _issue(
                        "POSSIBLE_MISSING",
                        stem,
                        "Model phát hiện vật thể nhưng nhãn không có box tương ứng.",
                        extra={"conf": confidence},
                    )
                )
                continue

            # Chia candidate thành cùng lớp và khác lớp.
            same_class = [
                (label, iou)
                for label, iou in candidates
                if label[0] == pred_class
            ]

            different_class = [
                (label, iou)
                for label, iou in candidates
                if label[0] != pred_class
            ]

            # (2) Có nhãn cùng lớp: chỉ xét IoU tốt nhất cùng lớp.
            if same_class:
                best_same_iou = max(
                    iou for _, iou in same_class
                )

                if best_same_iou < iou_loose:
                    issues.append(
                        _issue(
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            "Box nhãn cùng lớp có thể bị lỏng hoặc lệch.",
                            extra={
                                "conf": confidence,
                                "iou": best_same_iou,
                            },
                        )
                    )

                # Có nhãn đúng lớp thì không xét WRONG_CLASS.
                continue

            # (3) Không có nhãn cùng lớp:
            # chỉ cảnh báo WRONG_CLASS nếu IoU khác lớp >= iou_match.
            if different_class:
                best_different_iou = max(
                    iou for _, iou in different_class
                )

                if best_different_iou >= iou_match:
                    issues.append(
                        _issue(
                            "POSSIBLE_WRONG_CLASS",
                            stem,
                            "Model dự đoán lớp khác với nhãn hiện tại.",
                            extra={
                                "conf": confidence,
                                "iou": best_different_iou,
                            },
                        )
                    )

        # --------------------------------------------------
        # PHẦN 2: POSSIBLE_FALSE_POS
        # --------------------------------------------------

        # read_label_lines trả về:
        # [(line_number, raw_line), ...]
        # Giữ nguyên số dòng gốc, kể cả dòng trống và dòng hỏng.
        try:
            raw_lines = ds.read_label_lines(stem)
        except (ValueError, TypeError):
            raw_lines = []

        valid_line_boxes = []

        for line_number, raw_line in raw_lines:
            if not str(raw_line).strip():
                continue

            try:
                parsed = parse_yolo_line(raw_line)

                label = (
                    int(parsed[0]),
                    float(parsed[1]),
                    float(parsed[2]),
                    float(parsed[3]),
                    float(parsed[4]),
                )

                valid_line_boxes.append((line_number, label))

            except (ValueError, TypeError, IndexError):
                # Bỏ qua dòng nhãn hỏng.
                continue

        # Với mỗi dòng nhãn hợp lệ:
        # nếu IoU với MỌI prediction đạt fp_conf đều < iou_missing
        # thì cảnh báo FALSE_POS.
        for line_number, label in valid_line_boxes:
            best_iou = 0.0

            for pred in fp_preds:
                try:
                    iou = _prediction_iou(pred, label)
                except (ValueError, TypeError, IndexError):
                    continue

                best_iou = max(best_iou, iou)

            if best_iou < iou_missing:
                issues.append(
                    _issue(
                        "POSSIBLE_FALSE_POS",
                        stem,
                        "Box nhãn không khớp với prediction nào đủ confidence.",
                        extra={"iou": best_iou},
                        line=line_number,
                    )
                )

    return issues
