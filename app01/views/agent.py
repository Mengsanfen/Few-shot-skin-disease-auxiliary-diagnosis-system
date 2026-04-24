"""Dermatology consultation workspace powered by RAG and knowledge graph evidence."""

import json

from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from app01.models import DiagnosisConversation, DiagnosisMessage
from app01.services.medical_rag import medical_rag_engine


QUICK_PROMPTS = [
    "手臂出现红斑并伴有瘙痒，持续一周，可能是什么原因？",
    "脸上反复长痤疮，还会留下痘印，日常护理要注意什么？",
    "皮肤有一块白斑，边界比较清楚，需要做哪些检查？",
    "身上黑痣最近变大、颜色不均，要不要马上去医院？",
    "皮肤脱屑、发红，怎么区分湿疹和银屑病？",
]


def ai_diagnosis(request):
    """Render the dermatology consultation workspace."""

    session_key = _ensure_session(request)
    conversations = _conversation_queryset(request, session_key)[:12]
    active = conversations[0] if conversations else _create_conversation(request, session_key)
    messages = [_message_payload(message) for message in active.messages.all()]

    return render(
        request,
        "agent.html",
        {
            "conversation": active,
            "conversations": conversations,
            "messages": messages,
            "quick_prompts": QUICK_PROMPTS,
            "prefill_prompt": (request.GET.get("prompt") or "").strip(),
        },
    )


@require_POST
def chat_message(request):
    """Append a message, run RAG, and return assistant response."""

    session_key = _ensure_session(request)
    payload = _json_payload(request)
    message = (payload.get("message") or payload.get("symptoms") or "").strip()
    conversation_id = payload.get("conversation_id")

    if not message:
        return JsonResponse({"status": False, "message": "请输入皮肤症状或咨询问题"}, status=400)

    conversation = _get_or_create_active_conversation(request, session_key, conversation_id, message)
    history = [_message_payload(item) for item in conversation.messages.all()]

    user_message = DiagnosisMessage.objects.create(
        conversation=conversation,
        role="user",
        content=message,
    )

    rag_result = medical_rag_engine.answer(message, history)
    assistant_message = DiagnosisMessage.objects.create(
        conversation=conversation,
        role="assistant",
        content=rag_result["answer"],
        references=rag_result.get("references", []),
        graph_paths=rag_result.get("graph_paths", []),
        graph_payload=rag_result.get("graph_payload", {}),
        model_used=rag_result.get("model_used", ""),
    )

    _refresh_conversation(conversation, message, rag_result)

    return JsonResponse(
        {
            "status": True,
            "conversation": _conversation_payload(conversation),
            "user_message": _message_payload(user_message),
            "assistant_message": _message_payload(assistant_message),
            "graph": rag_result.get("graph_payload") or _graph_payload(rag_result.get("graph_paths", [])),
            "references": rag_result.get("references", []),
        }
    )


@require_POST
def chat_message_stream(request):
    """Stream assistant reply while preserving conversation history."""

    session_key = _ensure_session(request)
    payload = _json_payload(request)
    message = (payload.get("message") or payload.get("symptoms") or "").strip()
    conversation_id = payload.get("conversation_id")

    if not message:
        return JsonResponse({"status": False, "message": "请输入皮肤症状或咨询问题"}, status=400)

    conversation = _get_or_create_active_conversation(request, session_key, conversation_id, message)
    history = [_message_payload(item) for item in conversation.messages.all()]

    user_message = DiagnosisMessage.objects.create(
        conversation=conversation,
        role="user",
        content=message,
    )
    conversation_payload = _conversation_payload(conversation)

    def event_stream():
        assistant_text = ""
        final_result = None

        yield _stream_event(
            {
                "type": "conversation",
                "conversation": conversation_payload,
                "user_message": _message_payload(user_message),
            }
        )

        for item in medical_rag_engine.stream_answer(message, history):
            if item.get("type") == "chunk":
                assistant_text += item.get("content", "")
                yield _stream_event(item)
                continue

            if item.get("type") == "done":
                final_result = item
                if not assistant_text:
                    assistant_text = item.get("answer", "")
                assistant_message = DiagnosisMessage.objects.create(
                    conversation=conversation,
                    role="assistant",
                    content=assistant_text,
                    references=item.get("references", []),
                    graph_paths=item.get("graph_paths", []),
                    graph_payload=item.get("graph_payload", {}),
                    model_used=item.get("model_used", ""),
                )
                _refresh_conversation(conversation, message, item)
                yield _stream_event(
                    {
                        "type": "done",
                        "conversation": _conversation_payload(conversation),
                        "assistant_message": _message_payload(assistant_message),
                        "graph": item.get("graph_payload") or _graph_payload(item.get("graph_paths", [])),
                        "references": item.get("references", []),
                    }
                )
                break

        if final_result is None:
            fallback = {
                "answer": assistant_text or "暂时未生成回复，请稍后重试。",
                "references": [],
                "graph_paths": [],
                "model_used": "stream-fallback",
            }
            assistant_message = DiagnosisMessage.objects.create(
                conversation=conversation,
                role="assistant",
                content=fallback["answer"],
                references=[],
                graph_paths=[],
                graph_payload={},
                model_used=fallback["model_used"],
            )
            _refresh_conversation(conversation, message, fallback)
            yield _stream_event(
                {
                    "type": "done",
                    "conversation": _conversation_payload(conversation),
                    "assistant_message": _message_payload(assistant_message),
                    "graph": _graph_payload([]),
                    "references": [],
                }
            )

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def conversation_detail(request, conversation_id):
    """Return stored messages for one conversation."""

    session_key = _ensure_session(request)
    conversation = get_object_or_404(_conversation_queryset(request, session_key), id=conversation_id)
    return JsonResponse(
        {
            "status": True,
            "conversation": _conversation_payload(conversation),
            "messages": [_message_payload(message) for message in conversation.messages.all()],
        }
    )


