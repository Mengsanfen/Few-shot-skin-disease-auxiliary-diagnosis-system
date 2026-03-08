"""
SFEPT (Semantic Feature Enhanced Prototypical Transformer) 推理封装模块

该模块提供 SkinFSLPredictor 单例类，用于皮肤病小样本图像分类推理。

核心流程：
1. 初始化时加载模型权重和计算支持集原型
2. 推理时对输入图像进行特征提取、原型修正、语义增强、距离计算
"""

import os
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms

# 添加 FSL_skin 项目路径到 sys.path
FSL_SKIN_PATH = Path("D:/AI/FSL_skin")
if str(FSL_SKIN_PATH) not in sys.path:
    sys.path.insert(0, str(FSL_SKIN_PATH))

# 导入 SFEPT 相关模块
try:
    import timm
    from transformers import BertTokenizer, BertModel
    from easyfsl.methods.utils import compute_prototypes
except ImportError as e:
    raise ImportError(f"请确保安装了所需依赖: timm, transformers。错误: {e}")


# ============================================================================
# SFEPT 模型组件定义
# ============================================================================

class VectorDecoder(nn.Module):
    """
    向量解码器：使用冻结的 BERT 进行语义特征增强
    将输入向量解码为 BERT 嵌入表示
    """
    def __init__(self, input_dim: int = 768, bert_dim: int = 768):
        super(VectorDecoder, self).__init__()
        self.fc = nn.Linear(input_dim, bert_dim)
        # 加载预训练的 BERT 模型和分词器
        self.tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
        self.bert_model = BertModel.from_pretrained("bert-base-uncased")
        # 冻结 BERT 参数
        for param in self.bert_model.parameters():
            param.requires_grad = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded_input = self.fc(x).unsqueeze(1)
        with torch.no_grad():
            bert_output = self.bert_model(inputs_embeds=encoded_input)
        return bert_output.last_hidden_state.squeeze(1)


class S2PInference(nn.Module):
    """
    S2P (Similarity-to-Prototype) 推理模型

    包含:
    - Swin Transformer 特征提取器
    - Bias Diminishing 原型修正策略
    - BERT 语义增强模块
    """
    def __init__(
        self,
        backbone: nn.Module,
        use_softmax: bool = True,
        feature_normalization: Optional[float] = None,
    ):
        super().__init__()
        self.backbone = backbone
        self.use_softmax = use_softmax
        self.feature_normalization = feature_normalization
        self.feature_centering = torch.tensor(0.0)

        # 原型和支持集存储
        self.prototypes = torch.tensor(())
        self.support_features = torch.tensor(())
        self.support_labels = torch.tensor(())

        # BERT 语义增强模块
        self.text_decoder = VectorDecoder()

    def compute_features(self, images: torch.Tensor) -> torch.Tensor:
        """提取图像特征并进行归一化"""
        features = self.backbone(images)
        centered_features = features - self.feature_centering.to(features.device)
        if self.feature_normalization is not None:
            centered_features = nn.functional.normalize(
                centered_features, p=self.feature_normalization, dim=1
            )
        return centered_features

    def rectify_prototypes(self, query_features: torch.Tensor):
        """
        Bias Diminishing 原型修正策略

        通过计算支持集和查询集的平均特征偏移，修正原型表示
        """
        n_classes = self.support_labels.unique().size(0)
        one_hot_support_labels = nn.functional.one_hot(self.support_labels, n_classes)

        # 计算支持集和查询集的平均特征差
        average_support_query_shift = (
            self.support_features.mean(0, keepdim=True)
            - query_features.mean(0, keepdim=True)
        )
        query_features_shifted = query_features + average_support_query_shift

        # 计算余弦距离
        support_logits = self.cosine_distance_to_prototypes(self.support_features).exp()
        query_logits = self.cosine_distance_to_prototypes(query_features_shifted).exp()

        # 构建归一化向量
        one_hot_query_prediction = nn.functional.one_hot(
            query_logits.argmax(-1), n_classes
        )

        normalization_vector = (
            (one_hot_support_labels * support_logits).sum(0)
            + (one_hot_query_prediction * query_logits).sum(0)
        ).unsqueeze(0)

        support_reweighting = (
            one_hot_support_labels * support_logits
        ) / normalization_vector
        query_reweighting = (
            one_hot_query_prediction * query_logits
        ) / normalization_vector

        # 更新原型
        self.prototypes = (
            (support_reweighting * one_hot_support_labels).t().matmul(self.support_features)
            + (query_reweighting * one_hot_query_prediction).t().matmul(query_features_shifted)
        )

    def cosine_distance_to_prototypes(self, samples: torch.Tensor) -> torch.Tensor:
        """计算样本到原型的余弦距离"""
        return (
            nn.functional.normalize(samples, dim=1)
            @ nn.functional.normalize(self.prototypes, dim=1).T
        )

    def l2_distance_to_prototypes(self, samples: torch.Tensor) -> torch.Tensor:
        """计算样本到原型的欧氏距离"""
        return -torch.cdist(samples, self.prototypes)

    def process_support_set(
        self,
        support_images: torch.Tensor,
        support_labels: torch.Tensor,
    ):
        """处理支持集，计算原型"""
        self.support_labels = support_labels
        self.support_features = self.compute_features(support_images)
        self.prototypes = compute_prototypes(self.support_features, support_labels)

    def forward(self, query_images: torch.Tensor) -> torch.Tensor:
        """
        推理流程：
        1. 特征提取 (Swin Transformer → 768维)
        2. Bias Diminishing 原型修正
        3. [BERT 语义增强 - 暂时禁用]
        4. L2 距离计算
        """
        # 提取查询图像特征
        query_features = self.compute_features(query_images)

        # Bias Diminishing 原型修正
        self.rectify_prototypes(query_features)

        # [BERT 语义增强 - 暂时禁用]
        # semantic_features = self.text_decoder(query_features)
        # enhanced_features = semantic_features + query_features
        enhanced_features = query_features  # 直接使用原始特征，通道数保持 768 维

        # 计算 L2 距离
        scores = self.l2_distance_to_prototypes(enhanced_features)

        if self.use_softmax:
            scores = scores.softmax(-1)

        return scores


