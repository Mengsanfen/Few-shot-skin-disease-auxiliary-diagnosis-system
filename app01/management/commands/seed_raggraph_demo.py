from __future__ import annotations

from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from app01.models import KnowledgeChunk, KnowledgeDocument, KnowledgeEntity, KnowledgeRelation, MedicalKnowledge


@dataclass(frozen=True)
class DiseaseSeed:
    name: str
    category: str
    symptoms: tuple[str, ...]
    morphology: tuple[str, ...]
    body_parts: tuple[str, ...]
    triggers: tuple[str, ...]
    checks: tuple[str, ...]
    risks: tuple[str, ...]
    care: tuple[str, ...]
    differential: tuple[str, ...] = ()


DISEASES: tuple[DiseaseSeed, ...] = (
    DiseaseSeed(
        name="湿疹",
        category="炎症性皮肤病",
        symptoms=("瘙痒", "红斑", "渗出", "干燥脱屑", "反复发作"),
        morphology=("丘疹", "小水疱", "抓痕", "苔藓样变"),
        body_parts=("手背", "肘窝", "面部", "躯干"),
        triggers=("皮肤屏障受损", "过敏体质", "刺激物接触", "气候干燥"),
        checks=("皮肤科查体", "斑贴试验", "真菌镜检", "过敏原筛查"),
        risks=("渗出加重", "继发感染", "夜间瘙痒明显"),
        care=("规律保湿修复屏障", "避免搔抓和热水烫洗", "记录诱因并减少接触"),
        differential=("银屑病", "接触性皮炎", "体癣"),
    ),
    DiseaseSeed(
        name="银屑病",
        category="免疫相关鳞屑性疾病",
        symptoms=("边界清楚红色斑块", "银白色鳞屑", "轻中度瘙痒", "反复迁延"),
        morphology=("斑块", "鳞屑", "点状出血征", "甲凹点"),
        body_parts=("头皮", "肘部", "膝部", "骶尾部"),
        triggers=("感染后诱发", "精神压力", "皮肤外伤", "季节变化"),
        checks=("皮肤镜检查", "皮肤科查体", "必要时皮肤活检", "关节症状评估"),
        risks=("关节疼痛", "大面积皮损", "脓疱或红皮病表现"),
        care=("避免自行长期使用强效药", "保持皮肤湿润", "规律复诊评估控制程度"),
        differential=("湿疹", "脂溢性皮炎", "体癣"),
    ),
    DiseaseSeed(
        name="痤疮",
        category="毛囊皮脂腺疾病",
        symptoms=("粉刺", "炎性丘疹", "脓疱", "结节", "痘印"),
        morphology=("闭口粉刺", "丘疹", "脓疱", "炎性结节"),
        body_parts=("面部", "胸背部", "下颌缘"),
        triggers=("皮脂分泌旺盛", "毛囊堵塞", "高糖饮食", "熬夜压力"),
        checks=("皮肤科查体", "严重痤疮分级", "女性内分泌评估"),
        risks=("瘢痕形成", "疼痛性结节", "反复化脓"),
        care=("温和清洁", "避免挤压", "降低高糖高油饮食", "防晒减少色沉"),
        differential=("玫瑰痤疮", "毛囊炎", "脂溢性皮炎"),
    ),
    DiseaseSeed(
        name="白癜风",
        category="色素脱失性疾病",
        symptoms=("边界较清楚白斑", "色素脱失", "表面光滑", "可逐渐扩大"),
        morphology=("瓷白色斑片", "色素脱失斑", "毛发变白"),
        body_parts=("面部", "手背", "颈部", "躯干"),
        triggers=("自身免疫相关", "皮肤摩擦", "日晒刺激", "精神压力"),
        checks=("伍德灯检查", "皮肤镜检查", "甲状腺功能评估", "自身免疫指标评估"),
        risks=("短期扩大", "暴露部位明显", "心理压力增加"),
        care=("规律防晒", "避免刺激性偏方", "早期皮肤科评估", "做好心理支持"),
        differential=("花斑癣", "炎症后色素减退", "无色素痣"),
    ),
    DiseaseSeed(
        name="荨麻疹",
        category="过敏反应相关疾病",
        symptoms=("风团", "突发瘙痒", "此起彼伏", "数小时内消退"),
        morphology=("水肿性风团", "地图样红斑", "皮肤划痕征"),
        body_parts=("躯干", "四肢", "面部", "眼睑口唇"),
        triggers=("食物药物过敏", "感染诱发", "冷热刺激", "运动出汗"),
        checks=("过敏史追问", "血常规", "感染指标评估", "慢性荨麻疹诱因筛查"),
        risks=("喉头水肿", "呼吸困难", "胸闷头晕", "血压下降"),
        care=("记录可疑诱因", "避免已知过敏原", "急性严重反应及时就医"),
        differential=("药疹", "接触性皮炎", "血管性水肿"),
    ),
    DiseaseSeed(
        name="接触性皮炎",
        category="外源刺激/过敏性炎症",
        symptoms=("接触部位红斑", "灼热瘙痒", "水疱", "边界与接触区域相关"),
        morphology=("红斑", "水疱", "糜烂渗出", "脱屑"),
        body_parts=("手部", "面颈部", "前臂", "接触区域"),
        triggers=("化妆品接触", "清洁剂刺激", "金属饰品", "外用药物"),
        checks=("接触史追问", "斑贴试验", "皮肤科查体"),
        risks=("范围扩大", "渗出明显", "继发感染"),
        care=("停止可疑接触物", "温和清洁", "屏障修复", "必要时专科处理"),
        differential=("湿疹", "荨麻疹", "体癣"),
    ),
    DiseaseSeed(
        name="脂溢性皮炎",
        category="皮脂溢出相关炎症",
        symptoms=("油腻性鳞屑", "红斑", "瘙痒", "反复脱屑"),
        morphology=("油腻鳞屑", "淡红斑片", "头皮屑增多"),
        body_parts=("头皮", "鼻唇沟", "眉间", "胸前"),
        triggers=("皮脂分泌旺盛", "马拉色菌相关", "熬夜压力", "季节变化"),
        checks=("皮肤科查体", "真菌相关评估", "严重程度分级"),
        risks=("反复发作", "头皮瘙痒明显", "继发抓破"),
        care=("规律清洁头皮", "减少熬夜压力", "避免厚重油性护肤"),
        differential=("银屑病", "湿疹", "玫瑰痤疮"),
    ),
    DiseaseSeed(
        name="毛囊炎",
        category="毛囊感染/炎症",
        symptoms=("毛囊周围红丘疹", "脓疱", "疼痛", "局部压痛"),
        morphology=("针尖至米粒大脓疱", "炎性丘疹", "结痂"),
        body_parts=("头皮", "胸背部", "臀部", "大腿"),
        triggers=("出汗摩擦", "细菌感染", "油脂堵塞", "免疫状态下降"),
        checks=("皮肤科查体", "脓液细菌培养", "复发者血糖评估"),
        risks=("疼痛加重", "脓肿形成", "范围快速扩大"),
        care=("保持局部清洁干燥", "避免挤压", "减少摩擦闷热"),
        differential=("痤疮", "疖肿", "虫咬皮炎"),
    ),
    DiseaseSeed(
        name="带状疱疹",
        category="病毒感染性皮肤病",
        symptoms=("单侧带状疼痛", "成簇水疱", "灼痛", "触痛"),
        morphology=("群集性水疱", "红斑基础", "结痂"),
        body_parts=("胸背部", "腰腹部", "面部三叉神经区"),
        triggers=("水痘-带状疱疹病毒再激活", "免疫力下降", "疲劳压力"),
        checks=("皮肤科查体", "神经痛评估", "眼部受累评估"),
        risks=("眼周皮损", "剧烈神经痛", "免疫低下患者", "皮损泛发"),
        care=("尽早就医评估抗病毒治疗窗口", "避免抓破水疱", "保护皮损区域"),
        differential=("单纯疱疹", "接触性皮炎", "虫咬皮炎"),
    ),
    DiseaseSeed(
        name="玫瑰痤疮",
        category="面部慢性炎症性疾病",
        symptoms=("面部潮红", "灼热刺痛", "丘疹脓疱", "毛细血管扩张"),
        morphology=("持久性红斑", "丘疹脓疱", "血管扩张"),
        body_parts=("面颊", "鼻部", "额部", "下颌"),
        triggers=("日晒", "辛辣饮食", "酒精", "冷热刺激", "情绪压力"),
        checks=("皮肤科查体", "蠕形螨相关评估", "诱因评估"),
        risks=("眼部不适", "鼻赘样改变", "灼热持续"),
        care=("严格防晒", "减少辛辣酒精", "选择低刺激护肤", "避免过度清洁"),
        differential=("痤疮", "脂溢性皮炎", "激素依赖性皮炎"),
    ),
    DiseaseSeed(
        name="体癣",
        category="真菌感染性皮肤病",
        symptoms=("环形红斑", "边缘隆起", "脱屑", "瘙痒"),
        morphology=("环形斑片", "活动性边缘", "中央趋于消退"),
        body_parts=("躯干", "四肢", "腹股沟周围"),
        triggers=("皮肤癣菌感染", "潮湿闷热", "接触感染源", "共用毛巾衣物"),
        checks=("真菌镜检", "真菌培养", "皮肤科查体"),
        risks=("面积扩大", "反复传染", "误用激素后加重"),
        care=("保持干燥", "避免共用贴身物品", "规范抗真菌处理", "清洁衣物床品"),
        differential=("湿疹", "银屑病", "玫瑰糠疹"),
    ),
    DiseaseSeed(
        name="黑色素瘤警示",
        category="皮肤肿瘤风险信号",
        symptoms=("色素痣不对称", "边界不规则", "颜色不均", "短期增大", "破溃出血"),
        morphology=("不规则色素斑", "多色性皮损", "结节样隆起"),
        body_parts=("足底", "甲下", "躯干", "既有色素痣区域"),
        triggers=("紫外线暴露", "既往色素痣变化", "家族史", "反复摩擦"),
        checks=("皮肤镜检查", "ABCDE风险评估", "病理活检", "专科转诊"),
        risks=("快速增大", "破溃出血", "边界不规则", "颜色明显改变"),
        care=("尽快皮肤科或肿瘤相关专科评估", "保留变化照片", "避免自行处理色素痣"),
        differential=("普通色素痣", "脂溢性角化", "血管瘤"),
    ),
)


