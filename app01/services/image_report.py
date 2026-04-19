"""LLM-assisted report generation for skin image classification results."""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import List

from django.conf import settings
from django.utils import timezone
from PIL import Image

logger = logging.getLogger(__name__)


def generate_image_diagnosis_report(
    *,
    image: Image.Image,
    prediction: dict,
    top_predictions: List[dict],
    basic_tips: str,
) -> dict:
    """Generate a concise model report from image and classifier output."""

    if not _llm_ready():
        return {
            "ai_analysis": _fallback_report(prediction, top_predictions, basic_tips, "未配置大模型 API"),
            "ai_analysis_available": False,
            "analysis_source": "local_fallback",
        }

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.MEDICAL_VISION_MODEL,
            api_key=settings.MEDICAL_LLM_API_KEY,
            base_url=settings.MEDICAL_LLM_BASE_URL,
            temperature=0.2,
            timeout=settings.MEDICAL_LLM_TIMEOUT,
        )
        scores_text = _format_scores(top_predictions)
        image_profile = _image_profile(image)
        human_text = (
            "请结合皮肤图像分类模型输出，生成辅助诊断建议。\n"
            f"分类结果：{prediction.get('predicted_class_name')}\n"
            f"置信度：{prediction.get('confidence_percent')}\n"
            f"Top预测：{scores_text}\n"
            f"上传图片基础信息：{image_profile}\n"
            f"规则建议：{basic_tips}\n"
            "输出包含：影像观察、模型结果解释、建议就医科室/检查、居家注意事项、风险提醒。"
        )
        user_content = human_text
        if getattr(settings, "MEDICAL_VISION_SEND_IMAGE", False):
            image_url = _image_to_data_url(image)
            user_content = [
                {"type": "text", "text": human_text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]

        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "你是皮肤科辅助诊断报告助手。必须说明该结果仅供参考，不能替代医生诊断。"
                        "不要给出处方剂量；对疑似肿瘤、破溃出血、快速扩大等情况强调尽快就医。"
                        "禁止编造检查结果、具体治疗方案和任何日期时间。"
                        "不要自己输出“报告生成时间”，时间统一由系统追加。"
                    )
                ),
                HumanMessage(content=user_content),
            ]
        )
        normalized_report = _normalize_report(response.content)
        return {
            "ai_analysis": normalized_report,
            "ai_analysis_available": True,
            "analysis_source": settings.MEDICAL_VISION_MODEL,
        }
    except Exception as exc:  # pragma: no cover - depends on external provider
        logger.exception("[image_report] LLM image report failed: %s", exc)
        return {
            "ai_analysis": _fallback_report(prediction, top_predictions, basic_tips, f"大模型解读失败：{exc}"),
            "ai_analysis_available": False,
            "analysis_source": "local_fallback",
        }


def _llm_ready() -> bool:
    return bool(settings.MEDICAL_LLM_API_KEY and settings.MEDICAL_LLM_BASE_URL)


def _image_to_data_url(image: Image.Image) -> str:
    image = image.convert("RGB")
    image.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _image_profile(image: Image.Image) -> str:
    width, height = image.size
    return f"{width}x{height}px，颜色模式 {image.mode}"


def _format_scores(top_predictions: List[dict]) -> str:
    if not top_predictions:
        return "未返回Top预测"
    return "；".join(
        f"{item.get('class_name')} {float(item.get('confidence', 0)) * 100:.2f}%"
        for item in top_predictions
    )


def _normalize_report(content: str) -> str:
    generated_at = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
    cleaned = re.sub(r"(?im)^\s*[*-]?\s*报告生成时间[:：].*$", "", content or "")
    cleaned = re.sub(r"(?im)^\s*[*-]?\s*生成时间[:：].*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    footer = (
        "\n\n---\n"
        f"*报告生成时间：{generated_at}*\n"
        "*数据来源：上传图像、皮肤病分类模型结果与大模型辅助分析*"
    )
    return cleaned + footer


def _fallback_report(prediction: dict, top_predictions: List[dict], basic_tips: str, reason: str) -> str:
    class_name = prediction.get("predicted_class_name", "未知类别")
    confidence = prediction.get("confidence_percent", "未知")
    top_text = _format_scores(top_predictions)
    return (
        f"{reason}，当前先返回本地增强解读。\n\n"
        f"1. 模型结果解释：小样本分类模型倾向于“{class_name}”，置信度为 {confidence}。"
        "置信度越低，越需要结合病史、查体和必要检查复核。\n"
        f"2. Top预测参考：{top_text}。\n"
        f"3. 初步建议：{basic_tips}\n"
        "4. 风险提醒：若皮损快速扩大、颜色明显不均、破溃出血、疼痛加重，或伴发热等全身症状，"
        "请尽快到皮肤科就诊。该结果仅供辅助参考，不能替代医生诊断。"
        f"\n\n---\n*报告生成时间：{timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}*"
        "\n*数据来源：上传图像、皮肤病分类模型结果与本地增强分析*"
    )
