import http.client
import json
import os
import urllib

from django.db.models import Q
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from app01.models import KnowledgeDocument, KnowledgeEntity, KnowledgeRelation, MedicalKnowledge
from app01.services.knowledge_ingest import ingest_uploaded_document, safe_document_title
from app01.services.medical_rag import BUILTIN_KNOWLEDGE, medical_rag_engine


HEALTH_HABITS = [
    {
        "title": "温和清洁",
        "summary": "早晚各一次，运动或大量出汗后补充清洁，尽量选择温和配方，避免频繁去角质。",
        "tag": "基础护理",
        "image": "img/250406/images1.jpg",
    },
    {
        "title": "规律作息",
        "summary": "保持稳定睡眠与节律，减少连续熬夜，有助于炎症期皮肤的恢复与屏障稳定。",
        "tag": "生活方式",
        "image": "img/250406/sleep.jpg",
    },
    {
        "title": "饮食与补水",
        "summary": "控制高糖高油饮食，增加蔬果与优质蛋白，帮助减少痤疮和皮肤敏感的反复波动。",
        "tag": "饮食管理",
        "image": "img/250406/veget.png",
    },
]

HEALTH_WARNINGS = [
    {
        "title": "突然加重的红斑或瘙痒",
        "detail": "症状快速扩散、夜间瘙痒明显或抓挠后渗出增多时，建议尽快就诊排查。",
    },
    {
        "title": "色素痣短期变化",
        "detail": "如果出现边界不规则、颜色不均、直径增大或破溃出血，应优先到皮肤科评估。",
    },
    {
        "title": "反复化脓或疼痛性结节",
        "detail": "说明炎症可能较深或合并感染，不能只靠居家护理拖延处理。",
    },
]

HEALTH_TOPICS = [
    {"name": "敏感肌自护", "desc": "从清洁、保湿、防晒三个环节降低刺激。"},
    {"name": "痤疮护理", "desc": "关注炎症控制、不要挤压、减少复发诱因。"},
    {"name": "湿疹管理", "desc": "重视保湿、避免诱发因素、观察季节变化。"},
    {"name": "防晒与色素", "desc": "降低晒后加深、痘印残留和色沉风险。"},
]


HEALTH_FEATURED_IMAGES = [
    "img/250406/images.jpg",
    "img/250406/images1.jpg",
    "img/250406/images2.jpg",
    "img/250406/images3.jpg",
]


def _short_text(value, limit=36):
    text = (value or "").replace("，", "、").replace(",", "、").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip('、')}..."


def _featured_disease_cards():
    entries = list(MedicalKnowledge.objects.all().order_by("id")[:4])
    payload = []

    if entries:
        for index, entry in enumerate(entries):
            payload.append(
                {
                    "title": entry.disease,
                    "symptoms": _short_text(entry.symptoms, 34),
                    "checks": _short_text(entry.check_items, 28),
                    "advice": _short_text(entry.advice, 40),
                    "question": f"我想进一步了解{entry.disease}，常见表现是{_short_text(entry.symptoms, 20)}，一般建议做哪些检查，日常护理要注意什么？",
                    "source": "RAG 知识库",
                    "image": HEALTH_FEATURED_IMAGES[index % len(HEALTH_FEATURED_IMAGES)],
                }
            )
        return payload

    for index, item in enumerate(BUILTIN_KNOWLEDGE[:4]):
        payload.append(
            {
                "title": item["disease"],
                "symptoms": _short_text(item["symptoms"], 34),
                "checks": _short_text(item["check_items"], 28),
                "advice": _short_text(item["advice"], 40),
                "question": f"我想进一步了解{item['disease']}，常见表现是{_short_text(item['symptoms'], 20)}，一般建议做哪些检查，日常护理要注意什么？",
                "source": "内置医学模板",
                "image": HEALTH_FEATURED_IMAGES[index % len(HEALTH_FEATURED_IMAGES)],
            }
        )
    return payload


def health(request):
    return render(
        request,
        "health.html",
        {
            "habits": HEALTH_HABITS,
            "warnings": HEALTH_WARNINGS,
            "topics": HEALTH_TOPICS,
            "featured_diseases": _featured_disease_cards(),
        },
    )


def medical(request):
    query = (request.GET.get("q") or "").strip()
    entries = _knowledge_queryset(query)[:12 if query else 8]
    documents = KnowledgeDocument.objects.prefetch_related("chunks").all()[:10]
    stats = _knowledge_stats()

    return render(
        request,
        "medical.html",
        {
            "initial_query": query,
            "initial_entries": [_knowledge_payload(item) for item in entries],
            "initial_documents": [_document_payload(item, with_chunks=True) for item in documents],
            "knowledge_stats": stats,
        },
    )


def protect(request):
    return render(request, "protect.html")


@csrf_exempt
def get_medical(request):
    mname = request.POST.get("name")
    conn = http.client.HTTPSConnection("apis.tianapi.com")
    params = urllib.parse.urlencode({"key": "2ff1818d76c26970a7654baaf8618ce7", "word": mname})
    headers = {"Content-type": "application/x-www-form-urlencoded"}
    conn.request("POST", "/yaopin/index", params, headers)
    tianapi = conn.getresponse()
    result = tianapi.read()
    data = result.decode("utf-8")
    dict_data = json.loads(data)
    return JsonResponse(dict_data)