RELATION_MAP = {
    "symptoms": ("HAS_SYMPTOM", "symptom"),
    "morphology": ("HAS_MORPHOLOGY", "morphology"),
    "body_parts": ("LOCATED_AT", "body_part"),
    "triggers": ("TRIGGERED_BY", "trigger"),
    "checks": ("NEEDS_CHECK", "check"),
    "risks": ("RISK_SIGNAL", "risk"),
    "care": ("SUGGESTS_CARE", "care"),
    "differential": ("DIFFERENTIAL_WITH", "disease"),
}


class Command(BaseCommand):
    help = "Seed enterprise RAGGraph demo data for DermoAI."

    def handle(self, *args, **options):
        created_entries = 0
        created_entities = 0
        created_relations = 0

        for disease in DISEASES:
            entry, created = MedicalKnowledge.objects.update_or_create(
                disease=disease.name,
                defaults={
                    "symptoms": "；".join((*disease.symptoms, *disease.morphology, *disease.body_parts)),
                    "check_items": "；".join(disease.checks),
                    "advice": "；".join((*disease.care, "若出现危险信号或症状快速进展，应优先线下就医。")),
                },
            )
            created_entries += int(created)

            disease_entity, entity_created = self._entity(
                disease.name,
                "disease",
                f"{disease.category}；RAGGraph 中作为候选诊断主题参与全局关系扩展。",
                0.96,
            )
            created_entities += int(entity_created)

            for field_name, (relation_type, entity_type) in RELATION_MAP.items():
                for item in getattr(disease, field_name):
                    target, entity_created = self._entity(
                        item,
                        entity_type,
                        f"{disease.name} 相关{self._type_label(entity_type)}：{item}",
                        0.9 if field_name != "differential" else 0.84,
                    )
                    created_entities += int(entity_created)
                    relation, relation_created = KnowledgeRelation.objects.update_or_create(
                        subject=disease_entity,
                        relation_type=relation_type,
                        object=target,
                        evidence_source="DermoAI RAGGraph Demo Corpus",
                        defaults={
                            "weight": self._weight(field_name),
                            "evidence_text": self._evidence_text(disease.name, relation_type, item),
                            "source_type": "structured_seed",
                            "page_label": "SeedGraph",
                        },
                    )
                    created_relations += int(relation_created)

            self._ensure_case_document(disease, entry)

        self.stdout.write(
            self.style.SUCCESS(
                "RAGGraph demo data ready: "
                f"{MedicalKnowledge.objects.count()} knowledge entries, "
                f"{KnowledgeEntity.objects.count()} entities, "
                f"{KnowledgeRelation.objects.count()} relations. "
                f"Created this run: {created_entries} entries, {created_entities} entities, {created_relations} relations."
            )
        )

    def _entity(self, name: str, entity_type: str, description: str, confidence: float):
        return KnowledgeEntity.objects.update_or_create(
            normalized_name=self._normalize(name),
            entity_type=entity_type,
            defaults={
                "name": name,
                "description": description,
                "source": "dermoai_seed_graph",
                "confidence": confidence,
            },
        )

    def _ensure_case_document(self, disease: DiseaseSeed, entry: MedicalKnowledge) -> None:
        title = f"{disease.name} RAGGraph 临床知识卡"
        content = (
            f"{disease.name} 属于{disease.category}。典型表现包括：{'、'.join(disease.symptoms)}。"
            f"皮损形态可见：{'、'.join(disease.morphology)}。常见部位包括：{'、'.join(disease.body_parts)}。"
            f"推荐检查：{'、'.join(disease.checks)}。护理与处置建议：{'、'.join(disease.care)}。"
            f"需要警惕：{'、'.join(disease.risks)}。"
        )
        document, created = KnowledgeDocument.objects.get_or_create(
            title=title,
            defaults={
                "file_type": "txt",
                "chunk_strategy": "raggraph_seed",
                "status": "ready",
                "total_chars": len(content),
                "total_chunks": 1,
            },
        )
        if created:
            document.file.save(f"{self._normalize(disease.name)}_raggraph_seed.txt", ContentFile(content.encode("utf-8")))
        else:
            document.total_chars = len(content)
            document.total_chunks = 1
            document.status = "ready"
            document.chunk_strategy = "raggraph_seed"
            document.save(update_fields=["total_chars", "total_chunks", "status", "chunk_strategy", "updated_at"])

        KnowledgeChunk.objects.update_or_create(
            document=document,
            chunk_index=0,
            defaults={
                "page_label": "知识卡",
                "content": content,
                "token_estimate": max(1, len(content) // 2),
                "start_offset": 0,
                "end_offset": len(content),
            },
        )

    def _evidence_text(self, disease: str, relation_type: str, target: str) -> str:
        label = {
            "HAS_SYMPTOM": "典型症状",
            "HAS_MORPHOLOGY": "皮损形态",
            "LOCATED_AT": "常见部位",
            "TRIGGERED_BY": "相关诱因",
            "NEEDS_CHECK": "建议检查",
            "RISK_SIGNAL": "危险信号",
            "SUGGESTS_CARE": "护理建议",
            "DIFFERENTIAL_WITH": "鉴别诊断",
        }.get(relation_type, "关联证据")
        return f"{disease} 与「{target}」存在「{label}」关系，可作为 RAGGraph 检索和解释路径的结构化证据。"

    def _type_label(self, entity_type: str) -> str:
        return {
            "symptom": "症状",
            "morphology": "皮损形态",
            "body_part": "部位",
            "trigger": "诱因",
            "check": "检查",
            "risk": "风险信号",
            "care": "护理建议",
            "disease": "疾病",
        }.get(entity_type, "实体")

    def _weight(self, field_name: str) -> float:
        return {
            "symptoms": 0.95,
            "morphology": 0.9,
            "body_parts": 0.78,
            "triggers": 0.72,
            "checks": 0.86,
            "risks": 0.98,
            "care": 0.74,
            "differential": 0.68,
        }[field_name]

    def _normalize(self, value: str) -> str:
        return "".join(str(value).split()).lower()[:120]
