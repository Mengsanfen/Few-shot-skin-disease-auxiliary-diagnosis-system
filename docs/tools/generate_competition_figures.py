from __future__ import annotations

import html
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "figures" / "export"
DRAWIO_DIR = ROOT / "figures" / "drawio"
PLANTUML_DIR = ROOT / "figures" / "plantuml"
PLANTUML_EXPORT_DIR = ROOT / "figures" / "plantuml_rendered"


PALETTE = {
    "ink": "#0F172A",
    "muted": "#64748B",
    "line": "#CBD5E1",
    "blue": "#2563EB",
    "blue_soft": "#DBEAFE",
    "teal": "#0F766E",
    "teal_soft": "#CCFBF1",
    "green": "#16A34A",
    "green_soft": "#DCFCE7",
    "orange": "#EA580C",
    "orange_soft": "#FFEDD5",
    "purple": "#7C3AED",
    "purple_soft": "#EDE9FE",
    "gray_soft": "#F8FAFC",
    "white": "#FFFFFF",
}


def ensure_dirs() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    DRAWIO_DIR.mkdir(parents=True, exist_ok=True)
    PLANTUML_DIR.mkdir(parents=True, exist_ok=True)
    PLANTUML_EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for item in candidates:
        try:
            return ImageFont.truetype(item, size)
        except OSError:
            continue
    return ImageFont.load_default()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, fnt: ImageFont.FreeTypeFont) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for char in paragraph:
            candidate = current + char
            bbox = draw.textbbox((0, 0), candidate, font=fnt)
            if bbox[2] - bbox[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines


def rounded_box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    fill: str,
    outline: str = "#CBD5E1",
    radius: int = 24,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    text: str,
    size: int = 28,
    color: str = "#0F172A",
    bold: bool = False,
    max_lines: int = 4,
) -> None:
    fnt = font(size, bold)
    x1, y1, x2, y2 = xy
    lines = wrap_text(draw, text, x2 - x1 - 28, fnt)[:max_lines]
    line_h = size + 10
    total_h = len(lines) * line_h
    y = y1 + ((y2 - y1) - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=fnt)
        tw = bbox[2] - bbox[0]
        draw.text((x1 + ((x2 - x1) - tw) // 2, y), line, fill=color, font=fnt)
        y += line_h


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = "#334155", width: int = 3) -> None:
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 12
    pts = [
        end,
        (int(end[0] - size * math.cos(angle - math.pi / 6)), int(end[1] - size * math.sin(angle - math.pi / 6))),
        (int(end[0] - size * math.cos(angle + math.pi / 6)), int(end[1] - size * math.sin(angle + math.pi / 6))),
    ]
    draw.polygon(pts, fill=color)


def make_canvas(title: str, subtitle: str = "", size: tuple[int, int] = (1600, 1000)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    w, h = size
    # Academic but not flat: subtle panels and accent band.
    draw.rectangle((0, 0, w, 18), fill=PALETTE["blue"])
    draw.rectangle((0, 18, w, 24), fill=PALETTE["teal"])
    draw.text((64, 48), title, fill=PALETTE["ink"], font=font(38, True))
    if subtitle:
        draw.text((66, 98), subtitle, fill=PALETTE["muted"], font=font(21))
    return img, draw


def save_png(img: Image.Image, name: str) -> None:
    img.save(EXPORT_DIR / f"{name}.png", quality=96)


def save_plantuml_export(img: Image.Image, name: str, title: str, boxes: list[dict], arrows: list[tuple[str, str]] | None = None) -> None:
    img.save(PLANTUML_EXPORT_DIR / f"{name}.png", quality=96)
    old_export = EXPORT_DIR
    globals()["EXPORT_DIR"] = PLANTUML_EXPORT_DIR
    try:
        simple_svg_from_png_layout(name, title, boxes, arrows)
    finally:
        globals()["EXPORT_DIR"] = old_export


def write_puml(name: str, content: str) -> None:
    (PLANTUML_DIR / f"{name}.puml").write_text(content.strip() + "\n", encoding="utf-8")


def export_existing_png_as_plantuml(name: str, title: str, boxes: list[dict], edges: list[tuple[str, str]] | None = None) -> None:
    src = EXPORT_DIR / f"{name}.png"
    if src.exists():
        img = Image.open(src).convert("RGB")
        save_plantuml_export(img, name, title, boxes, edges)


def simple_svg_from_png_layout(name: str, title: str, boxes: list[dict], arrows: list[tuple[str, str]] | None = None, size=(1600, 1000)) -> None:
    id_map = {box["id"]: box for box in boxes}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size[0]}" height="{size[1]}" viewBox="0 0 {size[0]} {size[1]}">',
        "<defs><marker id=\"arrow\" markerWidth=\"12\" markerHeight=\"12\" refX=\"10\" refY=\"6\" orient=\"auto\"><path d=\"M2,2 L10,6 L2,10 Z\" fill=\"#334155\"/></marker></defs>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<rect x="0" y="0" width="{size[0]}" height="18" fill="{PALETTE["blue"]}"/>',
        f'<rect x="0" y="18" width="{size[0]}" height="6" fill="{PALETTE["teal"]}"/>',
        f'<text x="64" y="78" font-family="Microsoft YaHei, Arial" font-size="38" font-weight="700" fill="{PALETTE["ink"]}">{html.escape(title)}</text>',
    ]
    if arrows:
        for start_id, end_id in arrows:
            a, b = id_map[start_id], id_map[end_id]
            x1, y1, x2, y2 = a["xy"]
            bx1, by1, bx2, by2 = b["xy"]
            sx, sy = x2, (y1 + y2) // 2
            ex, ey = bx1, (by1 + by2) // 2
            if bx1 < x1:
                sx, ex = x1, bx2
            if by1 > y2:
                sx, sy = (x1 + x2) // 2, y2
                ex, ey = (bx1 + bx2) // 2, by1
            parts.append(f'<line x1="{sx}" y1="{sy}" x2="{ex}" y2="{ey}" stroke="#334155" stroke-width="3" marker-end="url(#arrow)"/>')
    for box in boxes:
        x1, y1, x2, y2 = box["xy"]
        parts.append(
            f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="24" fill="{box.get("fill", PALETTE["gray_soft"])}" stroke="{box.get("outline", PALETTE["line"])}" stroke-width="2"/>'
        )
        raw_lines = [line for line in box["label"].splitlines() if line]
        line_count = max(len(raw_lines), 1)
        font_size = box.get("size", 24)
        y_start = ((y1 + y2) // 2) - int((line_count - 1) * font_size * 0.65)
        tspan = "".join(
            f'<tspan x="{(x1+x2)//2}" dy="{0 if idx == 0 else int(font_size * 1.25)}">{html.escape(line)}</tspan>'
            for idx, line in enumerate(raw_lines or [box["label"]])
        )
        parts.append(
            f'<text x="{(x1+x2)//2}" y="{y_start}" text-anchor="middle" font-family="Microsoft YaHei, Arial" font-size="{font_size}" font-weight="{700 if box.get("bold", True) else 400}" fill="{box.get("color", PALETTE["ink"])}">{tspan}</text>'
        )
    parts.append("</svg>")
    (EXPORT_DIR / f"{name}.svg").write_text("\n".join(parts), encoding="utf-8")


def write_drawio(name: str, title: str, boxes: list[dict], edges: list[tuple[str, str]] | None = None) -> None:
    cells = [
        '<mxCell id="0"/>',
        '<mxCell id="1" parent="0"/>',
    ]
    for box in boxes:
        x1, y1, x2, y2 = box["xy"]
        style = (
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={box.get('fill', PALETTE['gray_soft'])};"
            f"strokeColor={box.get('outline', PALETTE['line'])};fontColor={box.get('color', PALETTE['ink'])};"
            "fontFamily=Microsoft YaHei;fontSize=16;fontStyle=1;"
        )
        cells.append(
            f'<mxCell id="{box["id"]}" value="{html.escape(box["label"])}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" as="geometry"/></mxCell>'
        )
    for idx, (start, end) in enumerate(edges or [], 1):
        cells.append(
            f'<mxCell id="edge{idx}" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;'
            f'jettySize=auto;html=1;strokeColor=#334155;endArrow=block;endFill=1;" edge="1" parent="1" source="{start}" target="{end}">'
            '<mxGeometry relative="1" as="geometry"/></mxCell>'
        )
    xml = (
        '<mxfile host="app.diagrams.net" modified="2026-04-23T00:00:00.000Z" agent="Codex" version="24.0.0">'
        f'<diagram id="{name}" name="{html.escape(title)}"><mxGraphModel dx="1600" dy="1000" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="1000" math="0" shadow="0"><root>'
        + "".join(cells)
        + "</root></mxGraphModel></diagram></mxfile>"
    )
    (DRAWIO_DIR / f"{name}.drawio").write_text(xml, encoding="utf-8")


def diagram_architecture() -> None:
    name = "fig2-1-system-architecture"
    boxes = [
        {"id": "u", "label": "用户端\n问诊 / 上传 / 查看", "xy": (70, 240, 330, 390), "fill": PALETTE["blue_soft"]},
        {"id": "web", "label": "前端交互层\n页面展示与操作反馈", "xy": (470, 160, 760, 300), "fill": PALETTE["teal_soft"]},
        {"id": "django", "label": "应用服务层\n业务路由与会话管理", "xy": (470, 390, 760, 560), "fill": PALETTE["green_soft"]},
        {"id": "rag", "label": "证据增强问诊\n知识检索与图谱推理", "xy": (920, 140, 1240, 290), "fill": PALETTE["purple_soft"]},
        {"id": "sfept", "label": "图像智能识别\n特征理解与类别判断", "xy": (920, 355, 1240, 520), "fill": PALETTE["orange_soft"]},
        {"id": "db", "label": "数据知识层\n会话 / 知识 / 切片", "xy": (470, 680, 760, 840), "fill": "#EEF2FF"},
        {"id": "llm", "label": "大模型接口\n生成问诊回答", "xy": (1320, 180, 1530, 330), "fill": "#F0FDFA"},
        {"id": "model", "label": "模型资源\n权重 / 支持集", "xy": (1320, 395, 1530, 560), "fill": "#FFF7ED"},
    ]
    edges = [("u", "web"), ("web", "django"), ("django", "rag"), ("django", "sfept"), ("django", "db"), ("rag", "llm"), ("sfept", "model"), ("rag", "db")]
    img, draw = make_canvas("DermoAI 系统总体架构图", "多模态问诊、SFEPT 图像分类、知识增强与数据沉淀的一体化架构")
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        arrow(draw, (aa["xy"][2], (aa["xy"][1] + aa["xy"][3]) // 2), (bb["xy"][0], (bb["xy"][1] + bb["xy"][3]) // 2))
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"])
        draw_centered_text(draw, b["xy"], b["label"], 24, bold=True, max_lines=3)
    save_png(img, name)
    export_existing_png_as_plantuml(name, "DermoAI 系统总体架构图", boxes, edges)
    simple_svg_from_png_layout(name, "DermoAI 系统总体架构图", boxes, edges)
    write_drawio(name, "系统总体架构图", boxes, edges)


def diagram_modules() -> None:
    name = "fig2-2-functional-modules"
    boxes = [
        {"id": "core", "label": "DermoAI\n皮肤医学智能辅助诊断平台", "xy": (590, 390, 1010, 550), "fill": PALETTE["blue_soft"]},
        {"id": "m1", "label": "平台总览\n能力导航", "xy": (80, 200, 340, 330), "fill": "#EFF6FF"},
        {"id": "m2", "label": "智能问诊\n证据增强回答", "xy": (460, 150, 720, 280), "fill": "#F0FDFA"},
        {"id": "m3", "label": "皮肤图像分类\n少样本智能识别", "xy": (880, 150, 1160, 280), "fill": "#FFF7ED"},
        {"id": "m4", "label": "医学知识中枢\n知识维护 / 文档切片", "xy": (1260, 200, 1530, 340), "fill": "#F5F3FF"},
        {"id": "m5", "label": "数据大屏\n趋势 / 分布 / 风险", "xy": (480, 700, 750, 840), "fill": "#ECFDF5"},
        {"id": "m6", "label": "辅助报告\n解释 / 建议 / 风险提示", "xy": (870, 700, 1160, 840), "fill": "#FEF3C7"},
    ]
    edges = [("core", "m1"), ("core", "m2"), ("core", "m3"), ("core", "m4"), ("core", "m5"), ("core", "m6")]
    img, draw = make_canvas("DermoAI 核心功能模块图", "仅保留当前作品展示链路：问诊、图像分类、知识中枢与数据大屏")
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        arrow(draw, ((aa["xy"][0] + aa["xy"][2]) // 2, (aa["xy"][1] + aa["xy"][3]) // 2), ((bb["xy"][0] + bb["xy"][2]) // 2, (bb["xy"][1] + bb["xy"][3]) // 2))
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"])
        draw_centered_text(draw, b["xy"], b["label"], 25, bold=True)
    save_png(img, name)
    export_existing_png_as_plantuml(name, "DermoAI 核心功能模块图", boxes, edges)
    simple_svg_from_png_layout(name, "DermoAI 核心功能模块图", boxes, edges)


def diagram_rag_sequence() -> None:
    name = "fig3-4-rag-sequence"
    lanes = [
        ("用户", 80),
        ("问诊页面", 300),
        ("问诊服务", 520),
        ("证据图谱", 760),
        ("知识库/切片", 1030),
        ("大模型接口", 1280),
    ]
    img, draw = make_canvas("RAG 智能问诊时序图", "从症状输入到证据增强回答的完整调用链")
    top, bottom = 180, 870
    for label, x in lanes:
        rounded_box(draw, (x - 78, top, x + 78, top + 62), "#F8FAFC")
        draw_centered_text(draw, (x - 78, top, x + 78, top + 62), label, 20, bold=True)
        draw.line((x, top + 65, x, bottom), fill="#CBD5E1", width=2)
    steps = [
        (80, 300, 280, "输入症状描述"),
        (300, 520, 360, "发送问诊请求"),
        (520, 760, 440, "携带历史会话组织检索"),
        (760, 1030, 520, "检索结构化知识与文档切片"),
        (1030, 760, 600, "返回引用依据与候选证据"),
        (760, 1280, 680, "组织问诊上下文并请求大模型"),
        (1280, 760, 760, "流式返回生成内容"),
        (760, 520, 820, "返回知识片段与图谱路径"),
        (520, 300, 860, "保存消息并推送前端"),
    ]
    for x1, x2, y, label in steps:
        arrow(draw, (x1, y), (x2, y), PALETTE["blue"] if x2 > x1 else PALETTE["teal"], 3)
        draw.text((min(x1, x2) + 12, y - 30), label, fill=PALETTE["ink"], font=font(18, True))
    save_png(img, name)
    export_existing_png_as_plantuml(name, "RAG 智能问诊时序图", [], [])
    simple_svg_from_png_layout(name, "RAG 智能问诊时序图", [], [])


def diagram_sfept_flow() -> None:
    name = "fig3-2-sfept-inference-flow"
    boxes = [
        {"id": "upload", "label": "上传皮肤图像", "xy": (70, 430, 260, 540), "fill": PALETTE["blue_soft"]},
        {"id": "prep", "label": "图像预处理\n尺寸统一与标准化", "xy": (340, 430, 590, 540), "fill": "#F8FAFC"},
        {"id": "swin", "label": "Swin 特征提取\n层次视觉表征", "xy": (680, 410, 960, 560), "fill": PALETTE["teal_soft"]},
        {"id": "support", "label": "支持集原型\n少样本类别中心", "xy": (1030, 210, 1280, 340), "fill": PALETTE["purple_soft"]},
        {"id": "query", "label": "待测图像表达\n病灶视觉语义", "xy": (1030, 530, 1280, 660), "fill": PALETTE["green_soft"]},
        {"id": "bd", "label": "原型偏移校正\n分布对齐与增强", "xy": (1345, 360, 1565, 510), "fill": PALETTE["orange_soft"]},
        {"id": "cls", "label": "距离度量分类\n类别与置信度", "xy": (650, 735, 980, 865), "fill": "#FEF3C7"},
    ]
    edges = [("upload", "prep"), ("prep", "swin"), ("swin", "support"), ("swin", "query"), ("support", "bd"), ("query", "bd"), ("bd", "cls")]
    img, draw = make_canvas("基于 SFEPT 思想的皮肤图像分类推理流程图", "系统实际采用：Swin特征、支持集原型、Bias Diminishing与距离分类")
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        arrow(draw, (aa["xy"][2], (aa["xy"][1] + aa["xy"][3]) // 2), (bb["xy"][0], (bb["xy"][1] + bb["xy"][3]) // 2))
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"])
        draw_centered_text(draw, b["xy"], b["label"], 22, bold=True)
    # Formula strip
    rounded_box(draw, (70, 150, 590, 315), "#FFFFFF", "#BFDBFE")
    draw.text((100, 180), "类别原型：", fill=PALETTE["ink"], font=font(24, True))
    draw.text((100, 225), "c_n = (1/K) sum f(x_j^n)", fill=PALETTE["blue"], font=font(25, True))
    rounded_box(draw, (70, 730, 590, 875), "#FFFFFF", "#FED7AA")
    draw.text((100, 760), "查询校正：", fill=PALETTE["ink"], font=font(24, True))
    draw.text((100, 805), "F_q' = F_q + (mu_S - mu_Q)", fill=PALETTE["orange"], font=font(25, True))
    save_png(img, name)
    export_existing_png_as_plantuml(name, "基于 SFEPT 思想的皮肤图像分类推理流程图", boxes, edges)
    simple_svg_from_png_layout(name, "基于 SFEPT 思想的皮肤图像分类推理流程图", boxes, edges)


def diagram_er() -> None:
    name = "fig2-3-er-diagram"
    boxes = [
        {"id": "user", "label": "用户信息表\n账号与联系方式", "xy": (70, 190, 300, 320), "fill": PALETTE["blue_soft"]},
        {"id": "conv", "label": "问诊会话表\n会话主题与状态", "xy": (450, 170, 760, 330), "fill": PALETTE["teal_soft"]},
        {"id": "msg", "label": "问诊消息表\n回答内容与证据图谱", "xy": (920, 160, 1270, 340), "fill": PALETTE["green_soft"]},
        {"id": "know", "label": "医学知识表\n疾病、症状、检查、建议", "xy": (100, 610, 440, 790), "fill": PALETTE["purple_soft"]},
        {"id": "doc", "label": "知识文档表\n资料来源与入库状态", "xy": (610, 610, 880, 770), "fill": PALETTE["orange_soft"]},
        {"id": "chunk", "label": "文档切片表\n片段内容与来源位置", "xy": (1040, 610, 1370, 790), "fill": "#FEF3C7"},
    ]
    edges = [("user", "conv"), ("conv", "msg"), ("know", "msg"), ("doc", "chunk"), ("chunk", "msg")]
    img, draw = make_canvas("DermoAI 核心数据库 E-R 图", "围绕问诊会话、证据引用与知识切片的可追溯数据结构")
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        arrow(draw, (aa["xy"][2], (aa["xy"][1] + aa["xy"][3]) // 2), (bb["xy"][0], (bb["xy"][1] + bb["xy"][3]) // 2))
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"])
        draw_centered_text(draw, b["xy"], b["label"], 22, bold=True)
    save_png(img, name)
    export_existing_png_as_plantuml(name, "DermoAI 核心数据库 E-R 图", boxes, edges)
    simple_svg_from_png_layout(name, "DermoAI 核心数据库 E-R 图", boxes, edges)


def diagram_knowledge_flow() -> None:
    name = "fig3-5-knowledge-ingestion-flow"
    boxes = [
        {"id": "file", "label": "上传医学资料\nPDF或文本文件", "xy": (70, 420, 250, 540), "fill": PALETTE["blue_soft"]},
        {"id": "extract", "label": "文本抽取\n识别正文内容", "xy": (340, 400, 590, 560), "fill": "#F8FAFC"},
        {"id": "clean", "label": "文本规范化\n换行 / 空白 / 段落", "xy": (680, 400, 930, 560), "fill": PALETTE["teal_soft"]},
        {"id": "chunk", "label": "医学语义切片\n保留上下文连续性", "xy": (1020, 370, 1280, 590), "fill": PALETTE["orange_soft"]},
        {"id": "db", "label": "知识片段入库\n记录来源与位置", "xy": (1370, 400, 1570, 560), "fill": PALETTE["green_soft"]},
        {"id": "rag", "label": "参与证据检索\n增强问诊回答", "xy": (680, 720, 930, 850), "fill": PALETTE["purple_soft"]},
    ]
    edges = [("file", "extract"), ("extract", "clean"), ("clean", "chunk"), ("chunk", "db"), ("db", "rag")]
    img, draw = make_canvas("医学知识文档入库与切片流程图", "把静态医学资料转化为可检索、可引用、可参与问诊的知识资产")
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        arrow(draw, (aa["xy"][2], (aa["xy"][1] + aa["xy"][3]) // 2), (bb["xy"][0], (bb["xy"][1] + bb["xy"][3]) // 2))
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"])
        draw_centered_text(draw, b["xy"], b["label"], 22, bold=True)
    save_png(img, name)
    export_existing_png_as_plantuml(name, "医学知识文档入库与切片流程图", boxes, edges)
    simple_svg_from_png_layout(name, "医学知识文档入库与切片流程图", boxes, edges)
    write_drawio(name, "医学知识文档入库与切片流程图", boxes, edges)
    write_puml(
        name,
        """
@startuml
left to right direction
skinparam shadowing false
skinparam roundcorner 18
skinparam activity {
  BackgroundColor #F8FAFC
  BorderColor #CBD5E1
  FontName Microsoft YaHei
}
start
:上传 PDF/TXT;
:文本抽取\n识别正文内容;
:文本规范化\n换行 / 空白 / 段落;
:医学语义切片\n保留上下文连续性;
:知识片段入库\n记录来源与位置;
:参与 RAGGraph 检索\n问诊证据增强;
stop
@enduml
""",
    )


def diagram_sfept_core_framework() -> None:
    name = "fig3-1-sfept-core-framework"
    boxes = [
        {"id": "input", "label": "皮肤图像输入\n支持样本与待测图像", "xy": (70, 420, 300, 560), "fill": PALETTE["blue_soft"]},
        {"id": "swin", "label": "层次视觉编码\n纹理、颜色与边界", "xy": (390, 380, 640, 600), "fill": PALETTE["teal_soft"]},
        {"id": "proto", "label": "类别原型构建\n少样本代表中心", "xy": (730, 210, 980, 350), "fill": PALETTE["purple_soft"]},
        {"id": "query", "label": "待测特征表达\n病灶视觉语义", "xy": (730, 620, 980, 760), "fill": PALETTE["green_soft"]},
        {"id": "bd", "label": "原型偏移校正\n分布对齐与伪标注", "xy": (1080, 380, 1320, 600), "fill": PALETTE["orange_soft"]},
        {"id": "sae", "label": "语义增强模块\n潜在医学先验注入", "xy": (1390, 210, 1560, 350), "fill": "#EEF2FF"},
        {"id": "cls", "label": "距离度量分类\n类别、置信度与候选结果", "xy": (1390, 620, 1560, 760), "fill": "#FEF3C7"},
    ]
    edges = [("input", "swin"), ("swin", "proto"), ("swin", "query"), ("proto", "bd"), ("query", "bd"), ("bd", "sae"), ("bd", "cls"), ("sae", "cls")]
    img, draw = make_canvas("SFEPT 模块核心技术框架图", "少样本视觉识别、原型修正与语义增强协同完成皮肤病图像分类")
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        arrow(draw, (aa["xy"][2], (aa["xy"][1] + aa["xy"][3]) // 2), (bb["xy"][0], (bb["xy"][1] + bb["xy"][3]) // 2))
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"], b.get("outline", PALETTE["line"]))
        draw_centered_text(draw, b["xy"], b["label"], 23, bold=True)
    save_png(img, name)
    export_existing_png_as_plantuml(name, "SFEPT 模块核心技术框架图", boxes, edges)
    simple_svg_from_png_layout(name, "SFEPT 模块核心技术框架图", boxes, edges)
    write_drawio(name, "SFEPT 模块核心技术框架图", boxes, edges)
    write_puml(
        name,
        """
@startuml
left to right direction
skinparam shadowing false
skinparam roundcorner 16
skinparam rectangle {
  FontName Microsoft YaHei
}
rectangle "皮肤图像输入\n支持样本与待测图像" as input #DBEAFE
rectangle "层次视觉编码\n纹理、颜色与边界" as swin #CCFBF1
rectangle "类别原型构建\n少样本代表中心" as proto #EDE9FE
rectangle "待测特征表达\n病灶视觉语义" as query #DCFCE7
rectangle "原型偏移校正\n分布对齐与伪标注" as bias #FFEDD5
rectangle "语义增强模块\n潜在医学先验注入" as sae #EEF2FF
rectangle "距离度量分类\n类别、置信度与候选结果" as cls #FEF3C7
input --> swin
swin --> proto
swin --> query
proto --> bias
query --> bias
bias --> sae
bias --> cls
sae --> cls
@enduml
""",
    )


def diagram_use_case() -> None:
    name = "fig2-4-core-use-case"
    boxes = [
        {"id": "actor", "label": "用户 / 医护人员", "xy": (80, 420, 310, 540), "fill": PALETTE["blue_soft"]},
        {"id": "uc1", "label": "进入平台总览\n查看能力入口", "xy": (470, 180, 760, 315), "fill": "#EFF6FF"},
        {"id": "uc2", "label": "智能问诊\n症状输入与证据回答", "xy": (470, 355, 760, 500), "fill": PALETTE["teal_soft"]},
        {"id": "uc3", "label": "皮肤图像分类\n上传图片并生成报告", "xy": (470, 585, 760, 735), "fill": PALETTE["orange_soft"]},
        {"id": "uc4", "label": "知识中枢\n维护医学资料", "xy": (1030, 250, 1320, 395), "fill": PALETTE["purple_soft"]},
        {"id": "uc5", "label": "数据大屏\n查看运行统计", "xy": (1030, 540, 1320, 685), "fill": PALETTE["green_soft"]},
    ]
    edges = [("actor", "uc1"), ("actor", "uc2"), ("actor", "uc3"), ("uc2", "uc4"), ("uc3", "uc5"), ("uc4", "uc5")]
    img, draw = make_canvas("DermoAI 核心用例图", "从使用者视角描述当前作品已实现开放的核心能力")
    rounded_box(draw, (405, 145, 1410, 790), "#FFFFFF", "#D1D5DB", radius=32, width=3)
    draw.text((445, 155), "DermoAI 系统边界", fill=PALETTE["muted"], font=font(22, True))
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        arrow(draw, (aa["xy"][2], (aa["xy"][1] + aa["xy"][3]) // 2), (bb["xy"][0], (bb["xy"][1] + bb["xy"][3]) // 2))
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"])
        draw_centered_text(draw, b["xy"], b["label"], 23, bold=True)
    save_png(img, name)
    export_existing_png_as_plantuml(name, "DermoAI 核心用例图", boxes, edges)
    simple_svg_from_png_layout(name, "DermoAI 核心用例图", boxes, edges)
    (PLANTUML_DIR / f"{name}.puml").write_text(
        """@startuml
left to right direction
skinparam packageStyle rectangle
skinparam shadowing false
actor "用户 / 医护人员" as User
rectangle "DermoAI" {
  usecase "进入平台总览\\n查看能力入口" as UC1
  usecase "智能问诊\\n症状输入与证据回答" as UC2
  usecase "皮肤图像分类\\n上传图片并生成报告" as UC3
  usecase "知识中枢\\n维护医学资料" as UC4
  usecase "数据大屏\\n查看运行统计" as UC5
}
User --> UC1
User --> UC2
User --> UC3
UC2 ..> UC4 : 检索证据
UC3 ..> UC5 : 统计沉淀
UC4 ..> UC5 : 知识指标
@enduml
""",
        encoding="utf-8",
    )


def diagram_diagnosis_dataflow() -> None:
    name = "fig3-7-diagnosis-dataflow"
    boxes = [
        {"id": "input", "label": "用户输入\n症状文本 / 皮肤图像", "xy": (80, 390, 330, 540), "fill": PALETTE["blue_soft"]},
        {"id": "router", "label": "应用业务编排\n会话管理与文件接收", "xy": (470, 380, 760, 550), "fill": PALETTE["teal_soft"]},
        {"id": "rag", "label": "RAG证据增强\n结构化知识 + 文档切片", "xy": (900, 170, 1210, 330), "fill": PALETTE["purple_soft"]},
        {"id": "vision", "label": "图像智能识别\n类别、置信度与候选结果", "xy": (900, 610, 1210, 770), "fill": PALETTE["orange_soft"]},
        {"id": "report", "label": "辅助报告生成\n解释 / 建议 / 风险提示", "xy": (1325, 380, 1560, 550), "fill": PALETTE["green_soft"]},
        {"id": "store", "label": "结果沉淀\n消息 / 引用 / 统计", "xy": (655, 790, 950, 900), "fill": "#EEF2FF"},
    ]
    edges = [("input", "router"), ("router", "rag"), ("router", "vision"), ("rag", "report"), ("vision", "report"), ("report", "store"), ("router", "store")]
    img, draw = make_canvas("DermoAI 辅助诊断闭环数据流图", "把输入、检索、推理、报告和数据沉淀串成可解释闭环")
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        start = (aa["xy"][2], (aa["xy"][1] + aa["xy"][3]) // 2)
        end = (bb["xy"][0], (bb["xy"][1] + bb["xy"][3]) // 2)
        if bb["xy"][1] > aa["xy"][3]:
            start = ((aa["xy"][0] + aa["xy"][2]) // 2, aa["xy"][3])
            end = ((bb["xy"][0] + bb["xy"][2]) // 2, bb["xy"][1])
        arrow(draw, start, end)
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"])
        draw_centered_text(draw, b["xy"], b["label"], 22, bold=True)
    save_png(img, name)
    export_existing_png_as_plantuml(name, "DermoAI 辅助诊断闭环数据流图", boxes, edges)
    simple_svg_from_png_layout(name, "DermoAI 辅助诊断闭环数据流图", boxes, edges)
    write_drawio(name, "DermoAI 辅助诊断闭环数据流图", boxes, edges)
    write_puml(
        name,
        """
@startuml
left to right direction
skinparam shadowing false
skinparam roundcorner 18
skinparam rectangle {
  FontName Microsoft YaHei
}
rectangle "用户输入\n症状文本 / 皮肤图像" as input #DBEAFE
rectangle "应用业务编排\n会话管理与文件接收" as django #CCFBF1
rectangle "RAGGraph证据增强\n结构化知识 + 文档切片" as rag #EDE9FE
rectangle "图像智能识别\n类别、置信度与候选结果" as sfept #FFEDD5
rectangle "辅助报告生成\n解释 / 建议 / 风险提示" as report #DCFCE7
database "结果沉淀\n消息 / 引用 / 图谱 / 统计" as store #EEF2FF
input --> django
django --> rag
django --> sfept
rag --> report
sfept --> report
report --> store
django --> store
@enduml
""",
    )


def diagram_test_matrix() -> None:
    name = "fig5-4-test-validation-matrix"
    img, draw = make_canvas("DermoAI 测试验证矩阵图", "围绕功能、算法、接口、可用性和部署迁移建立验证闭环")
    columns = [80, 385, 690, 995, 1300]
    rows = [190, 385, 580, 775]
    cards = [
        ("功能链路", "首页导航\n问诊\n图像分类", PALETTE["blue_soft"]),
        ("算法推理", "Swin特征\n原型校正\n置信度输出", PALETTE["orange_soft"]),
        ("知识增强", "知识检索\n文档切片\n引用回传", PALETTE["purple_soft"]),
        ("数据沉淀", "会话消息\n图谱路径\n统计指标", "#EEF2FF"),
        ("异常兜底", "无API\n无模型\n空输入", "#FEF3C7"),
        ("部署迁移", "CPU/CUDA\n环境变量\n模型路径", PALETTE["green_soft"]),
        ("界面体验", "对比度\n响应式\n操作反馈", PALETTE["teal_soft"]),
        ("安全边界", "风险提示\n非替代诊断\n日志可追溯", "#FEE2E2"),
    ]
    idx = 0
    for y in rows:
        for x in columns:
            if idx >= len(cards):
                break
            title, body, fill = cards[idx]
            rounded_box(draw, (x, y, x + 230, y + 145), fill)
            draw.text((x + 24, y + 22), title, fill=PALETTE["ink"], font=font(23, True))
            for n, line in enumerate(body.splitlines()):
                draw.text((x + 24, y + 62 + n * 26), line, fill=PALETTE["muted"], font=font(17, True))
            idx += 1
    save_png(img, name)
    boxes = [
        {"id": f"t{i}", "label": f"{title}\n{body}", "xy": (columns[i % 5], rows[i // 5], columns[i % 5] + 230, rows[i // 5] + 145), "fill": fill}
        for i, (title, body, fill) in enumerate(cards)
    ]
    export_existing_png_as_plantuml(name, "DermoAI 测试验证矩阵图", boxes, [])
    simple_svg_from_png_layout(name, "DermoAI 测试验证矩阵图", boxes, [])
    write_drawio(name, "DermoAI 测试验证矩阵图", boxes, [])
    write_puml(
        name,
        """
@startuml
skinparam shadowing false
skinparam roundcorner 16
skinparam rectangle {
  FontName Microsoft YaHei
}
rectangle "测试验证矩阵" {
  rectangle "功能链路\n首页导航 / 问诊 / 图像分类" as t1 #DBEAFE
  rectangle "算法推理\nSwin特征 / 原型校正 / 置信度" as t2 #FFEDD5
  rectangle "知识增强\n知识检索 / 文档切片 / 引用回传" as t3 #EDE9FE
  rectangle "数据沉淀\n会话消息 / 图谱路径 / 统计指标" as t4 #EEF2FF
  rectangle "异常兜底\n无API / 无模型 / 空输入" as t5 #FEF3C7
  rectangle "部署迁移\n运行设备 / 环境配置 / 模型路径" as t6 #DCFCE7
  rectangle "界面体验\n对比度 / 响应式 / 操作反馈" as t7 #CCFBF1
  rectangle "安全边界\n风险提示 / 非替代诊断 / 日志追溯" as t8 #FEE2E2
}
t1 -[hidden]right- t2
t2 -[hidden]right- t3
t3 -[hidden]right- t4
t4 -[hidden]right- t5
t6 -[hidden]right- t7
t7 -[hidden]right- t8
@enduml
""",
    )


def diagram_deployment() -> None:
    name = "fig4-12-deployment"
    boxes = [
        {"id": "client", "label": "客户端浏览器\n上传图像 / 发起问诊", "xy": (80, 380, 350, 540), "fill": PALETTE["blue_soft"]},
        {"id": "server", "label": "应用服务\n页面路由与业务处理", "xy": (500, 330, 800, 590), "fill": PALETTE["teal_soft"]},
        {"id": "db", "label": "SQLite / MySQL\n会话与知识数据", "xy": (950, 180, 1230, 330), "fill": "#EEF2FF"},
        {"id": "fsl", "label": "FSL_skin模型目录\n权重 / 支持集", "xy": (950, 440, 1230, 600), "fill": PALETTE["orange_soft"]},
        {"id": "llm", "label": "大模型服务\n问诊生成 / 报告解释", "xy": (950, 700, 1230, 850), "fill": PALETTE["purple_soft"]},
        {"id": "env", "label": "环境配置\n接口密钥、模型路径与运行设备", "xy": (1320, 380, 1540, 540), "fill": PALETTE["green_soft"]},
    ]
    edges = [("client", "server"), ("server", "db"), ("server", "fsl"), ("server", "llm"), ("env", "server"), ("env", "fsl")]
    img, draw = make_canvas("DermoAI 系统部署结构图", "通过环境变量统一管理数据库、大模型接口、模型路径和推理设备")
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        start = (aa["xy"][2], (aa["xy"][1] + aa["xy"][3]) // 2)
        end = (bb["xy"][0], (bb["xy"][1] + bb["xy"][3]) // 2)
        if aa["xy"][0] > bb["xy"][0]:
            start = (aa["xy"][0], (aa["xy"][1] + aa["xy"][3]) // 2)
            end = (bb["xy"][2], (bb["xy"][1] + bb["xy"][3]) // 2)
        arrow(draw, start, end)
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"])
        draw_centered_text(draw, b["xy"], b["label"], 23, bold=True)
    save_png(img, name)
    export_existing_png_as_plantuml(name, "DermoAI 系统部署结构图", boxes, edges)
    simple_svg_from_png_layout(name, "DermoAI 系统部署结构图", boxes, edges)


def main() -> None:
    ensure_dirs()
    diagram_architecture()
    diagram_modules()
    diagram_use_case()
    diagram_rag_sequence()
    diagram_sfept_flow()
    diagram_er()
    diagram_knowledge_flow()
    diagram_sfept_core_framework()
    diagram_diagnosis_dataflow()
    diagram_test_matrix()
    diagram_deployment()
    print(f"Generated figures in {EXPORT_DIR}")
    print(f"Generated draw.io sources in {DRAWIO_DIR}")


if __name__ == "__main__":
    main()
def diagram_knowledge_flow() -> None:
    """Override the earlier version with a more robust PlantUML source."""
    name = "fig3-5-knowledge-ingestion-flow"
    boxes = [
        {"id": "file", "label": "上传医学资料\nPDF或文本文件", "xy": (70, 420, 250, 540), "fill": PALETTE["blue_soft"]},
        {"id": "extract", "label": "文本抽取\n识别正文内容", "xy": (340, 400, 590, 560), "fill": "#F8FAFC"},
        {"id": "clean", "label": "文本规范化\n换行 / 空白 / 段落", "xy": (680, 400, 930, 560), "fill": PALETTE["teal_soft"]},
        {"id": "chunk", "label": "医学语义切片\n保留上下文连续性", "xy": (1020, 370, 1280, 590), "fill": PALETTE["orange_soft"]},
        {"id": "db", "label": "知识片段入库\n记录来源与位置", "xy": (1370, 400, 1570, 560), "fill": PALETTE["green_soft"]},
        {"id": "rag", "label": "参与 RAGGraph 检索\n增强问诊证据", "xy": (680, 720, 930, 850), "fill": PALETTE["purple_soft"]},
    ]
    edges = [("file", "extract"), ("extract", "clean"), ("clean", "chunk"), ("chunk", "db"), ("db", "rag")]
    img, draw = make_canvas("医学知识文档入库与切片流程图", "把静态医学资料转化为可检索、可引用、可参与问诊的知识资产")
    for a, b in edges:
        aa, bb = next(x for x in boxes if x["id"] == a), next(x for x in boxes if x["id"] == b)
        arrow(draw, (aa["xy"][2], (aa["xy"][1] + aa["xy"][3]) // 2), (bb["xy"][0], (bb["xy"][1] + bb["xy"][3]) // 2))
    for b in boxes:
        rounded_box(draw, b["xy"], b["fill"])
        draw_centered_text(draw, b["xy"], b["label"], 22, bold=True)
    save_png(img, name)
    export_existing_png_as_plantuml(name, "医学知识文档入库与切片流程图", boxes, edges)
    simple_svg_from_png_layout(name, "医学知识文档入库与切片流程图", boxes, edges)
    write_drawio(name, "医学知识文档入库与切片流程图", boxes, edges)
    write_puml(
        name,
        """
@startuml
left to right direction
skinparam shadowing false
skinparam roundcorner 18
skinparam defaultFontName Microsoft YaHei
skinparam rectangle {
  BorderColor #CBD5E1
  FontColor #0F172A
}
rectangle "上传医学资料\nPDF 或文本文件" as file #DBEAFE
rectangle "文本抽取\n识别正文内容" as extract #F8FAFC
rectangle "文本规范化\n换行 / 空白 / 段落" as clean #CCFBF1
rectangle "医学语义切片\n保留上下文连续性" as chunk #FFEDD5
rectangle "知识片段入库\n记录来源与位置" as store #DCFCE7
rectangle "参与 RAGGraph 检索\n增强问诊证据" as rag #EDE9FE
file --> extract
extract --> clean
clean --> chunk
chunk --> store
store --> rag
@enduml
""",
    )
