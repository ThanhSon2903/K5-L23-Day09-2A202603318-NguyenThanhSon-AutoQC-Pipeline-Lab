
"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.

Test: pytest tests/test_autofix.py -q

Các thay đổi được trả về để ghi nhận vào 03_fixes.csv.
"""

from collections import defaultdict
from pathlib import Path

import yaml

from ..common import ERROR, parse_yolo_line


def _get(issue, name, default=None):
    """Đọc thuộc tính từ Issue hoặc dict."""
    if isinstance(issue, dict):
        return issue.get(name, default)
    return getattr(issue, name, default)


def _issue_code(issue):
    return str(_get(issue, "code", "") or "")


def _issue_image(issue):
    return _get(issue, "image")


def _issue_line(issue):
    line = _get(issue, "line")
    return int(line) if line is not None else None


def _issue_extra(issue):
    extra = _get(issue, "extra", {})
    return extra if isinstance(extra, dict) else {}


def _classes(cfg):
    """Lấy danh sách class từ cấu hình."""
    return list(cfg.get("classes", []))


def _image_path(ds, stem):
    """Tìm đường dẫn ảnh theo stem."""
    for path in ds.image_files():
        if path.stem == stem:
            return Path(path)
    return None


def _label_path(ds, stem):
    """Tìm đường dẫn file nhãn theo stem."""
    for path in ds.label_files():
        if path.stem == stem:
            return Path(path)
    return None


def _record(image, line, action, before, after):
    return {
        "image": image,
        "line": line,
        "action": action,
        "before": before,
        "after": after,
    }


def _clip_yolo_line(raw_line, classes):
    """Cắt bounding box về trong phạm vi [0, 1]."""
    class_id, cx, cy, width, height = parse_yolo_line(raw_line)

    left = max(0.0, cx - width / 2)
    top = max(0.0, cy - height / 2)
    right = min(1.0, cx + width / 2)
    bottom = min(1.0, cy + height / 2)

    # Box nằm hoàn toàn ngoài ảnh hoặc không còn diện tích.
    if right <= left or bottom <= top:
        return None

    new_cx = (left + right) / 2
    new_cy = (top + bottom) / 2
    new_width = right - left
    new_height = bottom - top

    # Giữ nguyên class ID và định dạng số thập phân.
    return (
        f"{class_id} "
        f"{new_cx:.8f} {new_cy:.8f} "
        f"{new_width:.8f} {new_height:.8f}"
    )


def _remove_image_and_label(ds, stem):
    """Xóa ảnh và file nhãn tương ứng nếu tồn tại."""
    image_path = _image_path(ds, stem)
    label_path = _label_path(ds, stem)

    if image_path is not None and image_path.exists():
        image_path.unlink()

    if label_path is not None and label_path.exists():
        label_path.unlink()


def _rename_classes(ds, cfg):
    """Cập nhật names trong data.yaml theo cfg['classes']."""
    yaml_path = getattr(ds, "data_yaml", None)

    if yaml_path is None:
        yaml_path = getattr(ds, "yaml_path", None)

    if yaml_path is None:
        root = Path(getattr(ds, "root", "."))
        yaml_path = root / "data.yaml"

    yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        return False

    with yaml_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    data["names"] = _classes(cfg)

    with yaml_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(
            data,
            file,
            allow_unicode=True,
            sort_keys=False,
        )

    return True


def fix(ds, issues, cfg):
    """Sửa các lỗi ERROR có thể tự động xử lý an toàn.

    Returns:
        list[dict]: Các thay đổi gồm image, line, action, before, after.
    """
    fixes = []

    # Chỉ xử lý ERROR, bỏ qua toàn bộ WARN.
    errors = [
        issue for issue in issues
        if _get(issue, "severity") == ERROR
    ]

    # Những lỗi có thể xóa một dòng nhãn.
    drop_codes = {
        "BAD_FORMAT",
        "BAD_CLASS_ID",
        "BOX_ZERO",
        "DUP_BOX",
    }

    # Những lỗi có thể xóa cả ảnh và nhãn.
    remove_prefixes = (
        "DUP_IMAGE_",
    )

    remove_codes = {
        "LEAK_TEST",
        "CORRUPT_IMAGE",
        "BAD_SIZE",
    }

    # Gom lỗi theo ảnh và dòng gốc.
    drop_lines = defaultdict(dict)
    clip_lines = defaultdict(dict)
    remove_images = set()
    missing_labels = set()
    rename_class_issues = []

    for issue in errors:
        code = _issue_code(issue)
        stem = _issue_image(issue)
        line = _issue_line(issue)

        if code in drop_codes:
            if stem is not None and line is not None:
                drop_lines[stem][line] = issue

        elif code == "BOX_OUT_OF_IMAGE":
            if stem is not None and line is not None:
                clip_lines[stem][line] = issue

        elif code == "MISSING_LABEL_FILE":
            if stem is not None:
                missing_labels.add(stem)

        elif code == "BAD_CLASS_NAME":
            rename_class_issues.append(issue)

        elif code in remove_codes or code.startswith(remove_prefixes):
            if stem is not None:
                remove_images.add(stem)

    # 1. Xóa ảnh và nhãn trước.
    # Các issue dòng của ảnh bị xóa sẽ được bỏ qua.
    for stem in sorted(remove_images):
        image_path = _image_path(ds, stem)
        label_path = _label_path(ds, stem)

        existed = (
            (image_path is not None and image_path.exists())
            or (label_path is not None and label_path.exists())
        )

        if existed:
            _remove_image_and_label(ds, stem)
            fixes.append(
                _record(
                    stem,
                    None,
                    "remove_image",
                    "ảnh và nhãn hiện có",
                    "đã xóa ảnh và nhãn khỏi dataset",
                )
            )

    # 2. Xử lý các file nhãn.
    all_stems = set(drop_lines) | set(clip_lines)

    for stem in sorted(all_stems):
        if stem in remove_images:
            continue

        label_path = _label_path(ds, stem)

        if label_path is None or not label_path.exists():
            continue

        original_lines = label_path.read_text(
            encoding="utf-8"
        ).splitlines()

        new_lines = []
        changed = False

        for line_number, raw_line in enumerate(original_lines, start=1):
            # Dòng bị xóa có độ ưu tiên cao hơn clip.
            if line_number in drop_lines.get(stem, {}):
                fixes.append(
                    _record(
                        stem,
                        line_number,
                        "drop_line",
                        raw_line,
                        "",
                    )
                )
                changed = True
                continue

            if line_number in clip_lines.get(stem, {}):
                try:
                    clipped = _clip_yolo_line(
                        raw_line,
                        _classes(cfg),
                    )
                except (ValueError, TypeError):
                    # Không thể parse an toàn thì không tự sửa.
                    new_lines.append(raw_line)
                    continue

                if clipped is None:
                    fixes.append(
                        _record(
                            stem,
                            line_number,
                            "drop_line",
                            raw_line,
                            "",
                        )
                    )
                    changed = True
                    continue

                new_lines.append(clipped)

                if clipped != raw_line.strip():
                    fixes.append(
                        _record(
                            stem,
                            line_number,
                            "clip_box",
                            raw_line,
                            clipped,
                        )
                    )
                    changed = True

                continue

            new_lines.append(raw_line)

        # Chỉ ghi file khi có thay đổi.
        if changed:
            content = "\n".join(new_lines)
            if original_lines:
                content += "\n"

            label_path.write_text(content, encoding="utf-8")

    # 3. Ảnh chưa có nhãn: không tạo file rỗng.
    for stem in sorted(missing_labels):
        if stem in remove_images:
            continue

        label_path = _label_path(ds, stem)

        if label_path is None or not label_path.exists():
            fixes.append(
                _record(
                    stem,
                    None,
                    "needs_label",
                    "(không có file)",
                    "chuyển người gán",
                )
            )

    # 4. Sửa tên class trong data.yaml.
    if rename_class_issues:
        if _rename_classes(ds, cfg):
            fixes.append(
                _record(
                    "data.yaml",
                    None,
                    "rename_classes",
                    "names cũ",
                    _classes(cfg),
                )
            )

    return fixes
