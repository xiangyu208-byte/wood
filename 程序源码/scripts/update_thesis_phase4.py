from __future__ import annotations

import sys
from pathlib import Path

from docx import Document


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: 期望匹配 1 次，实际 {count} 次")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法: update_thesis_phase4.py <document.docx>")
    path = Path(sys.argv[1]).resolve()
    document = Document(path)
    changes = 0

    for paragraph in document.paragraphs:
        text = paragraph.text
        if "用Wise-IoU损失函数替代CioU损失函数" in text:
            paragraph.text = replace_once(
                text,
                "、更改YOLO损失函数（用Wise-IoU损失函数替代CioU损失函数）",
                "",
                "摘要 Wise-IoU",
            )
            changes += 1
        elif text.startswith("最终实验显示，选用的模型准确率达到95.5%"):
            paragraph.text = (
                "模型检查点保存的历史验证结果为：精确率95.374%，召回率89.180%，"
                "mAP@0.5为95.145%，mAP@0.5:0.95为75.373%。这些数值来自最优权重的训练记录；"
                "由于原训练与验证数据集未随工程归档，当前尚不能独立复算，后续应以统一评估脚本"
                "在同版本数据集上的输出为最终依据。"
            )
            changes += 1
        elif "、用Wise-IoU损失函数替代CioU[5]" in text:
            paragraph.text = replace_once(
                text,
                "、用Wise-IoU损失函数替代CioU[5]",
                "",
                "正文 Wise-IoU",
            )
            changes += 1
        elif text.startswith("PR曲线全称为精确率") and "对比两张 PR 曲线" in text:
            prefix = text.split("对比两张 PR 曲线", 1)[0]
            paragraph.text = (
                prefix
                + "模型检查点保存的全类别历史mAP@0.5为0.95145，与图中约0.951的展示一致。"
                "由于原验证集尚未随工程归档，本次无法独立复算各类别AP与曲线，因此不再列出"
                "无法由现有工程复现的逐类数值。恢复同版本数据集后，应使用evaluate.py统一生成"
                "PR曲线和评价指标，并以evaluation.json为准。"
            )
            changes += 1
        elif text.startswith("在木材缺陷检测的实际场景中") and "所有类别的平均F1分数由0.91提升至0.92" in text:
            old = "所有类别的平均F1分数由0.91提升至0.92，最佳置信度阈值也由0.438提升至0.547，说明模型在提升置信度的同时，仍能维持较高的F1分数，综合检测性能更稳定。"
            new = (
                "图示历史结果中全类别最佳F1约为0.92；该数值与最佳阈值需要在原验证集恢复后，"
                "由evaluate.py重新生成曲线并复核，现阶段不作为独立复现实验结论。"
            )
            paragraph.text = replace_once(text, old, new, "F1 指标口径")
            changes += 1

    if changes != 5:
        raise RuntimeError(f"期望修改 5 个段落，实际修改 {changes} 个")
    document.save(path)
    print(f"已更新 {path}，修改段落数: {changes}")


if __name__ == "__main__":
    main()
