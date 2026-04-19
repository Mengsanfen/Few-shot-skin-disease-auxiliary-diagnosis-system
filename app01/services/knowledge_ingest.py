"""Knowledge document ingestion and chunking for RAG."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

from app01.models import KnowledgeChunk, KnowledgeDocument


CHUNK_SIZE = 520
CHUNK_OVERLAP = 90
SECTION_SEPARATORS = ("\n\n", "\n", "。", "！", "？", "；", ".", ";", " ")


@dataclass(frozen=True)
class ChunkPiece:
    index: int
    content: str
    start_offset: int
    end_offset: int
    page_label: str = ""

    @property
    def token_estimate(self) -> int:
        return max(1, math.ceil(len(self.content) / 2))


def ingest_uploaded_document(document: KnowledgeDocument) -> dict:
    text, page_map = extract_text_from_document(document.file.path, document.file_type)
    normalized = normalize_text(text)
    chunks = split_medical_text(normalized, page_map=page_map)

    document.total_chars = len(normalized)
    document.total_chunks = len(chunks)
    document.chunk_strategy = "medical_recursive_v1"
    document.status = "ready" if chunks else "empty"
    document.save(update_fields=["total_chars", "total_chunks", "chunk_strategy", "status", "updated_at"])

    document.chunks.all().delete()
    KnowledgeChunk.objects.bulk_create(
        [
            KnowledgeChunk(
                document=document,
                chunk_index=piece.index,
                page_label=piece.page_label,
                content=piece.content,
                token_estimate=piece.token_estimate,
                start_offset=piece.start_offset,
                end_offset=piece.end_offset,
            )
            for piece in chunks
        ]
    )

    return {
        "chars": document.total_chars,
        "chunks": document.total_chunks,
        "strategy": document.chunk_strategy,
    }


def extract_text_from_document(path: str, file_type: str) -> tuple[str, list[tuple[int, int, str]]]:
    suffix = (file_type or Path(path).suffix.lower().lstrip(".")).lower()
    if suffix == "txt":
        text = read_text_file(path)
        return text, [(0, len(text), "TXT")]
    if suffix == "pdf":
        return extract_text_from_pdf(path)
    raise ValueError("仅支持 pdf 或 txt 文件")


def read_text_file(path: str) -> str:
    encodings = ("utf-8", "utf-8-sig", "gb18030", "gbk")
    last_error = None
    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as handle:
                return handle.read()
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    raise ValueError(f"文本文件编码无法识别: {last_error}")


def extract_text_from_pdf(path: str) -> tuple[str, list[tuple[int, int, str]]]:
    reader = _build_pdf_reader(path)
    page_texts = []
    page_map = []
    cursor = 0
    for page_index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        text = normalize_text(text)
        if not text:
            continue
        if page_texts:
            page_texts.append("\n\n")
            cursor += 2
        start = cursor
        page_texts.append(text)
        cursor += len(text)
        page_map.append((start, cursor, f"第 {page_index} 页"))
    merged = "".join(page_texts)
    if not merged:
        raise ValueError("PDF 未提取到可用文本。若为扫描件，请先进行 OCR。")
    return merged, page_map


def _build_pdf_reader(path: str):
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError:
        try:
            from PyPDF2 import PdfReader
        except ModuleNotFoundError as exc:
            raise ValueError("当前环境缺少 PDF 解析依赖，请安装 pypdf 后再上传 PDF。") from exc
    return PdfReader(path)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_medical_text(text: str, page_map: list[tuple[int, int, str]] | None = None) -> list[ChunkPiece]:
    if not text:
        return []

    sections = split_into_sections(text)
    chunks: list[ChunkPiece] = []
    cursor = 0
    index = 1

    for section in sections:
        section = section.strip()
        if not section:
            continue
        for chunk_text in recursive_chunk(section):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue
            start = text.find(chunk_text, cursor)
            if start == -1:
                start = cursor
            end = start + len(chunk_text)
            cursor = max(start, end - CHUNK_OVERLAP)
            page_label = resolve_page_label(start, end, page_map or [])
            chunks.append(
                ChunkPiece(
                    index=index,
                    content=chunk_text,
                    start_offset=start,
                    end_offset=end,
                    page_label=page_label,
                )
            )
            index += 1

    return chunks


def split_into_sections(text: str) -> list[str]:
    sections = re.split(r"\n(?=(?:第[一二三四五六七八九十0-9]+[章节篇]|[0-9一二三四五六七八九十]+\s*[、.]|[A-Z][.)]))", text)
    if len(sections) == 1:
        sections = text.split("\n\n")
    return [section.strip() for section in sections if section.strip()]


def recursive_chunk(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    separator = next((item for item in SECTION_SEPARATORS if item and item in text), None)
    if not separator:
        return fixed_overlap_chunks(text, chunk_size)

    pieces = []
    current = ""
    for part in text.split(separator):
        candidate = f"{current}{separator if current else ''}{part}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            pieces.append(current)
        if len(part) > chunk_size:
            pieces.extend(fixed_overlap_chunks(part, chunk_size))
            current = ""
        else:
            current = part.strip()
    if current:
        pieces.append(current)
    return pieces


def fixed_overlap_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(text), step):
        piece = text[start:start + chunk_size].strip()
        if not piece:
            continue
        chunks.append(piece)
        if start + chunk_size >= len(text):
            break
    return chunks


def resolve_page_label(start: int, end: int, page_map: list[tuple[int, int, str]]) -> str:
    for page_start, page_end, label in page_map:
        if start < page_end and end >= page_start:
            return label
    return ""


def safe_document_title(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = re.sub(r"[_\-]+", " ", stem).strip()
    return cleaned[:160] or "未命名知识文档"