@csrf_exempt
def knowledge_list(request):
    query = (request.GET.get("q") or "").strip()
    entries = _knowledge_queryset(query)[:50 if query else 12]
    return JsonResponse(
        {
            "status": True,
            "entries": [_knowledge_payload(item) for item in entries],
            "stats": _knowledge_stats(),
            "query": query,
        }
    )


def knowledge_detail(request, entry_id):
    entry = get_object_or_404(MedicalKnowledge, id=entry_id)
    return JsonResponse({"status": True, "entry": _knowledge_payload(entry, full=True)})


@csrf_exempt
@require_POST
def knowledge_save(request):
    payload = _json_payload(request)
    data = payload if payload else request.POST
    entry_id = data.get("id")
    disease = (data.get("disease") or "").strip()
    symptoms = (data.get("symptoms") or "").strip()
    check_items = (data.get("check_items") or "").strip()
    advice = (data.get("advice") or "").strip()

    if not all([disease, symptoms, check_items, advice]):
        return JsonResponse({"status": False, "message": "请完整填写疾病名称、典型症状、建议检查和处理建议"}, status=400)

    if entry_id:
        entry = get_object_or_404(MedicalKnowledge, id=entry_id)
        entry.disease = disease
        entry.symptoms = symptoms
        entry.check_items = check_items
        entry.advice = advice
        entry.save(update_fields=["disease", "symptoms", "check_items", "advice"])
        message = "知识条目已更新"
    else:
        entry = MedicalKnowledge.objects.create(
            disease=disease,
            symptoms=symptoms,
            check_items=check_items,
            advice=advice,
        )
        message = "知识条目已创建"

    return JsonResponse(
        {
            "status": True,
            "message": message,
            "entry": _knowledge_payload(entry, full=True),
            "stats": _knowledge_stats(),
        }
    )


@csrf_exempt
@require_POST
def knowledge_delete(request, entry_id):
    entry = get_object_or_404(MedicalKnowledge, id=entry_id)
    entry.delete()
    return JsonResponse({"status": True, "message": "知识条目已删除", "stats": _knowledge_stats()})


@csrf_exempt
@require_POST
def knowledge_import_builtin(request):
    created = 0
    skipped = 0

    for item in BUILTIN_KNOWLEDGE:
        exists = MedicalKnowledge.objects.filter(
            disease=item["disease"],
            symptoms=item["symptoms"],
        ).exists()
        if exists:
            skipped += 1
            continue
        MedicalKnowledge.objects.create(
            disease=item["disease"],
            symptoms=item["symptoms"],
            check_items=item["check_items"],
            advice=item["advice"],
        )
        created += 1

    return JsonResponse(
        {
            "status": True,
            "message": f"已导入 {created} 条内置知识，跳过 {skipped} 条重复条目",
            "stats": _knowledge_stats(),
        }
    )


@csrf_exempt
@require_POST
def knowledge_retrieve(request):
    payload = _json_payload(request)
    query = (payload.get("query") if payload else request.POST.get("query") or "").strip()
    if not query:
        return JsonResponse({"status": False, "message": "请输入检索问题或症状描述"}, status=400)

    retrieved = medical_rag_engine.retrieve(query)
    graph = medical_rag_engine.build_graph(retrieved, query)
    return JsonResponse(
        {
            "status": True,
            "query": query,
            "references": [
                {
                    "source": item.source,
                    "disease": item.disease,
                    "symptoms": item.symptoms,
                    "check_items": item.check_items,
                    "advice": item.advice,
                    "score": round(item.score, 2),
                    "source_type": item.source_type,
                    "page_label": item.page_label,
                    "retrieval_mode": item.retrieval_mode,
                }
                for item in retrieved
            ],
            "graph": graph.to_payload(),
            "graph_paths": graph.paths[:12],
        }
    )


@csrf_exempt
def knowledge_document_list(request):
    documents = KnowledgeDocument.objects.prefetch_related("chunks").all()[:30]
    return JsonResponse(
        {
            "status": True,
            "documents": [_document_payload(item, with_chunks=True) for item in documents],
            "stats": _knowledge_stats(),
        }
    )


@csrf_exempt
@require_POST
def knowledge_document_upload(request):
    file_obj = request.FILES.get("file")
    if not file_obj:
        return JsonResponse({"status": False, "message": "请先选择要上传的 pdf 或 txt 文件"}, status=400)

    extension = os.path.splitext(file_obj.name)[1].lower()
    if extension not in {".pdf", ".txt"}:
        return JsonResponse({"status": False, "message": "当前只支持 pdf 或 txt 文件"}, status=400)

    title = (request.POST.get("title") or "").strip() or safe_document_title(file_obj.name)
    document = KnowledgeDocument.objects.create(
        title=title,
        file=file_obj,
        file_type=extension.lstrip("."),
        status="processing",
    )

    try:
        result = ingest_uploaded_document(document)
    except Exception as exc:
        document.status = "failed"
        document.save(update_fields=["status", "updated_at"])
        if document.file:
            document.file.delete(save=False)
        document.delete()
        return JsonResponse({"status": False, "message": f"文档处理失败：{exc}"}, status=400)

    document.refresh_from_db()
    return JsonResponse(
        {
            "status": True,
            "message": f"文档已入库，共生成 {result['chunks']} 个切片",
            "document": _document_payload(document, with_chunks=True),
            "stats": _knowledge_stats(),
        }
    )


