"""Medical consultation RAG service with lightweight knowledge graph evidence."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Sequence

from django.conf import settings
from django.db.models import Q

from app01.models import KnowledgeChunk, KnowledgeEntity, KnowledgeRelation, MedicalKnowledge
from app01.services.rag_graph import RAGGraphResult, medical_rag_graph_engine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedKnowledge:
    """A medical knowledge chunk used as RAG context."""

    source: str
    disease: str
    symptoms: str
    check_items: str
    advice: str
    score: float
    source_type: str = "structured"
    page_label: str = ""
    retrieval_mode: str = "local"


@dataclass(frozen=True)
class GraphTriple:
    """A simple subject-relation-object medical graph edge."""

    subject: str
    relation: str
    object: str

    def as_path(self) -> str:
        return f"{self.subject} -> {self.relation} -> {self.object}"


@dataclass(frozen=True)
class LocalDocument:
    """Small fallback for environments that have not installed LangChain yet."""

    page_content: str
    metadata: dict


try:
    from langchain_core.documents import Document
except ModuleNotFoundError:  # pragma: no cover - depends on local env
    Document = LocalDocument


BUILTIN_KNOWLEDGE = [
    {
        "disease": "湿疹",
        "symptoms": "皮肤红斑、丘疹、渗出、干燥脱屑、瘙痒，常与过敏、屏障受损、刺激物接触相关。",
        "check_items": "皮肤科查体、过敏原筛查、真菌镜检或斑贴试验。",
        "advice": "避免搔抓和刺激物，保持皮肤保湿；若渗出、感染或反复发作，应皮肤科就诊。",
    },
    {
        "disease": "银屑病",
        "symptoms": "边界清楚的红色斑块，表面有银白色鳞屑，可伴瘙痒，常见于头皮、肘膝伸侧。",
        "check_items": "皮肤科查体、皮肤镜检查，必要时皮肤活检。",
        "advice": "避免自行长期使用强效药物；出现关节疼痛、广泛皮损时应尽快就诊。",
    },
    {
        "disease": "痤疮",
        "symptoms": "粉刺、丘疹、脓疱、结节，多见于面部、胸背部，可与皮脂分泌、毛囊堵塞相关。",
        "check_items": "皮肤科查体，严重或女性伴月经异常时可评估内分泌。",
        "advice": "温和清洁，避免挤压；中重度或留疤风险高时建议规范治疗。",
    },
    {
        "disease": "白癜风",
        "symptoms": "边界较清楚的色素脱失斑，表面通常光滑，可逐渐扩大。",
        "check_items": "伍德灯检查、皮肤镜检查、甲状腺功能等自身免疫相关评估。",
        "advice": "尽早皮肤科评估，注意防晒和心理支持，避免误用刺激性偏方。",
    },
    {
        "disease": "黑色素瘤警示",
        "symptoms": "色素痣不对称、边界不规则、颜色不均、直径增大、近期快速变化、破溃出血。",
        "check_items": "皮肤镜检查、专科评估，必要时病理活检。",
        "advice": "若出现 ABCDE 警示特征或短期快速变化，应尽快到皮肤科或肿瘤相关专科就诊。",
    },
    {
        "disease": "发热伴呼吸道症状",
        "symptoms": "发热、咳嗽、咽痛、流涕、乏力，可伴胸闷或气促。",
        "check_items": "体温监测、血常规、C反应蛋白、病原学检测，气促时评估血氧和胸部影像。",
        "advice": "高热不退、呼吸困难、血氧下降、胸痛或基础病患者应及时就医。",
    },
    {
        "disease": "急腹症警示",
        "symptoms": "持续或加重腹痛、腹肌紧张、呕吐、黑便或便血、发热。",
        "check_items": "腹部查体、血常规、肝胆胰酶、尿检、腹部超声或CT。",
        "advice": "突发剧烈腹痛、伴休克表现或消化道出血，应立即急诊。",
    },
]

STOPWORDS = {"我", "的", "了", "和", "有", "是", "在", "请问", "怎么办", "需要", "感觉"}


class MedicalRAGEngine:
    """Retrieves medical evidence and generates a grounded consultation reply."""

    def answer(self, user_input: str, history: Sequence[dict] | None = None) -> dict:
        prepared = self.prepare_answer(user_input, history)
        retrieved = prepared["retrieved"]
        graph: RAGGraphResult = prepared["graph"]

        if not self._llm_ready():
            return self._fallback_answer(user_input, retrieved, graph, "未配置大模型 API，已返回知识库增强建议")

        try:
            from langchain_core.output_parsers import StrOutputParser
        except ModuleNotFoundError as exc:
            return self._fallback_answer(user_input, retrieved, graph, f"LangChain 依赖未安装：{exc}")

        try:
            chain = self._build_prompt() | self._build_llm() | StrOutputParser()
            answer = chain.invoke(
                {
                    "question": prepared["question"],
                    "history": prepared["history_text"],
                    "rag_context": prepared["rag_context"],
                    "graph_context": prepared["graph_context"],
                }
            )
            return {
                "answer": answer,
                "references": self._references(retrieved),
                "graph_paths": graph.paths[:8],
                "graph_payload": graph.to_payload(),
                "model_used": settings.MEDICAL_LLM_MODEL,
                "fallback": False,
            }
        except Exception as exc:  # pragma: no cover - depends on external provider
            logger.exception("[MedicalRAGEngine] LLM call failed: %s", exc)
            return self._fallback_answer(user_input, retrieved, graph, f"大模型调用失败：{exc}")

    def stream_answer(self, user_input: str, history: Sequence[dict] | None = None) -> Iterator[dict]:
        prepared = self.prepare_answer(user_input, history)
        retrieved = prepared["retrieved"]
        graph: RAGGraphResult = prepared["graph"]
        metadata = {
            "references": self._references(retrieved),
            "graph_paths": graph.paths[:8],
            "graph_payload": graph.to_payload(),
            "model_used": settings.MEDICAL_LLM_MODEL if self._llm_ready() else "RAG fallback",
        }

        if not self._llm_ready():
            fallback = self._fallback_answer(user_input, retrieved, graph, "未配置大模型 API，已返回知识库增强建议")
            for chunk in self._chunk_text(fallback["answer"]):
                yield {"type": "chunk", "content": chunk}
            yield {"type": "done", **fallback}
            return

        try:
            prompt_value = self._build_prompt().invoke(
                {
                    "question": prepared["question"],
                    "history": prepared["history_text"],
                    "rag_context": prepared["rag_context"],
                    "graph_context": prepared["graph_context"],
                }
            )
            llm = self._build_llm()
            full_text = ""
            emitted = False
            for chunk in llm.stream(prompt_value.to_messages()):
                content = self._chunk_content(chunk)
                if not content:
                    continue
                emitted = True
                full_text += content
                yield {"type": "chunk", "content": content}

            if not emitted:
                full_text = "当前未收到模型输出，请稍后重试。"
                for chunk in self._chunk_text(full_text):
                    yield {"type": "chunk", "content": chunk}

            yield {
                "type": "done",
                        "answer": full_text,
                        "references": metadata["references"],
                        "graph_paths": metadata["graph_paths"],
                        "graph_payload": metadata["graph_payload"],
                        "model_used": metadata["model_used"],
                        "fallback": False,
                    }
        except ModuleNotFoundError as exc:
            fallback = self._fallback_answer(user_input, retrieved, graph, f"LangChain 依赖未安装：{exc}")
            for chunk in self._chunk_text(fallback["answer"]):
                yield {"type": "chunk", "content": chunk}
            yield {"type": "done", **fallback}
        except Exception as exc:  # pragma: no cover - depends on external provider
            logger.exception("[MedicalRAGEngine] LLM stream failed: %s", exc)
            fallback = self._fallback_answer(user_input, retrieved, graph, f"大模型流式调用失败：{exc}")
            for chunk in self._chunk_text(fallback["answer"]):
                yield {"type": "chunk", "content": chunk}
            yield {"type": "done", **fallback}

    def prepare_answer(self, user_input: str, history: Sequence[dict] | None = None) -> dict:
        history = history or []
        retrieved = self.retrieve(user_input)
        graph = self.build_graph(retrieved, user_input)
        return {
            "question": user_input,
            "retrieved": retrieved,
            "graph": graph,
            "history_text": self._format_history(history),
            "rag_context": self._format_context(retrieved),
            "graph_context": self._format_graph(graph),
        }

    def retrieve(self, query: str, limit: int = 5) -> List[RetrievedKnowledge]:
        documents = self._load_documents(query)
        graph_documents = self._load_graph_documents(query)
        documents.extend(graph_documents)
        if not documents:
            documents = self._builtin_documents()

        scored: dict[tuple[str, str, str], RetrievedKnowledge] = {}
        for doc in documents:
            score = self._score(query, doc)
            if score > 0:
                metadata = doc.metadata
                item = RetrievedKnowledge(
                    source=metadata.get("source", "knowledge"),
                    disease=metadata.get("disease", "未知"),
                    symptoms=metadata.get("symptoms", ""),
                    check_items=metadata.get("check_items", ""),
                    advice=metadata.get("advice", ""),
                    score=score,
                    source_type=metadata.get("source_type", "structured"),
                    page_label=metadata.get("page_label", ""),
                    retrieval_mode=metadata.get("retrieval_mode", "local"),
                )
                key = (item.source_type, item.disease, item.symptoms[:80])
                if key not in scored or item.score > scored[key].score:
                    scored[key] = item

        if not scored:
            fallback = [
                RetrievedKnowledge(
                    source=doc.metadata.get("source", "builtin"),
                    disease=doc.metadata.get("disease", "通用分诊"),
                    symptoms=doc.metadata.get("symptoms", ""),
                    check_items=doc.metadata.get("check_items", ""),
                    advice=doc.metadata.get("advice", ""),
                    score=0.1,
                    source_type=doc.metadata.get("source_type", "structured"),
                    page_label=doc.metadata.get("page_label", ""),
                    retrieval_mode=doc.metadata.get("retrieval_mode", "fallback"),
                )
                for doc in self._builtin_documents()[:3]
            ]
            return fallback

        return sorted(scored.values(), key=lambda item: item.score, reverse=True)[:limit]

    def build_graph(self, retrieved: Sequence[RetrievedKnowledge], query: str = "") -> RAGGraphResult:
        return medical_rag_graph_engine.build(query, retrieved)

    def _build_llm(self) -> ChatOpenAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.MEDICAL_LLM_MODEL,
            api_key=settings.MEDICAL_LLM_API_KEY,
            base_url=settings.MEDICAL_LLM_BASE_URL,
            temperature=0.2,
            timeout=settings.MEDICAL_LLM_TIMEOUT,
        )

    def _build_prompt(self):
        from langchain_core.prompts import ChatPromptTemplate

        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                "你是 DermoAI 的医疗问诊助手。请基于RAG证据、知识图谱路径和对话历史进行分诊式建议。"
                    "要求：不替代医生诊断；不提供处方剂量；优先识别急诊危险信号；"
                    "输出结构包含：初步判断、需要追问、建议检查、护理建议、何时就医、参考依据。",
                ),
                (
                    "human",
                    "患者本轮描述：{question}\n\n"
                    "对话历史：\n{history}\n\n"
                    "RAG检索证据：\n{rag_context}\n\n"
                    "知识图谱路径：\n{graph_context}\n\n"
                    "请用中文、温和专业、条理清晰地回答。",
                ),
            ]
        )

    def _llm_ready(self) -> bool:
        return bool(settings.MEDICAL_LLM_API_KEY and settings.MEDICAL_LLM_BASE_URL)

    def _load_documents(self, query: str) -> List[Document]:
        try:
            keywords = self._keywords(query)
            condition = Q()
            for keyword in keywords:
                condition |= (
                    Q(disease__icontains=keyword)
                    | Q(symptoms__icontains=keyword)
                    | Q(check_items__icontains=keyword)
                    | Q(advice__icontains=keyword)
                )
            records = MedicalKnowledge.objects.filter(condition).order_by("-id")[:30] if condition else []
            chunk_condition = Q()
            for keyword in keywords:
                chunk_condition |= (
                    Q(document__title__icontains=keyword)
                    | Q(content__icontains=keyword)
                )
            chunks = KnowledgeChunk.objects.select_related("document").filter(chunk_condition).order_by("document_id", "chunk_index")[:40] if chunk_condition else []
            documents = [self._record_to_document(record, "database") for record in records]
            documents.extend(self._chunk_to_document(chunk, "document_chunk") for chunk in chunks)
            return documents
        except Exception as exc:
            logger.warning("[MedicalRAGEngine] DB retrieval failed: %s", exc)
            return []

    def _load_graph_documents(self, query: str) -> List[Document]:
        """LightRAG-inspired graph expansion: entities and relations join retrieval."""
        try:
            keywords = self._keywords(query)
            if not keywords:
                return []
            entity_condition = Q()
            for keyword in keywords:
                entity_condition |= Q(name__icontains=keyword) | Q(description__icontains=keyword)
            entities = list(KnowledgeEntity.objects.filter(entity_condition).order_by("-confidence")[:16])
            if not entities:
                return []
            relations = (
                KnowledgeRelation.objects.select_related("subject", "object")
                .filter(Q(subject__in=entities) | Q(object__in=entities))
                .order_by("-weight", "-created_at")[:48]
            )
            documents: list[Document] = []
            for relation in relations:
                subject = relation.subject
                obj = relation.object
                disease_entity = subject if subject.entity_type == "disease" else obj if obj.entity_type == "disease" else subject
                relation_label = relation.get_relation_type_display()
                evidence = relation.evidence_text or f"{subject.name} 与 {obj.name} 存在「{relation_label}」关系。"
                check_items = obj.name if obj.entity_type == "check" else relation_label
                advice = obj.name if obj.entity_type == "care" else "该关系来自知识图谱扩展召回，请结合结构化条目和原文证据综合判断。"
                documents.append(
                    Document(
                        page_content=(
                            f"图谱主题：{disease_entity.name}\n"
                            f"关系路径：{subject.name} -> {relation_label} -> {obj.name}\n"
                            f"证据摘要：{evidence}"
                        ),
                        metadata={
                            "source": "knowledge_graph",
                            "source_type": "graph_relation",
                            "retrieval_mode": "global_graph",
                            "disease": disease_entity.name,
                            "symptoms": evidence,
                            "check_items": check_items,
                            "advice": advice,
                            "page_label": relation.page_label,
                        },
                    )
                )
            return documents
        except Exception as exc:
            logger.warning("[MedicalRAGEngine] graph retrieval failed: %s", exc)
            return []

    def _record_to_document(self, record: MedicalKnowledge, source: str) -> Document:
        return Document(
            page_content=(
                f"疾病：{record.disease}\n"
                f"典型症状：{record.symptoms}\n"
                f"建议检查：{record.check_items}\n"
                f"处理建议：{record.advice}"
            ),
            metadata={
                "source": source,
                "source_type": "structured",
                "retrieval_mode": "local_structured",
                "disease": record.disease,
                "symptoms": record.symptoms,
                "check_items": record.check_items,
                "advice": record.advice,
            },
        )

    def _builtin_documents(self) -> List[Document]:
        return [
            Document(
                page_content=(
                    f"疾病：{item['disease']}\n"
                    f"典型症状：{item['symptoms']}\n"
                    f"建议检查：{item['check_items']}\n"
                    f"处理建议：{item['advice']}"
                ),
                metadata={"source": "builtin", "source_type": "structured", "retrieval_mode": "fallback_builtin", **item},
            )
            for item in BUILTIN_KNOWLEDGE
        ]

    def _chunk_to_document(self, chunk: KnowledgeChunk, source: str) -> Document:
        title = chunk.document.title
        page_suffix = f"（{chunk.page_label}）" if chunk.page_label else ""
        return Document(
            page_content=f"文档标题：{title}{page_suffix}\n知识片段：{chunk.content}",
            metadata={
                "source": source,
                "source_type": "document_chunk",
                "retrieval_mode": "local_chunk",
                "disease": title,
                "symptoms": chunk.content,
                "check_items": chunk.page_label or "源文档切片",
                "advice": "请结合原始文档上下文和临床信息综合判断。",
                "page_label": chunk.page_label,
            },
        )

    def _score(self, query: str, doc: Document) -> float:
        text = doc.page_content
        metadata = doc.metadata
        score = 0.0
        if metadata.get("disease") and metadata["disease"] in query:
            score += 5
        if metadata.get("source_type") == "graph_relation":
            score += 1.4
        if metadata.get("retrieval_mode") == "global_graph":
            score += 0.8
        for keyword in self._keywords(query):
            if keyword in text:
                score += 1 + min(len(keyword), 4) * 0.2
        return score

    def _keywords(self, query: str) -> List[str]:
        tokens = re.split(r"[\s,，。；;、：:！？!?()\[\]{}<>《》\"']+", query)
        tokens = [token.strip() for token in tokens if token.strip() and token.strip() not in STOPWORDS]
        known_terms = [
            "发热",
            "咳嗽",
            "胸痛",
            "腹痛",
            "瘙痒",
            "红斑",
            "丘疹",
            "脱屑",
            "水疱",
            "脓疱",
            "色素",
            "黑痣",
            "出血",
            "疼痛",
            "过敏",
            "湿疹",
            "痤疮",
            "银屑病",
            "白癜风",
            "黑色素瘤",
        ]
        tokens.extend(term for term in known_terms if term in query)
        if not tokens and query.strip():
            tokens.append(query.strip())
        return list(dict.fromkeys(tokens))

    def _split_medical_terms(self, value: str) -> List[str]:
        terms = re.split(r"[，,；;、。\n]+", value or "")
        return [term.strip() for term in terms if term.strip()]

    def _format_history(self, history: Sequence[dict]) -> str:
        if not history:
            return "无"
        recent = history[-8:]
        return "\n".join(f"{item.get('role', 'unknown')}: {item.get('content', '')}" for item in recent)

    def _format_context(self, retrieved: Iterable[RetrievedKnowledge]) -> str:
        lines = []
        for index, item in enumerate(retrieved, 1):
            lines.append(
                f"[{index}] 来源：{item.source}；疾病/主题：{item.disease}\n"
                f"症状/片段：{item.symptoms}\n检查：{item.check_items}\n建议：{item.advice}"
            )
        return "\n\n".join(lines) if lines else "无相关证据"

    def _format_graph(self, graph: RAGGraphResult) -> str:
        if not graph or not graph.routes:
            return "无图谱路径"
        route_lines = [
            f"{route.path}；匹配实体：{'、'.join(route.matched_entities) or '无'}；证据摘要：{route.evidence}"
            for route in graph.routes[:6]
        ]
        edge_lines = [
            f"{edge.source.split(':', 1)[-1]} -> {edge.relation_label} -> {edge.target.split(':', 1)[-1]}（{edge.score:.2f}）"
            for edge in graph.edges[:8]
        ]
        return "\n".join(route_lines + edge_lines)

    def _references(self, retrieved: Sequence[RetrievedKnowledge]) -> List[dict]:
        return [
            {
                "source": item.source,
                "disease": item.disease,
                "symptoms": item.symptoms,
                "check_items": item.check_items,
                "advice": item.advice,
                "source_type": item.source_type,
                "page_label": item.page_label,
                "retrieval_mode": item.retrieval_mode,
            }
            for item in retrieved
        ]

    def _fallback_answer(
        self,
        question: str,
        retrieved: Sequence[RetrievedKnowledge],
        graph: RAGGraphResult,
        reason: str,
    ) -> dict:
        top = retrieved[0] if retrieved else None
        if top:
            answer = (
                f"{reason}\n\n"
                f"根据当前描述“{question}”，知识库最相关的参考为：{top.disease}。\n"
                f"典型表现：{top.symptoms}\n"
                f"建议检查：{top.check_items}\n"
                f"处理建议：{top.advice}\n\n"
                "如出现持续高热、呼吸困难、胸痛、意识异常、皮损快速扩大、破溃出血等危险信号，请立即就医。"
            )
        else:
            answer = (
                f"{reason}\n\n"
                "当前没有检索到足够知识库证据。请补充症状部位、持续时间、严重程度、诱因和伴随症状；"
                "若症状严重或进展迅速，请优先线下就医。"
            )
        return {
            "answer": answer,
            "references": self._references(retrieved),
            "graph_paths": graph.paths[:8],
            "graph_payload": graph.to_payload(),
            "model_used": "RAG fallback",
            "fallback": True,
        }

    def _chunk_text(self, text: str, size: int = 28) -> Iterator[str]:
        for index in range(0, len(text), size):
            yield text[index:index + size]

    def _chunk_content(self, chunk) -> str:
        content = getattr(chunk, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text", ""))
                else:
                    parts.append(str(item))
            return "".join(parts)
        return str(content) if content else ""


medical_rag_engine = MedicalRAGEngine()
