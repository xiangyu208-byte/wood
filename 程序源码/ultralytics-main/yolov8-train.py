from ultralytics import YOLO
import os
import torch

# ========================= 1. 核心配置 =========================
# 数据集配置文件路径
DATA_YAML = "yolo-bvn.yaml"
# 训练参数（根据GPU显存调整）
EPOCHS = 500
BATCH_SIZE = 128  # 显存不足则改为64/32
WORKERS = 16
# 自动识别GPU（无GPU则用CPU）
DEVICE = 0 if torch.cuda.is_available() else "cpu"

# ========================= 2. 类别权重（解决9类缺陷不平衡） =========================
# 核心逻辑：样本数越少，权重越高，强制模型关注低频缺陷
# 基于你提供的样本分布手动设定（可根据训练效果微调）
class_weights = {
    0: 80.0,   # defect_0（87个）：极高权重
    1: 10.0,   # defect_1：中权重
    2: 1.0,    # defect_2（10154个）：最低权重
    3: 30.0,   # defect_3（405个）：高权重
    4: 1.0,    # defect_4（17859个）：最低权重
    5: 10.0,   # defect_5：中权重
    6: 15.0,   # defect_6（872个）：较高权重
    7: 10.0,   # defect_7：中权重
    8: 10.0    # defect_8：中权重
}

# ========================= 3. 加载模型并训练（核心适配空标签） =========================
# 选择模型：yolov8s.pt（精度高）/yolov8n.pt（轻量化，显存不足时用）
model = YOLO('yolov8s.pt')  

# 开始训练（关键优化：让模型正确处理空标签）
results = model.train(
    data=DATA_YAML,
    epochs=EPOCHS,
    batch=BATCH_SIZE,
    workers=WORKERS,
    device=DEVICE,
    
    # 学习率优化：慢起步，避免因空标签/不平衡数据震荡
    lr0=0.001,         # 初始学习率（调低，默认0.01，适配不平衡数据）
    lrf=0.01,          # 最终学习率因子
    warmup_epochs=5,   # 预热轮数（延长，让模型先学基础特征）
    optimizer='AdamW', # AdamW优化器：比SGD更适合不平衡数据
    
    # 损失权重：核心适配“有缺陷/无缺陷”区分
    box=7.0,           # 定位损失权重（缺陷定位优先）
    cls=2.0,           # 分类损失权重（提高，强化9类缺陷区分）
    obj=1.5,           # 置信度损失权重（重点！提高该值，让模型更精准区分“有/无缺陷”）
    class_weights=class_weights,  # 类别权重（解决9类缺陷不平衡）
    
    # 训练策略：适配空标签（正常样本）
    patience=60,       # 早停机制（延长，给低频缺陷足够学习时间）
    pretrained=True,   # 预训练权重（必须，基于COCO初始化，加快收敛）
    val=True,          # 每轮验证（监控空标签样本的“无缺陷”识别率）
    save=True,         # 保存最佳模型（按验证集mAP排序）
    save_period=10,    # 每10轮保存一次检查点
    project='runs/detect',
    name='wood_defect_empty_label',  # 实验名称
    exist_ok=True,
    # 关键：关闭强制标注检查，允许空标签
    rect=False,        # 关闭矩形训练，避免空标签样本报错
    single_cls=False   # 保持多类别，不合并
)

# ========================= 4. 模型验证（重点看空标签/低频缺陷效果） =========================
print("训练完成，验证模型性能...")
best_model = YOLO('runs/detect/wood_defect_empty_label/weights/best.pt')
metrics = best_model.val()

# 打印关键指标
print(f"整体mAP@0.5（缺陷检测精度）: {metrics.box.map50:.4f}")
# 打印每类缺陷的精度/召回率（重点看低频缺陷defect_0/defect_3）
for cls_id, (prec, rec) in enumerate(zip(metrics.box.precision, metrics.box.recall)):
    print(f"缺陷{cls_id} - 精度: {prec:.4f}, 召回率: {rec:.4f}")

# ========================= 5. 单张图片测试（验证空标签/缺陷样本预测） =========================
def test_image(img_path):
    """测试单张图片：区分“无缺陷（空标签对应）”和“有缺陷”"""
    if not os.path.exists(img_path):
        print(f"图片不存在：{img_path}")
        return
    # 预测
    results = best_model(img_path)
    # 解析结果：boxes为空 → 无缺陷（对应空标签）；boxes非空 → 有缺陷
    if len(results[0].boxes) == 0:
        print(f"预测结果：该木材无缺陷（正常）")
    else:
        # 提取缺陷类别
        defect_ids = results[0].boxes.cls.cpu().numpy()
        defect_names = [model.names[int(cls)] for cls in defect_ids]
        print(f"预测结果：检测到缺陷 - {defect_names}")
    # 保存预测图（标注缺陷位置/无缺陷提示）
    results[0].save("test_result.jpg")
    print("预测结果图片已保存：test_result.jpg")

# 测试示例（替换为你的图片路径，可测试空标签对应的正常图片）
test_image("D:/aa/ultralytics-main/datasets/data/val/images/normal_wood.jpg")