@csrf_exempt
@require_POST
def knowledge_document_delete(request, document_id):
    document = get_object_or_404(KnowledgeDocument, id=document_id)
    if document.file:
        document.file.delete(save=False)
    document.delete()
    return JsonResponse({"status": True, "message": "知识文档已删除", "stats": _knowledge_stats()})


@csrf_exempt
def get_tips(request):
    try:
        conn = http.client.HTTPSConnection("apis.tianapi.com")
        params = urllib.parse.urlencode({"key": "6167edd906a2d042b16f5e847ca72674"})
        headers = {"Content-type": "application/x-www-form-urlencoded"}

        conn.request("POST", "/healthtip/index", params, headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        json_data = json.loads(data)
        return JsonResponse({"code": 200, "msg": "success", "data": json_data.get("result", {})})

    except Exception:
        return JsonResponse({"code": 500, "msg": "服务异常", "data": None})


@csrf_exempt
def get_air(request):
    mname = request.POST.get("name")
    conn = http.client.HTTPSConnection("apis.tianapi.com")
    params = urllib.parse.urlencode({"key": "6167edd906a2d042b16f5e847ca72674", "area": mname})
    headers = {"Content-type": "application/x-www-form-urlencoded"}
    conn.request("POST", "/aqi/index", params, headers)
    tianapi = conn.getresponse()
    result = tianapi.read()
    data = result.decode("utf-8")
    dict_data = json.loads(data)
    return JsonResponse(dict_data)


@csrf_exempt
def get_coup(request):
    keyword = request.POST.get("keyword")
    conn = http.client.HTTPSConnection("apis.tianapi.com")
    params = urllib.parse.urlencode({"key": "6167edd906a2d042b16f5e847ca72674", "word": keyword})
    headers = {"Content-type": "application/x-www-form-urlencoded"}
    conn.request("POST", "/healthskill/index", params, headers)
    tianapi = conn.getresponse()
    result = tianapi.read()
    data = result.decode("utf-8")
    dict_data = json.loads(data)
    return JsonResponse(dict_data)


def _knowledge_queryset(query=""):
    queryset = MedicalKnowledge.objects.all().order_by("-id")
    if query:
        queryset = queryset.filter(
            Q(disease__icontains=query)
            | Q(symptoms__icontains=query)
            | Q(check_items__icontains=query)
            | Q(advice__icontains=query)
        )
    return queryset


def _knowledge_stats():
    total = MedicalKnowledge.objects.count()
    diseases = MedicalKnowledge.objects.values("disease").distinct().count()
    symptom_hits = MedicalKnowledge.objects.exclude(symptoms="").count()
    builtin = len(BUILTIN_KNOWLEDGE)
    documents = KnowledgeDocument.objects.count()
    chunks = sum(item.total_chunks for item in KnowledgeDocument.objects.only("total_chunks"))
    entities = KnowledgeEntity.objects.count()
    relations = KnowledgeRelation.objects.count()
    return {
        "total_entries": total,
        "distinct_diseases": diseases,
        "with_symptoms": symptom_hits,
        "builtin_templates": builtin,
        "document_total": documents,
        "chunk_total": chunks,
        "entity_total": entities,
        "relation_total": relations,
    }


def _knowledge_payload(entry, full=False):
    payload = {
        "id": entry.id,
        "disease": entry.disease,
        "symptoms_preview": _preview(entry.symptoms),
        "check_preview": _preview(entry.check_items),
        "advice_preview": _preview(entry.advice),
    }
    if full:
        payload.update(
            {
                "symptoms": entry.symptoms,
                "check_items": entry.check_items,
                "advice": entry.advice,
            }
        )
        return payload
    return payload


def _document_payload(document, with_chunks=False):
    payload = {
        "id": document.id,
        "title": document.title,
        "file_type": document.file_type,
        "chunk_strategy": document.chunk_strategy,
        "status": document.status,
        "total_chars": document.total_chars,
        "total_chunks": document.total_chunks,
        "file_name": os.path.basename(document.file.name) if document.file else "",
        "updated_at": document.updated_at.strftime("%Y-%m-%d %H:%M"),
    }
    if with_chunks:
        payload["chunks"] = [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "page_label": chunk.page_label,
                "content_preview": _preview(chunk.content, limit=120),
                "token_estimate": chunk.token_estimate,
            }
            for chunk in document.chunks.all()[:6]
        ]
    return payload


def _preview(text, limit=72):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else f"{text[:limit]}..."


def _json_payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}
