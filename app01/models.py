from django.conf import settings
from django.db import models
from django.db.models import Q

class MedicalKnowledge(models.Model):
    disease = models.CharField("疾病名称", max_length=100)
    symptoms = models.TextField("典型症状")
    check_items = models.TextField("建议检查")
    advice = models.TextField("处理建议")

    def __str__(self):
        return self.disease

    @classmethod
    def search(cls, symptoms):
        keywords = [word.strip() for word in symptoms.split(',') if word.strip()]
        query = Q()
        for kw in keywords:
            query |= Q(symptoms__icontains=kw)
        return cls.objects.filter(query).order_by('-id')[:3]


def knowledge_document_upload_to(instance, filename):
    return f"knowledge_docs/{filename}"


class KnowledgeDocument(models.Model):
    title = models.CharField("文档标题", max_length=160)
    file = models.FileField("原始文件", upload_to=knowledge_document_upload_to)
    file_type = models.CharField("文件类型", max_length=20, default="txt")
    chunk_strategy = models.CharField("切片策略", max_length=80, default="medical_recursive")
    status = models.CharField("处理状态", max_length=20, default="ready")
    total_chars = models.PositiveIntegerField("总字符数", default=0)
    total_chunks = models.PositiveIntegerField("切片数量", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "知识库文档"
        verbose_name_plural = "知识库文档"

    def __str__(self):
        return self.title


class KnowledgeChunk(models.Model):
    document = models.ForeignKey(
        KnowledgeDocument,
        verbose_name="所属文档",
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField("分块序号")
    page_label = models.CharField("页码标签", max_length=40, blank=True, default="")
    content = models.TextField("切片内容")
    token_estimate = models.PositiveIntegerField("估计 token 数", default=0)
    start_offset = models.PositiveIntegerField("起始位置", default=0)
    end_offset = models.PositiveIntegerField("结束位置", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]
        verbose_name = "知识切片"
        verbose_name_plural = "知识切片"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="unique_document_chunk_index",
            )
        ]

    def __str__(self):
        return f"{self.document.title}#{self.chunk_index}"


class DiagnosisConversation(models.Model):
    """皮肤病智能问诊会话。"""

    title = models.CharField("会话标题", max_length=120, default="新的皮肤问诊")
    session_key = models.CharField("会话标识", max_length=80, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="diagnosis_conversations",
    )
    summary = models.TextField("上下文摘要", blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "智能问诊会话"
        verbose_name_plural = "智能问诊会话"

    def __str__(self):
        return self.title


class DiagnosisMessage(models.Model):
    """皮肤病问诊消息记录，保存 RAG 证据与知识图谱路径。"""

    ROLE_CHOICES = (
        ("user", "用户"),
        ("assistant", "AI助手"),
    )

    conversation = models.ForeignKey(
        DiagnosisConversation,
        verbose_name="所属会话",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField("角色", max_length=20, choices=ROLE_CHOICES)
    content = models.TextField("消息内容")
    references = models.JSONField("RAG参考", default=list, blank=True)
    graph_paths = models.JSONField("知识图谱路径", default=list, blank=True)
    model_used = models.CharField("使用模型", max_length=80, blank=True, default="")
    created_at = models.DateTimeField("发送时间", auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "智能问诊消息"
        verbose_name_plural = "智能问诊消息"

    def __str__(self):
        return f"{self.get_role_display()} - {self.created_at:%Y-%m-%d %H:%M}"
