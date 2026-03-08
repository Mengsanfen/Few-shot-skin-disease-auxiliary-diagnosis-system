"""
皮肤病图像分类视图模块

包含:
- SFEPT 算法页面展示
- 皮肤病图像上传和预测接口
"""

import base64
import io
import logging
import random

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from PIL import Image

from app01.utils.utils import del_filedir

# 配置日志
logger = logging.getLogger(__name__)

# ============================================================================
# 全局预测器实例（单例模式）
# ============================================================================
_predictor = None

def get_predictor():
    """
    获取皮肤病预测器实例（延迟加载）

    Returns:
        SkinFSLPredictor: 预测器实例
    """
    global _predictor
    if _predictor is None:
        try:
            from app01.ai_core import SkinFSLPredictor
            _predictor = SkinFSLPredictor.get_instance()
            logger.info("[Views] SkinFSLPredictor 初始化成功")
        except Exception as e:
            logger.error(f"[Views] SkinFSLPredictor 初始化失败: {e}")
            raise
    return _predictor


# ============================================================================
# 页面视图
# ============================================================================

def lungkonw(request):
    """SFEPT 算法架构解析页面"""
    return render(request, 'lungKonw.html')


def skin_disease_index(request):
    """皮肤病图像分类系统首页"""
    return render(request, 'lung_index.html')


# 保留旧路由兼容性
def lung_index(request):
    """兼容旧路由"""
    return skin_disease_index(request)


# ============================================================================
# 图像上传和预测接口
# ============================================================================

@csrf_exempt
def skin_disease_upload(request):
    """
    上传皮肤病图像

    POST 请求:
        - uploadImage: 图像文件

    Returns:
        JsonResponse: {'status': True/False, 'message': '...'}
    """
    if request.method == 'GET':
        return render(request, "lung_index.html")

    try:
        file_object = request.FILES.get('uploadImage')
        if not file_object:
            return JsonResponse({
                'status': False,
                'message': '未找到上传的图像文件'
            }, status=400)

        # 保存图像到临时位置（可选，用于调试）
        upload_dir = 'app01/lung/data/images/'
        import os
        os.makedirs(upload_dir, exist_ok=True)

        with open(os.path.join(upload_dir, 'input.png'), mode='wb') as f:
            for chunk in file_object.chunks():
                f.write(chunk)

        return JsonResponse({'status': True, 'message': '图像上传成功'})

    except Exception as e:
        logger.error(f"[skin_disease_upload] 上传失败: {e}")
        return JsonResponse({
            'status': False,
            'message': f'图像上传失败: {str(e)}'
        }, status=500)


@csrf_exempt
def skin_disease_predict(request):
    """
    皮肤病图像分类预测接口

    POST 请求:
        - image: 图像文件 (可选，如果未上传则使用之前保存的图像)
        - return_all_scores: 是否返回所有类别分数 (可选，默认 False)

    Returns:
        JsonResponse: {
            'status': True/False,
            'predicted_class': int,
            'predicted_class_name': str,
            'confidence': float,
            'tips': str,
            'all_scores': dict (可选)
        }
    """
    if request.method != 'POST':
        return JsonResponse({
            'status': False,
            'message': '仅支持 POST 请求'
        }, status=405)

    try:
        # 获取预测器实例
        predictor = get_predictor()

        # 获取图像
        image = None

        # 方式1: 从请求中获取图像文件
        if 'image' in request.FILES:
            file_object = request.FILES['image']
            image = Image.open(file_object).convert('RGB')

        # 方式2: 从之前上传的位置读取
        elif 'uploadImage' in request.FILES:
            file_object = request.FILES['uploadImage']
            image = Image.open(file_object).convert('RGB')

        else:
            # 尝试从保存的位置读取
            import os
            saved_image_path = 'app01/lung/data/images/input.png'
            if os.path.exists(saved_image_path):
                image = Image.open(saved_image_path).convert('RGB')
            else:
                return JsonResponse({
                    'status': False,
                    'message': '未找到图像，请先上传图像'
                }, status=400)

        # 是否返回所有分数
        return_all_scores = request.POST.get('return_all_scores', 'false').lower() == 'true'

        # 调用预测器
        result = predictor.predict(image, return_all_scores=return_all_scores)

        # 生成诊断建议
        tips = _generate_tips(result['predicted_class_name'], result['confidence'])

        # 构建响应
        response_data = {
            'status': True,
            'predicted_class': result['predicted_class'],
            'predicted_class_name': result['predicted_class_name'],
            'confidence': round(result['confidence'], 4),
            'confidence_percent': f"{result['confidence'] * 100:.2f}%",
            'tips': tips
        }

        if return_all_scores:
            # 只返回置信度前5的类别
            all_scores = result.get('all_scores', {})
            sorted_scores = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)[:5]
            response_data['top_predictions'] = [
                {'class_name': name, 'confidence': round(score, 4)}
                for name, score in sorted_scores
            ]

        logger.info(f"[skin_disease_predict] 预测成功: {result['predicted_class_name']} ({result['confidence']:.4f})")
        return JsonResponse(response_data)

    except ImportError as e:
        logger.error(f"[skin_disease_predict] 模块导入失败: {e}")
        return JsonResponse({
            'status': False,
            'message': 'AI 模块加载失败，请检查配置'
        }, status=500)

    except Exception as e:
        logger.error(f"[skin_disease_predict] 预测失败: {e}")
        return JsonResponse({
            'status': False,
            'message': f'预测失败: {str(e)}'
        }, status=500)


