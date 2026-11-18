 
"""BƯỚC 4 — Quality Gate: Release / Hold / Rework."""

from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    # Lấy cấu hình
    threshold = cfg["gate"]["warn_ratio_hold"]

    image_stems = set(image_stems)
    reviewed = set(reviewed)

    n_images = len(image_stems)

    # Chỉ giữ những issue thuộc ảnh thực tế trong dataset
    valid_issues = [
        issue for issue in issues
        if issue.image in image_stems
    ]

    error_issues = [
        issue for issue in valid_issues
        if issue.severity == ERROR
    ]

    n_errors = len(error_issues)

    warn_images = {
        issue.image
        for issue in valid_issues
        if issue.severity == WARN
        and issue.image not in reviewed
    }

    n_warn_images = len(warn_images)

    # 3. Tính tỷ lệ cảnh báo
    warn_ratio = (
        n_warn_images / n_images
        if n_images > 0
        else 0.0
    )

    warn_ratio = round(warn_ratio, 4)

    reasons = []

    if n_errors > 0:
        decision = "Rework"
        reasons.append(
            f"Còn {n_errors} lỗi ERROR chưa được xử lý, "
            f"pipeline phải Rework."
        )

    elif warn_ratio >= threshold:
        decision = "Hold"
        reasons.append(
            f"Có {n_warn_images}/{n_images} ảnh còn cảnh báo "
            f"(tỷ lệ {warn_ratio:.4f}), "
            f"đạt hoặc vượt ngưỡng Hold {threshold:.4f}."
        )

    else:
        decision = "Release"
        reasons.append(
            f"Không còn lỗi ERROR và tỷ lệ cảnh báo "
            f"{warn_ratio:.4f} thấp hơn ngưỡng Hold "
            f"{threshold:.4f}."
        )

    if reviewed:
        reasons.append(
            f"Đã review {len(reviewed & image_stems)} ảnh; "
            f"WARN của các ảnh này không còn được tính."
        )

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons
    }
