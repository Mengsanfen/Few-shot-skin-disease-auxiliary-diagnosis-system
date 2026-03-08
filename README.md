项目名：SkinProto - 基于原型网络的小样本皮肤病辅助诊断系统
品牌符号：SkinProto
----
本项目基于SFEPT（Semantic Feature Enhanced Prototypical Transformer）算法，针对皮肤病医学图像，结合原型网络、Swin Transformer特征提取、Bias Diminishing原型修正策略、SAE语义特征增强等技术，提供小样本皮肤病图像分类、智能诊断、皮肤病科普等功能，并通过 ECharts 数据可视化展示系统性能指标。

核心算法特点：
1. 使用 Swin Transformer 提取特征
2. 引入非迭代的原型修正策略（Bias Diminishing）解决小样本偏差
3. 使用冻结的 BERT 作为潜语义投影器（SAE模块）进行特征增强

1. 首先，需要安装依赖包：

2. 数据迁移
```bash
python manage.py makemigrations
python manage.py migrate``
```

3. 运行项目
```bash
python manage.py runserver
```