"""Enterprise-style medical RAGGraph construction and scoring."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from django.db import IntegrityError, transaction

from app01.models import KnowledgeEntity, KnowledgeRelation

logger = logging.getLogger(__name__)


RELATION_META = {
    "HAS_SYMPTOM": {"label": "典型症状", "weight": 1.0, "edge_type": "clinical"},
    "LOCATED_AT": {"label": "发生部位", "weight": 0.82, "edge_type": "context"},
    "HAS_MORPHOLOGY": {"label": "皮损形态", "weight": 0.92, "edge_type": "clinical"},
    "TRIGGERED_BY": {"label": "相关诱因", "weight": 0.72, "edge_type": "context"},
    "NEEDS_CHECK": {"label": "建议检查", "weight": 0.86, "edge_type": "action"},
    "RISK_SIGNAL": {"label": "风险信号", "weight": 1.15, "edge_type": "risk"},
    "SUGGESTS_CARE": {"label": "护理建议", "weight": 0.7, "edge_type": "action"},
    "EVIDENCED_BY": {"label": "证据来源", "weight": 0.62, "edge_type": "evidence"},
}

RELATION_META["DIFFERENTIAL_WITH"] = {"label": "鉴别诊断", "weight": 0.68, "edge_type": "clinical"}

BODY_PART_TERMS = {
    "面部",
    "头皮",
    "手背",
    "手臂",
    "胸背部",
    "肘膝",
    "躯干",
    "四肢",
    "皮肤",
}

MORPHOLOGY_TERMS = {
    "红斑",
    "丘疹",
    "斑块",
    "鳞屑",
    "脱屑",
    "水疱",
    "脓疱",
    "结节",
    "白斑",
    "色素痣",
    "色素脱失斑",
}

RISK_TERMS = {
    "破溃出血",
    "快速变化",
    "快速扩大",
    "颜色不均",
    "边界不规则",
    "剧烈疼痛",
    "呼吸困难",
    "高热不退",
    "血氧下降",
}

TRIGGER_TERMS = {
    "过敏",
    "屏障受损",
    "刺激物接触",
    "皮脂分泌",
    "毛囊堵塞",
    "光照",
    "肤色差异",
    "拍摄设备",
}

SOURCE_TRUST = {
    "structured": 0.92,
    "document_chunk": 0.86,
    "graph_relation": 0.94,
    "database": 0.9,
    "builtin": 0.72,
}


@dataclass(frozen=True)
class RAGGraphNode:
    id: str
    label: str
    type: str
    score: float = 0.0
    description: str = ""
    source: str = ""


@dataclass(frozen=True)
class RAGGraphEdge:
    id: str
    source: str
    target: str
    relation: str
    relation_label: str
    score: float
    evidence: str = ""
    source_type: str = "structured"
    page_label: str = ""


@dataclass(frozen=True)
class RAGGraphRoute:
    disease: str
    score: float
    matched_entities: tuple[str, ...]
    evidence: str
    path: str


@dataclass
class RAGGraphResult:
    nodes: list[RAGGraphNode] = field(default_factory=list)
    edges: list[RAGGraphEdge] = field(default_factory=list)
    routes: list[RAGGraphRoute] = field(default_factory=list)
    query_entities: list[str] = field(default_factory=list)
    retrieval_modes: dict[str, int] = field(default_factory=dict)

    @property
    def paths(self) -> list[str]:
        return [route.path for route in self.routes]

    def to_payload(self) -> dict:
        return {
            "nodes": [node.__dict__ for node in self.nodes],
            "edges": [edge.__dict__ for edge in self.edges],
            "paths": self.paths,
            "routes": [route.__dict__ for route in self.routes],
            "query_entities": self.query_entities,
            "retrieval_modes": self.retrieval_modes,
            "metrics": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "route_count": len(self.routes),
                "graph_evidence_count": self.retrieval_modes.get("global_graph", 0),
                "local_evidence_count": sum(
                    count for mode, count in self.retrieval_modes.items() if mode.startswith("local")
                ),
                "avg_score": round(sum(route.score for route in self.routes) / max(len(self.routes), 1), 3),
                "query_mode": "LightRAG Hybrid",
            },
        }


class MedicalRAGGraphEngine:
    """Builds a scored RAGGraph from retrieved medical evidence."""

    def build(self, query: str, retrieved: Sequence) -> RAGGraphResult:
        query_entities = self.extract_query_entities(query)
        retrieval_modes: dict[str, int] = {}
        nodes: dict[str, RAGGraphNode] = {}
        edges: dict[str, RAGGraphEdge] = {}
        route_scores: dict[str, dict] = {}

        for rank, item in enumerate(retrieved, 1):
            mode = getattr(item, "retrieval_mode", "local") or "local"
            retrieval_modes[mode] = retrieval_modes.get(mode, 0) + 1
            disease_name = self._clean_entity(item.disease or "医学主题")
            disease_id = self._node_id("disease", disease_name)
            retrieval_score = float(getattr(item, "score", 0.1) or 0.1)
            source_type = getattr(item, "source_type", "structured") or "structured"
            source_trust = SOURCE_TRUST.get(source_type, SOURCE_TRUST.get(getattr(item, "source", ""), 0.78))
            base_score = self._normalize_score(retrieval_score) * 0.45 + source_trust * 0.2 + (1 / rank) * 0.1
            nodes[disease_id] = self._merge_node(
                nodes.get(disease_id),
                RAGGraphNode(
                    id=disease_id,
                    label=disease_name,
                    type="disease",
                    score=base_score,
                    description=self._clip(item.symptoms, 120),
                    source=getattr(item, "source", ""),
                ),
            )

            route_matched: set[str] = set()
            relation_specs = [
                ("HAS_SYMPTOM", item.symptoms, "symptom"),
                ("NEEDS_CHECK", item.check_items, "check"),
                ("SUGGESTS_CARE", item.advice, "care"),
            ]
            for relation, text, default_type in relation_specs:
                for term in self.split_terms(text)[:7]:
                    entity_type, relation_type = self.classify_term(term, relation, default_type)
                    node = self._term_node(term, entity_type, query_entities, source_type)
                    nodes[node.id] = self._merge_node(nodes.get(node.id), node)
                    edge = self._make_edge(
                        disease_id,
                        node.id,
                        relation_type,
                        item,
                        query_entities,
                        retrieval_score,
                    )
                    edges[edge.id] = self._merge_edge(edges.get(edge.id), edge)
                    if self._term_hits_query(term, query_entities):
                        route_matched.add(term)

            evidence_label = self._evidence_label(item)
            if evidence_label:
                evidence_node = self._term_node(evidence_label, "evidence", query_entities, source_type)
                nodes[evidence_node.id] = self._merge_node(nodes.get(evidence_node.id), evidence_node)
                edge = self._make_edge(disease_id, evidence_node.id, "EVIDENCED_BY", item, query_entities, retrieval_score)
                edges[edge.id] = self._merge_edge(edges.get(edge.id), edge)

            route_scores[disease_name] = {
                "disease": disease_name,
                "score": base_score + len(route_matched) * 0.08,
                "matched": tuple(sorted(route_matched)) or tuple(query_entities[:3]),
                "evidence": self._clip(item.symptoms or item.advice, 120),
            }

        routes = [
            RAGGraphRoute(
                disease=data["disease"],
                score=round(min(data["score"], 0.99), 3),
                matched_entities=data["matched"],
                evidence=data["evidence"],
                path=self._route_path(data["disease"], data["matched"], data["score"]),
            )
            for data in sorted(route_scores.values(), key=lambda value: value["score"], reverse=True)[:6]
        ]

        result = RAGGraphResult(
            nodes=sorted(nodes.values(), key=lambda node: (-node.score, node.type, node.label))[:42],
            edges=sorted(edges.values(), key=lambda edge: -edge.score)[:72],
            routes=routes,
            query_entities=query_entities,
            retrieval_modes=retrieval_modes,
        )
        self._persist_best_effort(result)
        return result

    def extract_query_entities(self, query: str) -> list[str]:
        tokens = [item.strip() for item in re.split(r"[\s,，。；;、：:！？!?()\[\]{}<>《》\"']+", query or "") if item.strip()]
        known_terms = BODY_PART_TERMS | MORPHOLOGY_TERMS | RISK_TERMS | TRIGGER_TERMS | {
            "湿疹",
            "痤疮",
            "银屑病",
            "白癜风",
            "黑色素瘤",
            "瘙痒",
            "疼痛",
            "过敏",
            "皮肤镜检查",
            "伍德灯检查",
            "真菌镜检",
        }
        tokens.extend(term for term in known_terms if term in query)
        return list(dict.fromkeys(self._clean_entity(token) for token in tokens if len(token) >= 2))[:16]

    def split_terms(self, value: str) -> list[str]:
        terms = re.split(r"[，,；;、。\n]+", value or "")
        return [self._clean_entity(term) for term in terms if self._clean_entity(term)]

    def classify_term(self, term: str, relation: str, default_type: str) -> tuple[str, str]:
        if any(value in term for value in RISK_TERMS):
            return "risk", "RISK_SIGNAL"
        if any(value in term for value in BODY_PART_TERMS):
            return "body_part", "LOCATED_AT"
        if any(value in term for value in MORPHOLOGY_TERMS):
            return "morphology", "HAS_MORPHOLOGY"
        if any(value in term for value in TRIGGER_TERMS):
            return "trigger", "TRIGGERED_BY"
        return default_type, relation

    def _term_node(self, term: str, entity_type: str, query_entities: Sequence[str], source_type: str) -> RAGGraphNode:
        hit_score = 0.18 if self._term_hits_query(term, query_entities) else 0.0
        type_bonus = {"risk": 0.18, "morphology": 0.12, "symptom": 0.1, "check": 0.08}.get(entity_type, 0.05)
        trust = SOURCE_TRUST.get(source_type, 0.78) * 0.16
        return RAGGraphNode(
            id=self._node_id(entity_type, term),
            label=term,
            type=entity_type,
            score=round(0.45 + hit_score + type_bonus + trust, 3),
            source=source_type,
        )

    def _make_edge(self, source_id: str, target_id: str, relation: str, item, query_entities: Sequence[str], retrieval_score: float) -> RAGGraphEdge:
        meta = RELATION_META.get(relation, {"label": relation, "weight": 0.7, "edge_type": "clinical"})
        evidence = self._clip(getattr(item, "symptoms", "") or getattr(item, "advice", ""), 140)
        target_label = target_id.split(":", 1)[-1]
        entity_hit = 1.0 if self._term_hits_query(target_label, query_entities) else 0.35
        score = self._normalize_score(retrieval_score) * 0.45 + meta["weight"] * 0.35 + entity_hit * 0.2
        edge_id = self._edge_id(source_id, relation, target_id, getattr(item, "source", ""))
        return RAGGraphEdge(
            id=edge_id,
            source=source_id,
            target=target_id,
            relation=relation,
            relation_label=meta["label"],
            score=round(min(score, 0.99), 3),
            evidence=evidence,
            source_type=getattr(item, "source_type", "structured"),
            page_label=getattr(item, "page_label", ""),
        )

    def _persist_best_effort(self, graph: RAGGraphResult) -> None:
        try:
            with transaction.atomic():
                entity_map = {}
                for node in graph.nodes:
                    entity, _ = KnowledgeEntity.objects.update_or_create(
                        normalized_name=self._normalize(node.label),
                        entity_type=node.type,
                        defaults={
                            "name": node.label,
                            "description": node.description,
                            "source": node.source or "rag_graph",
                            "confidence": min(max(node.score, 0.0), 1.0),
                        },
                    )
                    entity_map[node.id] = entity
                for edge in graph.edges:
                    subject = entity_map.get(edge.source)
                    obj = entity_map.get(edge.target)
                    if not subject or not obj:
                        continue
                    KnowledgeRelation.objects.update_or_create(
                        subject=subject,
                        relation_type=edge.relation,
                        object=obj,
                        evidence_source=edge.source_type,
                        defaults={
                            "weight": edge.score,
                            "evidence_text": edge.evidence,
                            "source_type": edge.source_type,
                            "page_label": edge.page_label,
                        },
                    )
        except (IntegrityError, Exception) as exc:
            logger.debug("[MedicalRAGGraphEngine] Persist skipped: %s", exc)

    def _merge_node(self, existing: RAGGraphNode | None, incoming: RAGGraphNode) -> RAGGraphNode:
        if existing is None or incoming.score > existing.score:
            return incoming
        return existing

    def _merge_edge(self, existing: RAGGraphEdge | None, incoming: RAGGraphEdge) -> RAGGraphEdge:
        if existing is None or incoming.score > existing.score:
            return incoming
        return existing

    def _term_hits_query(self, term: str, query_entities: Sequence[str]) -> bool:
        return any(term in query or query in term for query in query_entities)

    def _route_path(self, disease: str, matched: Iterable[str], score: float) -> str:
        entities = " + ".join(list(matched)[:4]) or "证据片段"
        return f"{entities} -> 支持候选 -> {disease}（路径评分 {min(score, 0.99):.2f}）"

    def _evidence_label(self, item) -> str:
        source = getattr(item, "source", "") or getattr(item, "source_type", "")
        page = getattr(item, "page_label", "")
        if page:
            return f"{source}:{page}"
        return source

    def _normalize_score(self, value: float) -> float:
        return min(1.0, math.log1p(max(value, 0.0)) / 2.4)

    def _node_id(self, entity_type: str, label: str) -> str:
        return f"{entity_type}:{self._normalize(label)}"

    def _edge_id(self, source: str, relation: str, target: str, evidence: str) -> str:
        raw = f"{source}|{relation}|{target}|{evidence}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def _normalize(self, value: str) -> str:
        return re.sub(r"\s+", "", value or "").lower()[:120]

    def _clean_entity(self, value: str) -> str:
        value = re.sub(r"\s+", "", value or "")
        value = value.strip("：:，,。；;、. ")
        return value[:80]

    def _clip(self, value: str, length: int) -> str:
        clean = " ".join((value or "").split())
        return clean[:length] + ("..." if len(clean) > length else "")


medical_rag_graph_engine = MedicalRAGGraphEngine()
