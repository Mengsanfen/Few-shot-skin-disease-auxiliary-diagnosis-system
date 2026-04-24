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


class KnowledgeEntity(models.Model):
    """医学知识图谱实体。"""

    ENTITY_TYPES = (
        ("disease", "疾病/主题"),
        ("symptom", "症状"),
        ("body_part", "部位"),
        ("morphology", "皮损形态"),
        ("trigger", "诱因"),
        ("check", "检查"),
        ("risk", "风险信号"),
        ("care", "护理建议"),
        ("evidence", "证据来源"),
    )

    name = models.CharField("实体名称", max_length=120)
    normalized_name = models.CharField("标准化名称", max_length=140, db_index=True)
    entity_type = models.CharField("实体类型", max_length=30, choices=ENTITY_TYPES, db_index=True)
    description = models.TextField("实体描述", blank=True, default="")
    source = models.CharField("来源", max_length=80, blank=True, default="rag_graph")
    confidence = models.FloatField("实体置信度", default=0.8)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["entity_type", "name"]
        verbose_name = "医学图谱实体"
        verbose_name_plural = "医学图谱实体"
        constraints = [
            models.UniqueConstraint(
                fields=["normalized_name", "entity_type"],
                name="unique_knowledge_entity_type_name",
            )
        ]

    def __str__(self):
        return f"{self.get_entity_type_display()}：{self.name}"


class KnowledgeRelation(models.Model):
    """医学知识图谱关系，保留证据来源与关系权重。"""

    RELATION_TYPES = (
        ("HAS_SYMPTOM", "具有症状"),
        ("LOCATED_AT", "发生部位"),
        ("HAS_MORPHOLOGY", "皮损形态"),
        ("TRIGGERED_BY", "相关诱因"),
        ("NEEDS_CHECK", "建议检查"),
        ("RISK_SIGNAL", "风险信号"),
        ("SUGGESTS_CARE", "护理建议"),
        ("EVIDENCED_BY", "证据来源"),
        ("DIFFERENTIAL_WITH", "鉴别诊断"),
    )

    subject = models.ForeignKey(
        KnowledgeEntity,
        verbose_name="主体实体",
        on_delete=models.CASCADE,
        related_name="outgoing_relations",
    )
    relation_type = models.CharField("关系类型", max_length=40, choices=RELATION_TYPES, db_index=True)
    object = models.ForeignKey(
        KnowledgeEntity,
        verbose_name="客体实体",
        on_delete=models.CASCADE,
        related_name="incoming_relations",
    )
    weight = models.FloatField("关系权重", default=1.0)
    evidence_text = models.TextField("证据文本", blank=True, default="")
    evidence_source = models.CharField("证据来源", max_length=160, blank=True, default="")
    source_type = models.CharField("来源类型", max_length=40, blank=True, default="structured")
    page_label = models.CharField("页码标签", max_length=40, blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["-weight", "relation_type"]
        verbose_name = "医学图谱关系"
        verbose_name_plural = "医学图谱关系"
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "relation_type", "object", "evidence_source"],
                name="unique_knowledge_relation_evidence",
            )
        ]

    def __str__(self):
        return f"{self.subject.name} -{self.get_relation_type_display()}-> {self.object.name}"


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
    graph_payload = models.JSONField("RAGGraph结构化结果", default=dict, blank=True)
    model_used = models.CharField("使用模型", max_length=80, blank=True, default="")
    created_at = models.DateTimeField("发送时间", auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "智能问诊消息"
        verbose_name_plural = "智能问诊消息"

    def __str__(self):
        return f"{self.get_role_display()} - {self.created_at:%Y-%m-%d %H:%M}"
