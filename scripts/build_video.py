#!/usr/bin/env python3
"""Build a short MP4 slideshow from generated figures."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figures-dir", default="figures")
    parser.add_argument("--output", default="outputs/mathlib-network-demo.mp4")
    return parser.parse_args()


def font(size: int):
    for candidate in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Light.ttc"]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def make_frame(title: str, figure: Path | None) -> Image.Image:
    frame = Image.new("RGB", (1280, 720), "#f8fafc")
    draw = ImageDraw.Draw(frame)
    draw.text((48, 34), title, fill="#0f172a", font=font(36))
    if figure and figure.exists():
        image = Image.open(figure).convert("RGB")
        image.thumbnail((1184, 570))
        x = (1280 - image.width) // 2
        frame.paste(image, (x, 118))
    return frame


def main() -> None:
    args = parse_args()
    figures_dir = Path(args.figures_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frames_dir = output.parent / "video_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    slides = [
        ("Mathlib dependency network overview", figures_dir / "network_overview.png"),
        ("Bridge modules by centrality", figures_dir / "centrality_top_modules.png"),
        ("Depth distribution", figures_dir / "depth_distribution.png"),
        ("Topic-community overlap", figures_dir / "topic_community_heatmap.png"),
    ]
    frame_index = 0
    for title, figure in slides:
        frame = make_frame(title, figure)
        for _ in range(45):
            frame.save(frames_dir / f"frame_{frame_index:04d}.png")
            frame_index += 1

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to build the demo video.")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            "15",
            "-i",
            str(frames_dir / "frame_%04d.png"),
            "-pix_fmt",
            "yuv420p",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"Built video: {output}")


if __name__ == "__main__":
    main()

