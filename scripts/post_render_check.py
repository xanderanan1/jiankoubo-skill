#!/usr/bin/env python3
"""Post-render visual QA for render-talking-video outputs."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


cv2 = None
OPENCV_INSTALL_ATTEMPTED = False
OPENCV_INSTALL_ERROR = ""


def load_cv2(auto_install: bool = True) -> bool:
    global cv2, OPENCV_INSTALL_ATTEMPTED, OPENCV_INSTALL_ERROR
    try:
        cv2 = importlib.import_module("cv2")
        return True
    except Exception as first_error:
        if not auto_install:
            OPENCV_INSTALL_ERROR = repr(first_error)
            cv2 = None
            return False
    OPENCV_INSTALL_ATTEMPTED = True
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "opencv-python"],
            check=True,
            capture_output=True,
            text=True,
        )
        importlib.invalidate_caches()
        cv2 = importlib.import_module("cv2")
        return True
    except Exception as install_error:  # pragma: no cover - depends on host network/pip
        OPENCV_INSTALL_ERROR = repr(install_error)
        cv2 = None
        return False


@dataclass
class Box:
    kind: str
    label: str
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    def clipped(self, width: int, height: int) -> "Box":
        x = max(0, min(self.x, width))
        y = max(0, min(self.y, height))
        x2 = max(x, min(self.x2, width))
        y2 = max(y, min(self.y2, height))
        return Box(self.kind, self.label, x, y, x2 - x, y2 - y)

    def to_json(self) -> dict[str, Any]:
        return {"kind": self.kind, "label": self.label, "x": self.x, "y": self.y, "w": self.w, "h": self.h}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def scale_for(width: int, height: int) -> float:
    return clamp(min(width, height) / 1080, 0.85, 2.2)


def px(value: float, scale: float) -> int:
    return int(round(value * scale))


def ms_to_frame(ms: int, fps: int) -> int:
    return max(0, round((ms / 1000) * fps))


def rect_intersection(left: Box, right: Box) -> int:
    x1 = max(left.x, right.x)
    y1 = max(left.y, right.y)
    x2 = min(left.x2, right.x2)
    y2 = min(left.y2, right.y2)
    return max(0, x2 - x1) * max(0, y2 - y1)


def overlap_ratio(left: Box, right: Box) -> float:
    overlap = rect_intersection(left, right)
    if overlap <= 0:
        return 0.0
    smaller = max(1, min(left.w * left.h, right.w * right.h))
    return overlap / smaller


def active_at(item: dict[str, Any], sample_ms: int) -> bool:
    return int(item.get("start_ms", 0)) <= sample_ms <= int(item.get("end_ms", 0))


def text_len(item: dict[str, Any]) -> int:
    return len(str(item.get("text") or item.get("label") or ""))


def layout_box(
    item: dict[str, Any],
    width: int,
    height: int,
    scale: float,
    preferred_width: int,
    preferred_height: int,
) -> Box:
    is_vertical = height > width
    margin = px(48 if is_vertical else 68, scale)
    box_width = px(preferred_width, scale)
    box_height = px(preferred_height, scale)
    layout = str(item.get("layout") or item.get("lane") or "upper-right")

    if layout == "upper-left":
        x, y = margin, px(236 if is_vertical else 118, scale)
    elif layout == "middle-left":
        x, y = margin, px(430 if is_vertical else 218, scale)
    elif layout == "middle-right":
        x, y = width - margin - box_width, px(500 if is_vertical else 252, scale)
    elif layout == "lower-left":
        x, y = margin, height - px(570 if is_vertical else 245, scale) - box_height
    elif layout == "lower-right":
        x, y = width - margin - box_width, height - px(570 if is_vertical else 245, scale) - box_height
    elif layout == "center":
        x, y = round((width - box_width) / 2), round(height * 0.46 - box_height / 2)
    elif layout == "top-center":
        x, y = round((width - box_width) / 2), px(248 if is_vertical else 122, scale)
    elif layout == "lower-third":
        side = px(58 if is_vertical else 110, scale)
        x = side
        box_width = width - side * 2
        y = height - px(560 if is_vertical else 235, scale) - box_height
    else:
        x, y = width - margin - box_width, px(300 if is_vertical else 142, scale)

    return Box("component", str(item.get("text") or item.get("label") or item.get("component") or "component"), x, y, box_width, box_height)


def estimate_component_box(item: dict[str, Any], width: int, height: int, scale: float, kind: str = "component") -> Box:
    is_vertical = height > width
    component = str(item.get("component") or "")
    variant = str(item.get("variant") or "")
    label = str(item.get("text") or item.get("label") or component or kind)

    if component == "hook_title" or kind == "hook":
        box = layout_box(item, width, height, scale, 660 if is_vertical else 720, 165 if is_vertical else 125)
        box.kind = "hook"
        box.label = label
        return box
    if component == "metric_card":
        if variant == "giant_number":
            return layout_box(item, width, height, scale, 430 if is_vertical else 360, 150 if is_vertical else 112)
        if variant == "speedometer":
            return layout_box(item, width, height, scale, 350 if is_vertical else 300, 210 if is_vertical else 174)
        return layout_box(item, width, height, scale, 350 if is_vertical else 290, 185 if is_vertical else 150)
    if component == "spec_chip":
        if variant == "stacked_specs":
            return layout_box(item, width, height, scale, 310 if is_vertical else 260, 105 if is_vertical else 82)
        chars = max(4, text_len(item))
        return layout_box(item, width, height, scale, min(360, 128 + chars * 28) if is_vertical else min(300, 105 + chars * 20), 72 if is_vertical else 56)
    if component == "benefit_badge":
        return layout_box(item, width, height, scale, 360 if is_vertical else 300, 92 if is_vertical else 72)
    if component == "callout":
        return layout_box(item, width, height, scale, 390 if is_vertical else 320, 116 if is_vertical else 92)

    chars = max(4, text_len(item))
    preferred = min(460 if is_vertical else 380, 150 + chars * (24 if is_vertical else 18))
    return layout_box(item, width, height, scale, preferred, 95 if is_vertical else 75)


def estimate_subtitle_box(width: int, height: int, scale: float) -> Box:
    is_vertical = height > width
    left = px(42 if is_vertical else 72, scale)
    bottom = px(390 if is_vertical else 160, scale)
    box_height = px(112 if is_vertical else 82, scale)
    return Box("subtitle", "subtitle", left, height - bottom - box_height, width - left * 2, box_height)


def sample_points(manifest: dict[str, Any], max_samples: int) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    hook = ((manifest.get("packaging") or {}).get("hook") or {}) if isinstance(manifest.get("packaging"), dict) else {}
    if isinstance(hook, dict) and hook.get("enabled", True) and hook.get("text"):
        start = int(hook.get("start_ms", 0))
        end = int(hook.get("end_ms", start + 1200))
        points.append({"time_ms": round((start + end) / 2), "reason": "hook"})

    events = [event for event in manifest.get("visual_events", []) or [] if isinstance(event, dict)]
    for event in events:
        if str(event.get("render_mode") or "flower") != "flower":
            continue
        start = int(event.get("start_ms", 0))
        end = int(event.get("end_ms", start + 1000))
        points.append({"time_ms": min(end, start + 450), "reason": str(event.get("text") or "visual_event")})

    subtitles = [item for item in manifest.get("subtitles", []) or [] if isinstance(item, dict)]
    if subtitles:
        step = max(1, math.ceil(len(subtitles) / 3))
        for subtitle in subtitles[::step]:
            start = int(subtitle.get("start_ms", 0))
            end = int(subtitle.get("end_ms", start + 500))
            points.append({"time_ms": round((start + end) / 2), "reason": "subtitle"})

    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    for point in sorted(points, key=lambda item: item["time_ms"]):
        bucket = round(point["time_ms"] / 200)
        if bucket in seen:
            continue
        seen.add(bucket)
        unique.append(point)
        if len(unique) >= max_samples:
            break
    return unique


def frame_at(video_path: Path, time_ms: int) -> Any:
    if cv2 is None:
        return None
    capture = cv2.VideoCapture(str(video_path))
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0, time_ms))
    ok, frame = capture.read()
    capture.release()
    return frame if ok else None


def detect_faces(frame: Any) -> list[Box]:
    if cv2 is None or frame is None:
        return []
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    cascade = cv2.CascadeClassifier(cascade_path)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(40, 40))
    return [Box("face", "face", int(x), int(y), int(w), int(h)) for x, y, w, h in faces]


def parse_focus_boxes(values: list[str], width: int, height: int) -> list[Box]:
    boxes: list[Box] = []
    for value in values:
        label = "focus"
        coords = value
        if ":" in value:
            label, coords = value.split(":", 1)
            label = label.strip() or "focus"
        parts = [part.strip() for part in coords.split(",")]
        if len(parts) != 4:
            raise SystemExit(f"--focus-box must be label:x,y,w,h or x,y,w,h: {value}")
        numbers = [float(part) for part in parts]
        if all(0 <= number <= 1 for number in numbers):
            x, y, w, h = numbers
            box = Box("focus", label, round(x * width), round(y * height), round(w * width), round(h * height))
        else:
            x, y, w, h = numbers
            box = Box("focus", label, round(x), round(y), round(w), round(h))
        boxes.append(box.clipped(width, height))
    return boxes


def draw_debug(frame: Any, boxes: list[Box], faces: list[Box], focus_boxes: list[Box], path: Path) -> None:
    if cv2 is None or frame is None:
        return
    colors = {
        "hook": (0, 215, 255),
        "component": (80, 240, 170),
        "subtitle": (255, 255, 255),
        "face": (80, 80, 255),
        "focus": (255, 120, 0),
        "safe": (255, 180, 60),
    }
    for box in boxes + faces + focus_boxes:
        color = colors.get(box.kind, (255, 255, 0))
        cv2.rectangle(frame, (box.x, box.y), (box.x2, box.y2), color, 4)
        cv2.putText(frame, box.label[:18], (box.x, max(28, box.y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)


def make_contact_sheet(image_paths: list[Path], output: Path) -> None:
    if cv2 is None or not image_paths:
        return
    images = [cv2.imread(str(path)) for path in image_paths]
    images = [image for image in images if image is not None]
    if not images:
        return
    thumb_h = 720
    thumbs = []
    for image in images:
        h, w = image.shape[:2]
        thumb_w = round(w * thumb_h / h)
        thumbs.append(cv2.resize(image, (thumb_w, thumb_h)))
    cols = min(3, len(thumbs))
    rows = math.ceil(len(thumbs) / cols)
    cell_w = max(image.shape[1] for image in thumbs)
    sheet = cv2.UMat(rows * thumb_h, cols * cell_w, cv2.CV_8UC3).get()
    sheet[:] = 255
    for index, image in enumerate(thumbs):
        row = index // cols
        col = index % cols
        sheet[row * thumb_h : row * thumb_h + image.shape[0], col * cell_w : col * cell_w + image.shape[1]] = image
    cv2.imwrite(str(output), sheet)


def evaluate_sample(
    manifest: dict[str, Any],
    video_path: Path,
    point: dict[str, Any],
    frames_dir: Path,
    index: int,
    focus_boxes: list[Box],
    face_overlap_threshold: float,
    box_overlap_threshold: float,
) -> dict[str, Any]:
    output = manifest.get("output") or {}
    width = int(output.get("width") or 0)
    height = int(output.get("height") or 0)
    scale = scale_for(width, height)
    time_ms = int(point["time_ms"])

    boxes: list[Box] = []
    hook = ((manifest.get("packaging") or {}).get("hook") or {}) if isinstance(manifest.get("packaging"), dict) else {}
    if isinstance(hook, dict) and hook.get("enabled", True) and active_at(hook, time_ms):
        boxes.append(estimate_component_box(hook, width, height, scale, "hook"))
    for event in manifest.get("visual_events", []) or []:
        if not isinstance(event, dict) or str(event.get("render_mode") or "flower") != "flower":
            continue
        if active_at(event, time_ms):
            boxes.append(estimate_component_box(event, width, height, scale))
    subtitle_active = any(isinstance(item, dict) and active_at(item, time_ms) for item in manifest.get("subtitles", []) or [])
    subtitle_box = estimate_subtitle_box(width, height, scale) if subtitle_active else None
    if subtitle_box:
        boxes.append(subtitle_box)

    frame = frame_at(video_path, time_ms)
    faces = detect_faces(frame)
    issues: list[dict[str, Any]] = []

    for box in boxes:
        if box.x < 0 or box.y < 0 or box.x2 > width or box.y2 > height:
            issues.append({"severity": "fail", "type": "offscreen", "box": box.to_json()})

    visual_boxes = [box for box in boxes if box.kind in {"hook", "component"}]
    for left_index, left in enumerate(visual_boxes):
        for right in visual_boxes[left_index + 1 :]:
            ratio = overlap_ratio(left, right)
            if ratio > box_overlap_threshold:
                issues.append(
                    {
                        "severity": "fail",
                        "type": "component_overlap",
                        "ratio": round(ratio, 3),
                        "boxes": [left.to_json(), right.to_json()],
                    }
                )

    if subtitle_box:
        for box in visual_boxes:
            ratio = overlap_ratio(box, subtitle_box)
            if ratio > 0.02:
                issues.append(
                    {
                        "severity": "fail",
                        "type": "subtitle_overlap",
                        "ratio": round(ratio, 3),
                        "boxes": [box.to_json(), subtitle_box.to_json()],
                    }
                )
        safe_bottom = height - px(320 if height > width else 120, scale)
        if subtitle_box.y2 > safe_bottom:
            issues.append({"severity": "fail", "type": "subtitle_too_low", "box": subtitle_box.to_json()})

    lower_band_top = height - max(px(260, scale), round(height * 0.16))
    for box in visual_boxes:
        if box.y2 > lower_band_top:
            issues.append({"severity": "warn", "type": "component_in_platform_overlay_band", "box": box.to_json()})

    if cv2 is None:
        issues.append({"severity": "warn", "type": "face_detection_unavailable"})
    elif not faces:
        issues.append({"severity": "warn", "type": "no_face_detected", "note": "Face detector found no frontal faces in this sample."})
    else:
        for box in visual_boxes:
            for face in faces:
                ratio = overlap_ratio(box, face)
                if ratio > face_overlap_threshold:
                    issues.append(
                        {
                            "severity": "fail",
                            "type": "face_occlusion",
                            "ratio": round(ratio, 3),
                            "boxes": [box.to_json(), face.to_json()],
                        }
                    )

    for box in visual_boxes:
        for focus in focus_boxes:
            ratio = overlap_ratio(box, focus)
            if ratio > face_overlap_threshold:
                issues.append(
                    {
                        "severity": "fail",
                        "type": "focus_occlusion",
                        "ratio": round(ratio, 3),
                        "boxes": [box.to_json(), focus.to_json()],
                    }
                )

    debug_path = frames_dir / f"qa-{index:02d}-{time_ms}ms.png"
    draw_debug(frame, boxes, faces, focus_boxes, debug_path)
    return {
        "time_ms": time_ms,
        "reason": point.get("reason", ""),
        "debug_frame": str(debug_path) if debug_path.exists() else "",
        "boxes": [box.to_json() for box in boxes],
        "faces": [face.to_json() for face in faces],
        "focus_boxes": [box.to_json() for box in focus_boxes],
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check rendered video packaging layout and face occlusion.")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames-dir", type=Path)
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument(
        "--focus-box",
        action="append",
        default=[],
        help="Optional key visual region to protect, as label:x,y,w,h. Coordinates may be pixels or normalized 0..1.",
    )
    parser.add_argument("--max-samples", type=int, default=10)
    parser.add_argument("--face-overlap-threshold", type=float, default=0.08)
    parser.add_argument("--box-overlap-threshold", type=float, default=0.12)
    parser.add_argument(
        "--no-auto-install-opencv",
        action="store_true",
        help="Disable automatic opencv-python installation when cv2 is missing.",
    )
    args = parser.parse_args()

    load_cv2(auto_install=not args.no_auto_install_opencv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    output = manifest.get("output") or {}
    width = int(output.get("width") or 0)
    height = int(output.get("height") or 0)
    focus_boxes = parse_focus_boxes(args.focus_box, width, height)
    frames_dir = args.frames_dir or args.output.with_suffix("").parent / "qa-frames"
    points = sample_points(manifest, max(1, args.max_samples))
    samples = [
        evaluate_sample(
            manifest,
            args.video,
            point,
            frames_dir,
            index,
            focus_boxes,
            args.face_overlap_threshold,
            args.box_overlap_threshold,
        )
        for index, point in enumerate(points, start=1)
    ]

    issue_counts = {"fail": 0, "warn": 0}
    for sample in samples:
        for issue in sample["issues"]:
            severity = issue.get("severity")
            if severity in issue_counts:
                issue_counts[severity] += 1

    status = "fail" if issue_counts["fail"] else "warn" if issue_counts["warn"] else "pass"
    contact_sheet = args.contact_sheet or args.output.with_suffix(".contact-sheet.png")
    make_contact_sheet([Path(sample["debug_frame"]) for sample in samples if sample.get("debug_frame")], contact_sheet)
    report = {
        "status": status,
        "video": str(args.video),
        "manifest": str(args.manifest),
        "opencv_available": cv2 is not None,
        "opencv_auto_install_attempted": OPENCV_INSTALL_ATTEMPTED,
        "opencv_install_error": OPENCV_INSTALL_ERROR,
        "samples_checked": len(samples),
        "focus_boxes": [box.to_json() for box in focus_boxes],
        "issue_counts": issue_counts,
        "contact_sheet": str(contact_sheet) if contact_sheet.exists() else "",
        "samples": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(args.output), "contact_sheet": report["contact_sheet"]}, ensure_ascii=False))
    if status == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
