#!/usr/bin/env python3
"""Build a Chinese PDF report using Pillow only."""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/processed")
    parser.add_argument("--figures-dir", default="figures")
    parser.add_argument("--output", default="report/mathlib-network-report.pdf")
    return parser.parse_args()


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], font, fill, width: int, line_gap: int = 8) -> int:
    x, y = xy
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            y += font.size + line_gap
            continue
        lines = []
        current = ""
        for char in paragraph:
            test = current + char
            if draw.textlength(test, font=font) <= width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
        for line in lines:
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + line_gap
    return y


def add_page(title: str, body: str, figures: list[Path] | None = None) -> Image.Image:
    page = Image.new("RGB", (1240, 1754), "#ffffff")
    draw = ImageDraw.Draw(page)
    title_font = load_font(42)
    body_font = load_font(25)
    small_font = load_font(19)
    draw.text((92, 78), title, font=title_font, fill="#0f172a")
    y = draw_wrapped(draw, body, (92, 155), body_font, "#1e293b", 1056, 11)
    if figures:
        y += 22
        for fig in figures:
            if not fig.exists():
                continue
            image = Image.open(fig).convert("RGB")
            image.thumbnail((1056, 520))
            page.paste(image, (92, min(y, 1180)))
            y += image.height + 22
    draw.text((92, 1708), "Mathlib Network Explorer - generated artifact", font=small_font, fill="#64748b")
    return page


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    figures_dir = Path(args.figures_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    metrics = json.loads((data_dir / "metrics.json").read_text(encoding="utf-8"))
    is_full_source = "Full Mathlib source" in str(metrics.get("data_source", ""))
    network_name = "全量 Mathlib module import network" if is_full_source else "Mathlib dependency network"
    input_description = (
        "输入数据的每一行表示 Mathlib 源码中的一个模块。管线扫描 Mathlib/**/*.lean，"
        "把文件路径规范化为模块名，并把 public import / import / import all 中的 Mathlib 依赖展开为有向边。"
        if is_full_source
        else
        "输入数据的每一行表示 Mathlib 中的一个符号或定理。管线先把 filename 规范化为模块名，"
        "再把 imports 展开为 source imports target 的有向边。"
    )
    top_bridge = metrics.get("top_betweenness", [])[:5]
    top_text = "\n".join(
        f"{idx + 1}. {item['id']} (betweenness={item['betweenness']:.4g}, topic={item['topic']})"
        for idx, item in enumerate(top_bridge)
    )
    if not top_text:
        top_text = "样例数据规模较小，暂无显著中心节点。"

    pages = [
        add_page(
            "Mathlib 数学依赖网络可视化报告",
            (
                "本项目参考 MathlibExplorer 的核心思想：用依赖关系决定横向层级，"
                "用 topic 聚合数学分支，并在交互中突出直接邻居、传递依赖和传递被依赖。"
                "为了保证长期可维护性，本项目没有依赖原桌面二进制，而是实现了可复现的 Python 数据管线和 Web-first 可视化。\n\n"
                f"当前网络：{network_name}。\n"
                f"当前数据源：{metrics.get('data_source')}。\n"
                f"模块数：{metrics.get('node_count')}；源码导入边数：{metrics.get('raw_edge_count', metrics.get('edge_count'))}；"
                f"结构骨架边数：{metrics.get('structural_edge_count', metrics.get('edge_count'))}；"
                f"社区数：{metrics.get('community_count')}；最大深度：{metrics.get('max_depth')}。"
            ),
            [figures_dir / "network_overview.png"],
        ),
        add_page(
            "数据处理与网络建模",
            (
                f"{input_description}节点聚合符号数量、类型分布、"
                "所属 library/topic、入度、出度、PageRank、中介中心度、社区编号和拓扑深度。\n\n"
                "布局参考 MathlibExplorer 并固化为左右依赖层次：rank 越深越靠右，同 namespace/topic 模块在相近的垂直 lane 中排列。"
                "坐标先由拓扑层级和 namespace lane 决定，再做弱力导向 refinement，仅用于局部避让和轻微聚合。"
                "默认边显示 transitive reduction 的结构骨架，完整源码 import 边保留为交互切换；节点大小默认映射 downstream influence。"
            ),
            [figures_dir / "depth_distribution.png"],
        ),
        add_page(
            "中心节点与社区发现",
            (
                "中介中心度用于寻找连接不同数学分支的桥接模块。社区发现使用无向化后的依赖图，"
                "再与人工 library/topic 标签对照，观察机器划分是否贴近代数、拓扑、分析、测度论等学科结构。\n\n"
                "Top bridge modules:\n"
                f"{top_text}"
            ),
            [figures_dir / "centrality_top_modules.png", figures_dir / "topic_community_heatmap.png"],
        ),
        add_page(
            "结论与局限",
            (
                "这个实现优先满足课程作业的可提交性，同时保留长期项目结构。静态页面可直接打开，"
                "TypeScript/Vite/Sigma.js 前端可以继续迭代为更大规模的 WebGL 体验。\n\n"
                "局限性：本版全量图是模块级 import 网络，不是定理级证明依赖网络；"
                "当前环境没有 lake，因此使用源码静态解析近似 lake exe graph 的模块关系；解析器会忽略文档块和注释中的示例 import。"
                "后续安装 Lean/Lake 后，可以加入 lake exe graph 作为高保真导出路径。"
            ),
        ),
    ]
    pages[0].save(output, save_all=True, append_images=pages[1:])
    print(f"Built report: {output}")


if __name__ == "__main__":
    main()
