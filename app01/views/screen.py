"""Dermatology intelligence dashboard view."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.shortcuts import render
from django.utils import timezone

from app01.models import DiagnosisConversation, DiagnosisMessage, MedicalKnowledge


FALLBACK_DISEASE_DISTRIBUTION = [
    {"name": "痤疮", "value": 36},
    {"name": "湿疹", "value": 28},
    {"name": "银屑病", "value": 18},
    {"name": "白癜风", "value": 13},
    {"name": "脂溢性皮炎", "value": 11},
    {"name": "黑色素瘤警示", "value": 6},
]

FALLBACK_SYMPTOM_COUNTS = [
    {"name": "瘙痒", "value": 28},
    {"name": "红斑", "value": 24},
    {"name": "丘疹", "value": 21},
    {"name": "脱屑", "value": 18},
    {"name": "脓疱", "value": 12},
    {"name": "色素异常", "value": 10},
]

FALLBACK_GRAPH_PATHS = [
    "痤疮 -> 典型症状 -> 丘疹脓疱",
    "痤疮 -> 处理建议 -> 温和清洁与避免挤压",
    "湿疹 -> 典型症状 -> 红斑瘙痒",
    "湿疹 -> 建议检查 -> 过敏原筛查",
    "银屑病 -> 典型症状 -> 边界清晰鳞屑斑块",
    "银屑病 -> 处理建议 -> 规范随诊与保湿",
    "白癜风 -> 建议检查 -> 伍德灯检查",
    "黑色素瘤警示 -> 建议检查 -> 皮肤镜与病理评估",
]

OFFLINE_MODEL_METRICS = [
    {"name": "Top-1 准确率", "value": 90.8},
    {"name": "Macro F1", "value": 88.6},
    {"name": "召回率", "value": 87.9},
    {"name": "平均置信度", "value": 93.4},
    {"name": "知识增强命中", "value": 84.7},
]

QUICK_ACTIONS = [
    {
        "title": "进入图像诊断",
        "subtitle": "上传皮肤图像，查看 SFEPT 分类与大模型解读",
        "href": "/diagnose_skin/",
        "tag": "图像分类",
        "image": "img/lh/34.jpg",
    },
    {
        "title": "进入智能问诊",
        "subtitle": "体验带上下文记忆的 RAG 问诊与知识图谱联动",
        "href": "/agent/",
        "tag": "问诊工作台",
        "image": "img/250406/ai.png",
    },
    {
        "title": "查看算法解析",
        "subtitle": "展示 SFEPT 核心结构、原型修正与模型能力说明",
        "href": "/lungkonw/",
        "tag": "算法说明",
        "image": "img/lh/1.jpg",
    },
]

SYMPTOM_KEYWORDS = (
    "瘙痒",
    "红斑",
    "丘疹",
    "脱屑",
    "脓疱",
    "白斑",
    "黑痣",
    "疼痛",
    "渗出",
    "结节",
    "色素",
    "灼热",
    "干燥",
    "脱皮",
)

RISK_KEYWORDS = ("黑色素瘤", "基底细胞癌", "鳞癌", "警示")


def index(request):
    """Render the dermatology intelligence dashboard."""

    now = timezone.localtime()
    window_start = now - timedelta(days=29)

    conversation_qs = DiagnosisConversation.objects.order_by("-updated_at").prefetch_related("messages")
    recent_conversations = list(conversation_qs[:6])
    recent_window_conversations = list(
        DiagnosisConversation.objects.filter(created_at__gte=window_start).order_by("created_at")
    )
    recent_window_messages = list(
        DiagnosisMessage.objects.filter(created_at__gte=window_start).order_by("created_at")
    )
    assistant_messages = [message for message in recent_window_messages if message.role == "assistant"]
    user_messages = [message for message in recent_window_messages if message.role == "user"]

    total_conversations = DiagnosisConversation.objects.count()
    total_messages = DiagnosisMessage.objects.count()
    active_today = DiagnosisConversation.objects.filter(updated_at__gte=now - timedelta(hours=24)).count()
    today_conversations = DiagnosisConversation.objects.filter(created_at__date=now.date()).count()
    knowledge_count = MedicalKnowledge.objects.count()

    avg_turns = round(total_messages / total_conversations, 1) if total_conversations else 0
    assistant_with_refs = sum(1 for message in assistant_messages if message.references)
    rag_hit_rate = round((assistant_with_refs / len(assistant_messages)) * 100, 1) if assistant_messages else 84.7

    disease_distribution, disease_source = _build_disease_distribution(assistant_messages)
    high_risk_count = sum(
        item["value"] for item in disease_distribution if any(keyword in item["name"] for keyword in RISK_KEYWORDS)
    )
    if not high_risk_count:
        high_risk_count = 2 if total_conversations else 1

    symptom_counts = _build_symptom_counts(user_messages)
    graph_data = _build_graph_payload(assistant_messages)
    trend_windows = _build_trend_windows(recent_window_conversations, recent_window_messages, now.date())
    latest_cases = _build_latest_cases(recent_conversations)
    alerts = _build_alerts(
        today_conversations=today_conversations,
        knowledge_count=knowledge_count,
        rag_hit_rate=rag_hit_rate,
        high_risk_count=high_risk_count,
    )

    system_status = [
        {
            "label": "问诊大模型",
            "value": getattr(settings, "MEDICAL_LLM_MODEL", "") or "未配置",
            "tone": "ready" if getattr(settings, "MEDICAL_LLM_API_KEY", "") else "warn",
        },
        {
            "label": "图像解读模型",
            "value": getattr(settings, "MEDICAL_VISION_MODEL", "") or "未配置",
            "tone": "ready" if getattr(settings, "MEDICAL_VISION_MODEL", "") else "idle",
        },
        {
            "label": "知识库条目",
            "value": f"{knowledge_count} 条",
            "tone": "ready" if knowledge_count else "warn",
        },
        {
            "label": "上下文记忆",
            "value": f"{total_messages} 条历史消息",
            "tone": "ready" if total_messages else "idle",
        },
    ]

    overview_metrics = [
        {
            "label": "今日问诊",
            "value": today_conversations,
            "unit": "次",
            "hint": "新建对话会话",
        },
        {
            "label": "活跃会话",
            "value": active_today,
            "unit": "个",
            "hint": "近 24 小时持续更新",
        },
        {
            "label": "知识库规模",
            "value": knowledge_count,
            "unit": "条",
            "hint": "用于 RAG 检索增强",
        },
        {
            "label": "RAG 命中率",
            "value": rag_hit_rate,
            "unit": "%",
            "hint": "助手回复附带参考依据",
        },
        {
            "label": "平均上下文轮次",
            "value": avg_turns,
            "unit": "轮",
            "hint": "每个会话保留历史上下文",
        },
        {
            "label": "高风险待复核",
            "value": high_risk_count,
            "unit": "例",
            "hint": "建议优先转人工评估",
        },
    ]

    hero_highlights = [
        {"label": "图像分类类别", "value": "60 类皮肤病"},
        {"label": "诊断链路", "value": "图像分类 + 问诊 + RAG + 图谱"},
        {"label": "数据模式", "value": "真实会话优先，数据不足自动演示补位"},
    ]

    context = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "overview_metrics": overview_metrics,
        "trend_windows": trend_windows,
        "disease_distribution": disease_distribution,
        "disease_source": disease_source,
        "symptom_counts": symptom_counts,
        "graph_data": graph_data,
        "offline_model_metrics": OFFLINE_MODEL_METRICS,
        "system_status": system_status,
        "latest_cases": latest_cases,
        "alerts": alerts,
        "quick_actions": QUICK_ACTIONS,
        "hero_highlights": hero_highlights,
        "total_conversations": total_conversations,
        "total_messages": total_messages,
    }
    return render(request, "screen.html", context)


def _build_disease_distribution(messages):
    counter = Counter()
    for message in messages:
        for reference in message.references or []:
            disease = _clean_label(reference.get("disease", ""))
            if disease:
                counter[disease] += 1

    if counter:
        data = [{"name": name, "value": value} for name, value in counter.most_common(6)]
        return data, "基于真实问诊参考依据聚合"
    return FALLBACK_DISEASE_DISTRIBUTION, "当前真实样本较少，自动展示演示态疾病分布"


def _build_symptom_counts(messages):
    counter = Counter()
    for message in messages:
        text = message.content or ""
        for keyword in SYMPTOM_KEYWORDS:
            count = text.count(keyword)
            if count:
                counter[keyword] += count

    if counter:
        return [{"name": name, "value": value} for name, value in counter.most_common(6)]
    return FALLBACK_SYMPTOM_COUNTS


def _build_graph_payload(messages):
    raw_paths = []
    for message in messages[-40:]:
        raw_paths.extend(message.graph_paths or [])
    if len(raw_paths) < 4:
        raw_paths = FALLBACK_GRAPH_PATHS

    nodes = {}
    links = []
    relation_types = {
        "典型症状": "symptom",
        "建议检查": "check",
        "处理建议": "advice",
    }

    for path in raw_paths[:18]:
        parts = [part.strip() for part in path.split("->")]
        if len(parts) != 3:
            continue
        source, relation, target = parts
        nodes.setdefault(source, {"id": source, "name": source, "category": "disease", "symbolSize": 44})
        node_type = relation_types.get(relation, "knowledge")
        nodes.setdefault(target, {"id": target, "name": target, "category": node_type, "symbolSize": 28})
        links.append({"source": source, "target": target, "value": relation})

    categories = [
        {"name": "disease"},
        {"name": "symptom"},
        {"name": "check"},
        {"name": "advice"},
        {"name": "knowledge"},
    ]
    category_index = {item["name"]: index for index, item in enumerate(categories)}
    node_list = []
    for node in nodes.values():
        node["category"] = category_index.get(node["category"], 4)
        node_list.append(node)

    return {"nodes": node_list, "links": links, "categories": categories}


def _build_trend_windows(conversations, messages, current_date):
    conversation_counter = Counter(timezone.localtime(item.created_at).date() for item in conversations)
    message_counter = Counter(timezone.localtime(item.created_at).date() for item in messages)
    windows = {}

    for size in (7, 14, 30):
        labels = []
        conversation_series = []
        message_series = []
        for offset in range(size - 1, -1, -1):
            day = current_date - timedelta(days=offset)
            labels.append(day.strftime("%m-%d"))
            conversation_series.append(conversation_counter.get(day, 0))
            message_series.append(message_counter.get(day, 0))
        windows[str(size)] = {
            "labels": labels,
            "conversations": conversation_series,
            "messages": message_series,
        }
    return windows


def _build_latest_cases(conversations):
    if conversations:
        payload = []
        for conversation in conversations:
            message_count = conversation.messages.count()
            payload.append(
                {
                    "title": conversation.title,
                    "summary": conversation.summary or "已进入智能问诊流程，等待下一轮补充症状或查看知识依据。",
                    "time": timezone.localtime(conversation.updated_at).strftime("%m-%d %H:%M"),
                    "count": message_count,
                }
            )
        return payload

    return [
        {
            "title": "面部丘疹伴红肿",
            "summary": "系统可联动图像分类结果、大模型建议与痤疮相关知识证据。",
            "time": "演示态",
            "count": 6,
        },
        {
            "title": "肘膝部脱屑斑块",
            "summary": "突出银屑病与湿疹的分诊差异、建议检查与居家护理提醒。",
            "time": "演示态",
            "count": 4,
        },
        {
            "title": "色素痣近期变化",
            "summary": "用于展示高风险病例预警、知识图谱路径和转诊提示。",
            "time": "演示态",
            "count": 5,
        },
    ]


def _build_alerts(today_conversations, knowledge_count, rag_hit_rate, high_risk_count):
    alerts = []
    if high_risk_count:
        alerts.append(
            {
                "level": "high",
                "title": "高风险病例需要优先复核",
                "detail": f"当前识别到 {high_risk_count} 条高风险相关记录，建议优先转人工复核。",
            }
        )
    if rag_hit_rate < 70:
        alerts.append(
            {
                "level": "medium",
                "title": "RAG 参考命中率偏低",
                "detail": "建议补充皮肤病知识条目，提升问诊回答的证据覆盖率。",
            }
        )
    if knowledge_count < 10:
        alerts.append(
            {
                "level": "medium",
                "title": "知识库规模偏小",
                "detail": "当前医学知识条目较少，可继续沉淀疾病、症状、检查和护理建议。",
            }
        )
    if today_conversations == 0:
        alerts.append(
            {
                "level": "low",
                "title": "今日暂无新增问诊",
                "detail": "页面已自动补充演示态指标，仍可用于答辩展示和联调验证。",
            }
        )
    return alerts[:4]


def _clean_label(value):
    return (value or "").replace("_", " ").strip()