def _generate_tips(class_name: str, confidence: float) -> str:
    """
    根据预测结果生成诊断建议

    Args:
        class_name: 预测类别名称
        confidence: 置信度

    Returns:
        str: 诊断建议
    """
    # 常见皮肤病建议映射
    tips_mapping = {
        'Acne_Vulgaris': '检测到痤疮特征，建议保持面部清洁，避免挤压，必要时就医治疗。',
        'Vitiligo': '检测到白癜风特征，建议尽早就医进行专业诊断和治疗。',
        'Eczema': '检测到湿疹特征，建议避免过敏原，保持皮肤湿润，必要时使用药物治疗。',
        'Psoriasis': '检测到银屑病特征，建议就医进行专业诊断和治疗，注意皮肤保湿。',
        'Basal_Cell_Carcinoma': '检测到可疑基底细胞癌特征，请立即就医进行专业检查！',
        'Melanoma': '检测到可疑黑色素瘤特征，请立即就医进行专业检查！',
        'Seborrheic_Keratosis': '检测到脂溢性角化症特征，一般为良性，建议定期观察。',
        'Actinic_Keratosis': '检测到日光性角化症特征，建议就医评估，注意防晒。',
        'Dermatitis': '检测到皮炎特征，建议避免刺激性物质，保持皮肤清洁。',
        'Tinea_Versicolor': '检测到花斑癣特征，建议就医进行抗真菌治疗。',
        'Allergic_Contact_Dermatitis': '检测到过敏性接触性皮炎特征，建议排查过敏原。',
    }

    # 获取建议
    tips = tips_mapping.get(class_name, f'检测到 {class_name} 特征，建议咨询专业医生进行诊断。')

    # 根据置信度添加提示
    if confidence < 0.5:
        tips += ' (注意：置信度较低，建议结合其他检查)'
    elif confidence > 0.8:
        tips += ' (置信度较高)'

    return tips


# ============================================================================
# 兼容旧接口（模拟数据）
# ============================================================================

@csrf_exempt
def lung_upload(request):
    """兼容旧上传接口"""
    return skin_disease_upload(request)


def lung_detect(request):
    """
    兼容旧检测接口（模拟数据）

    注意：此接口仅用于演示，实际请使用 skin_disease_predict
    """
    try:
        # 尝试使用真实预测器
        predictor = get_predictor()

        # 从保存的位置读取图像
        import os
        saved_image_path = 'app01/lung/data/images/input.png'
        if os.path.exists(saved_image_path):
            image = Image.open(saved_image_path).convert('RGB')
            result = predictor.predict(image)
            tips = _generate_tips(result['predicted_class_name'], result['confidence'])

            return JsonResponse({
                'status': True,
                'name': result['predicted_class_name'],
                'rate': result['confidence'],
                'kind': result['predicted_class'],
                'tips': tips
            })
    except Exception as e:
        logger.warning(f"[lung_detect] 使用预测器失败，回退到模拟数据: {e}")

    # 回退到模拟数据
    rate = round(random.uniform(75, 96), 2) / 100
    kind = random.randint(0, 7)

    skin_diseases = [
        {"name": "湿疹", "tips": "检测到湿疹特征，建议避免过敏原并保持皮肤清洁"},
        {"name": "银屑病", "tips": "发现银屑病特征，建议进行专业皮肤科检查"},
        {"name": "痤疮", "tips": "检测到痤疮特征，建议保持面部清洁并避免挤压"},
        {"name": "白癜风", "tips": "发现白癜风特征，建议进行专业诊断和治疗"},
        {"name": "荨麻疹", "tips": "检测到荨麻疹特征，建议排查过敏原"},
        {"name": "皮炎", "tips": "发现皮炎特征，建议避免刺激性物质接触"},
        {"name": "黑色素瘤", "tips": "检测到可疑黑色素瘤特征，请立即就医进行专业检查"},
        {"name": "正常皮肤", "tips": "皮肤图像分析正常，请继续保持皮肤健康"},
    ]

    disease = skin_diseases[kind]

    result = {
        'status': True,
        'name': disease["name"],
        'rate': rate,
        'kind': kind,
        'tips': disease["tips"]
    }
    return JsonResponse(result)