# ============================================================================
# 单例预测器类
# ============================================================================

class SkinFSLPredictor:
    """
    皮肤病小样本分类预测器（单例模式）

    在 Django 启动时初始化一次，加载模型和计算支持集原型。
    提供 predict 方法进行单张图像推理。

    使用示例：
        predictor = SkinFSLPredictor.get_instance()
        result = predictor.predict(image)
    """

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        model_path: str = None,
        support_set_dir: str = None,
        class_names: List[str] = None,
        device: str = "cuda",
        image_size: int = 224,
    ):
        """
        初始化预测器

        Args:
            model_path: 模型权重文件路径
            support_set_dir: 支持集图像目录
            class_names: 类别名称列表
            device: 运行设备
            image_size: 输入图像大小
        """
        # 避免重复初始化
        if SkinFSLPredictor._initialized:
            return

        self.device = device if torch.cuda.is_available() else "cpu"
        self.image_size = image_size

        # 默认路径配置
        self.model_path = model_path or str(FSL_SKIN_PATH / "checkpoints" / "best_swin_model.pth")
        self.support_set_dir = support_set_dir or str(FSL_SKIN_PATH / "data" / "CUB")

        # 默认类别名称（可根据实际数据集配置）
        self.class_names = class_names or self._load_class_names()

        print(f"[SkinFSLPredictor] 初始化中...")
        print(f"[SkinFSLPredictor] 设备: {self.device}")
        print(f"[SkinFSLPredictor] 模型路径: {self.model_path}")

        # 图像预处理
        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

        # 加载模型
        self.model = self._load_model()

        # 加载支持集并计算原型
        self._load_support_set()

        SkinFSLPredictor._initialized = True
        print(f"[SkinFSLPredictor] 初始化完成！共 {len(self.class_names)} 个类别")

    def _load_class_names(self) -> List[str]:
        """从配置文件加载类别名称"""
        import json
        config_path = FSL_SKIN_PATH / "data" / "CUB" / "test.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("class_names", [])
        return []

    def _load_model(self) -> S2PInference:
        """加载 SFEPT 模型"""
        print("[SkinFSLPredictor] 加载 Swin Transformer...")

        # 创建 Swin Transformer 骨干网络
        backbone = timm.create_model(
            'swin_base_patch4_window7_224',
            pretrained=False  # 我们会加载自己的权重
        )
        # 修改输出维度
        backbone.head.fc = nn.Linear(in_features=1024, out_features=768, bias=True)

        # 创建 S2P 模型
        model = S2PInference(
            backbone=backbone,
            use_softmax=True,
            feature_normalization=None,
        )

        # 加载训练好的权重
        if os.path.exists(self.model_path):
            print(f"[SkinFSLPredictor] 加载模型权重: {self.model_path}")
            state_dict = torch.load(self.model_path, map_location=self.device)
            model.load_state_dict(state_dict)
        else:
            print(f"[SkinFSLPredictor] 警告: 模型文件不存在 {self.model_path}")

        model = model.to(self.device)
        model.eval()

        return model

    def _load_support_set(self):
        """
        加载支持集图像并计算原型

        这里使用测试集配置中的每个类别的代表性图像作为支持集
        """
        print("[SkinFSLPredictor] 加载支持集...")

        support_images = []
        support_labels = []

        # 从配置文件读取支持集路径
        import json
        config_path = FSL_SKIN_PATH / "data" / "CUB" / "test.json"

        if not config_path.exists():
            print(f"[SkinFSLPredictor] 警告: 配置文件不存在 {config_path}")
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        class_roots = config.get("class_roots", [])

        for label, class_root in enumerate(class_roots):
            # 构建完整路径
            class_path = FSL_SKIN_PATH / class_root.lstrip("./")

            if not class_path.exists():
                continue

            # 获取该类别的前几张图像作为支持集样本
            image_files = list(class_path.glob("*.[jJ][pP][gG]")) + \
                         list(class_path.glob("*.[pP][nN][gG]")) + \
                         list(class_path.glob("*.[jJ][pP][eE][gG]"))

            # 每个类别取 n_shot 张图像
            n_shot = 5
            for img_path in image_files[:n_shot]:
                try:
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = self.transform(img)
                    support_images.append(img_tensor)
                    support_labels.append(label)
                except Exception as e:
                    print(f"[SkinFSLPredictor] 警告: 无法加载图像 {img_path}: {e}")

        if not support_images:
            print("[SkinFSLPredictor] 警告: 未找到支持集图像")
            return

        # 转换为张量
        support_images = torch.stack(support_images).to(self.device)
        support_labels = torch.tensor(support_labels).to(self.device)

        print(f"[SkinFSLPredictor] 支持集大小: {len(support_images)} 张图像")

        # 计算原型
        with torch.no_grad():
            self.model.process_support_set(support_images, support_labels)

        print("[SkinFSLPredictor] 原型计算完成")

    def predict(
        self,
        image: Union[Image.Image, np.ndarray, torch.Tensor],
        return_all_scores: bool = False,
    ) -> Dict:
        """
        对单张图像进行预测

        Args:
            image: 输入图像，支持 PIL Image、numpy 数组或 torch Tensor
            return_all_scores: 是否返回所有类别的分数

        Returns:
            dict: 包含预测结果的字典
                - predicted_class: 预测类别索引
                - predicted_class_name: 预测类别名称
                - confidence: 预测置信度
                - all_scores: 所有类别分数（可选）
        """
        # 图像预处理
        if isinstance(image, Image.Image):
            image = image.convert('RGB')
            image_tensor = self.transform(image).unsqueeze(0)
        elif isinstance(image, np.ndarray):
            image = Image.fromarray(image).convert('RGB')
            image_tensor = self.transform(image).unsqueeze(0)
        elif isinstance(image, torch.Tensor):
            if image.dim() == 3:
                image_tensor = image.unsqueeze(0)
            else:
                image_tensor = image
        else:
            raise ValueError(f"不支持的图像类型: {type(image)}")

        image_tensor = image_tensor.to(self.device)

        # 推理
        with torch.no_grad():
            scores = self.model(image_tensor)

        # 获取预测结果
        predicted_class = scores.argmax(dim=1).item()
        confidence = scores[0, predicted_class].item()

        result = {
            "predicted_class": predicted_class,
            "predicted_class_name": (
                self.class_names[predicted_class]
                if predicted_class < len(self.class_names) else f"Class_{predicted_class}"
            ),
            "confidence": confidence,
        }

        if return_all_scores:
            result["all_scores"] = {
                self.class_names[i] if i < len(self.class_names) else f"Class_{i}": scores[0, i].item()
                for i in range(scores.size(1))
            }

        return result

    def predict_batch(
        self,
        images: List[Union[Image.Image, np.ndarray, torch.Tensor]],
    ) -> List[Dict]:
        """
        批量预测多张图像

        Args:
            images: 图像列表

        Returns:
            list: 预测结果列表
        """
        results = []
        for image in images:
            result = self.predict(image)
            results.append(result)
        return results


# ============================================================================
# 便捷函数
# ============================================================================

def get_predictor() -> SkinFSLPredictor:
    """
    获取全局预测器实例

    Returns:
        SkinFSLPredictor: 单例预测器实例
    """
    return SkinFSLPredictor.get_instance()


def predict_skin_disease(
    image: Union[Image.Image, np.ndarray],
    return_all_scores: bool = False,
) -> Dict:
    """
    便捷函数：预测皮肤病类别

    Args:
        image: 输入图像
        return_all_scores: 是否返回所有类别分数

    Returns:
        dict: 预测结果
    """
    predictor = get_predictor()
    return predictor.predict(image, return_all_scores)


# ============================================================================
# Django 应用就绪时自动初始化
# ============================================================================

def init_predictor():
    """初始化预测器（在 Django 启动时调用）"""
    try:
        SkinFSLPredictor.get_instance()
    except Exception as e:
        print(f"[SkinFSLPredictor] 初始化失败: {e}")


if __name__ == "__main__":
    # 测试代码
    predictor = SkinFSLPredictor.get_instance()
    print(f"模型已加载，共 {len(predictor.class_names)} 个类别")