@require_POST
def new_conversation(request):
    """Create a fresh conversation."""

    session_key = _ensure_session(request)
    conversation = _create_conversation(request, session_key)
    return JsonResponse({"status": True, "conversation": _conversation_payload(conversation), "messages": []})


@require_POST
def clear_conversation(request, conversation_id):
    """Delete one stored conversation."""

    session_key = _ensure_session(request)
    conversation = get_object_or_404(_conversation_queryset(request, session_key), id=conversation_id)
    conversation.delete()
    remaining = _conversation_queryset(request, session_key)[:12]
    active = remaining[0] if remaining else _create_conversation(request, session_key)
    return JsonResponse(
        {
            "status": True,
            "conversation": _conversation_payload(active),
            "conversations": [_conversation_payload(item) for item in remaining],
            "messages": [_message_payload(message) for message in active.messages.all()],
        }
    )


@require_POST
def graph_query(request):
    """Query RAG evidence and graph paths without adding chat messages."""

    payload = _json_payload(request)
    query = (payload.get("query") or "").strip()
    if not query:
        return JsonResponse({"status": False, "message": "请输入疾病、症状或检查关键词"}, status=400)

    retrieved = medical_rag_engine.retrieve(query)
    graph = medical_rag_engine.build_graph(retrieved, query)
    references = [
        {
            "source": item.source,
            "disease": item.disease,
            "symptoms": item.symptoms,
            "check_items": item.check_items,
            "advice": item.advice,
            "retrieval_mode": item.retrieval_mode,
            "source_type": item.source_type,
        }
        for item in retrieved
    ]
    return JsonResponse(
        {
            "status": True,
            "graph": graph.to_payload(),
            "references": references,
        }
    )


def _ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _conversation_queryset(request, session_key):
    queryset = DiagnosisConversation.objects.filter(session_key=session_key)
    if request.user.is_authenticated:
        queryset = DiagnosisConversation.objects.filter(user=request.user) | queryset
    return queryset.distinct().prefetch_related("messages")


def _create_conversation(request, session_key, title="新的皮肤问诊"):
    return DiagnosisConversation.objects.create(
        title=title,
        session_key=session_key,
        user=request.user if request.user.is_authenticated else None,
    )


def _get_or_create_active_conversation(request, session_key, conversation_id, first_message):
    if conversation_id:
        conversation = _conversation_queryset(request, session_key).filter(id=conversation_id).first()
        if conversation:
            return conversation
    title = _make_title(first_message)
    return _create_conversation(request, session_key, title)


def _refresh_conversation(conversation, user_message, rag_result):
    if conversation.title == "新的皮肤问诊":
        conversation.title = _make_title(user_message)
    references = rag_result.get("references", [])
    if references:
        diseases = "、".join(item.get("disease", "") for item in references[:3] if item.get("disease"))
        conversation.summary = f"相关知识：{diseases}" if diseases else conversation.summary
    conversation.save(update_fields=["title", "summary", "updated_at"])


def _make_title(text):
    clean = " ".join(text.split())
    return clean[:28] + ("..." if len(clean) > 28 else "")


def _json_payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _conversation_payload(conversation):
    return {
        "id": conversation.id,
        "title": conversation.title,
        "summary": conversation.summary,
        "updated_at": conversation.updated_at.strftime("%Y-%m-%d %H:%M"),
        "message_count": conversation.messages.count(),
    }


def _message_payload(message):
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "references": message.references,
        "graph_paths": message.graph_paths,
        "graph_payload": message.graph_payload,
        "model_used": message.model_used,
        "created_at": message.created_at.strftime("%H:%M"),
    }


def _graph_payload(paths):
    nodes = {}
    edges = []
    for path in paths:
        parts = [part.strip() for part in path.split("->")]
        if len(parts) != 3:
            continue
        subject, relation, obj = parts
        nodes.setdefault(subject, {"id": subject, "label": subject, "type": "disease"})
        nodes.setdefault(obj, {"id": obj, "label": obj, "type": relation})
        edges.append({"source": subject, "target": obj, "relation": relation})
    return {"nodes": list(nodes.values()), "edges": edges, "paths": paths}


def _stream_event(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
