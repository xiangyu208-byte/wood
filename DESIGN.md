---
name: Wood Inspect
description: 清晰、可靠的木材缺陷检测工作台
colors:
  primary: "#276749"
  primary-deep: "#1f513b"
  accent: "#b7791f"
  canvas: "#f5f7f3"
  surface: "#fbfcfa"
  surface-muted: "#edf1eb"
  text: "#17231c"
  text-muted: "#5c6b62"
  border: "#d4ddd6"
  success: "#287a50"
  warning: "#9a640e"
  danger: "#b13a3a"
  info: "#48677a"
typography:
  headline:
    fontFamily: "Inter, PingFang SC, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Inter, PingFang SC, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 650
    lineHeight: 1.35
  body:
    fontFamily: "Inter, PingFang SC, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Inter, PingFang SC, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.4
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "10px 18px"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "10px 18px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "24px"
---

# Design System: Wood Inspect

## Overview

**Creative North Star: "The Quiet Inspection Bench"**

界面模拟白天车间或实验室里的一张整洁质检台：背景安静，工具位置稳定，图片和状态是绝对主角。整体采用受木材与林业启发但不过度拟物的暖绿色体系，以适中的信息密度服务重复操作。

系统拒绝默认 Vue 模板感、高对比摄影背景、玻璃拟态和大面积透明卡片。响应式变化以结构重排为主，移动端保留完整功能；动效只用于解释状态变化，并尊重减少动态效果设置。

**Key Characteristics:**

- 浅色、克制、适合长时间查看图片和表格。
- 状态同时使用文字、形状和语义色，不只依赖颜色。
- 高级设置渐进展开，默认流程保持直接。
- 44 像素以上触控目标和清晰键盘焦点。

## Colors

以深森林绿承担主要操作，暖琥珀仅用于提醒和处理中状态，带绿色倾向的中性色形成稳定工作台。

### Primary

- **Forest Action**：主要按钮、当前导航和键盘焦点。
- **Forest Deep**：主要操作的悬停和按下状态。

### Secondary

- **Timber Amber**：处理中、需要注意但不危险的状态。

### Neutral

- **Workshop Canvas**：页面底色，降低长时间查看疲劳。
- **Paper Surface**：主要工作表面和图片承托区域。
- **Moss Border**：分隔线、输入边界和表格结构。
- **Ink Text**：标题与正文，保证浅色背景上的可读性。

**The Sparse Accent Rule.** 主色只用于主要操作、当前选择和状态提示，不作为装饰填满界面。

## Typography

**Display Font:** Inter、苹方、微软雅黑与系统无衬线回退

**Body Font:** Inter、苹方、微软雅黑与系统无衬线回退

**Character:** 单一无衬线字体保持跨平台稳定，通过字重和紧凑字号建立层级，数据与标签优先清晰而非戏剧性。

### Hierarchy

- **Headline**（700，24px，1.25）：页面标题和关键任务名称。
- **Title**（650，18px，1.35）：区块标题与结果标题。
- **Body**（400，15px，1.6）：说明、数据和错误详情，说明文字限制在 70ch 内。
- **Label**（600，13px，1.4）：字段名、状态和辅助标签。

**The Calm Hierarchy Rule.** 标题通过字号和字重区分，禁止渐变文字、全大写长标签和装饰性字体。

## Elevation

系统以色调分层和细边框为主，阴影仅在主要浮层与悬停反馈中使用。静止表面保持接近扁平，避免多层卡片堆叠。

### Shadow Vocabulary

- **Ambient Low** (`0 10px 30px rgba(25, 52, 36, 0.08)`): 页面级工作表面。
- **Interactive Lift** (`0 8px 20px rgba(25, 52, 36, 0.12)`): 可点击结果条目的悬停反馈。

**The Flat-by-Default Rule.** 阴影表达层级或交互状态，不用于每一个容器。

## Components

### Buttons

- **Shape:** 轻微圆角（6px），保持工具感。
- **Primary:** 深森林绿底色、浅色文字，内边距 10px 18px。
- **Hover / Focus:** 悬停加深，焦点使用 3px 低透明主色外环。
- **Secondary / Ghost:** 浅表面、细边框和深色文字；危险操作使用文字明确的红色语义。

### Chips

- **Style:** 浅语义底色、同色深文字、完整状态文案。
- **State:** 成功、失败、处理中、等待和已取消具有不同文本与图标语义。

### Cards / Containers

- **Corner Style:** 中等圆角（14px）。
- **Background:** Paper Surface。
- **Shadow Strategy:** 仅页面级容器使用 Ambient Low。
- **Border:** 1px Moss Border。
- **Internal Padding:** 桌面 24px，移动端 16px。

### Inputs / Fields

- **Style:** 实色浅背景、1px 边界、6px 圆角。
- **Focus:** 主色边界和低透明外环。
- **Error / Disabled:** 同时改变文字、图标和边界，禁止只变颜色。

### Navigation

桌面使用紧凑顶栏，当前项有实色或底部标记；移动端变为可横向操作的三项导航。每一项保留文字标签，焦点顺序与视觉顺序一致。

### Task Progress

总进度由进度条、已处理计数和当前批次状态共同表达。逐项状态按上传顺序排列，失败原因就地展示，重试与重新识别靠近对应失败条目。

## Do's and Don'ts

### Do:

- **Do** 在所有关键状态旁显示中文文字，不依赖颜色解释结果。
- **Do** 为加载、空数据、网络离线和服务不可用提供不同文案及恢复入口。
- **Do** 在 768px 以下将图片双栏改为单栏、历史表格改为条目列表。
- **Do** 保持所有主要触控目标至少 44px，并提供清晰 `:focus-visible` 状态。

### Don't:

- **Don't** 使用默认 Vue 示例页面的通用绿色和双栏模板感。
- **Don't** 使用会妨碍图片与表格阅读的高对比摄影背景、玻璃拟态和大面积透明卡片。
- **Don't** 使用只有颜色、没有文字的状态表达。
- **Don't** 把识别失败、网络离线或任务取消包装成成功结果。
- **Don't** 为标准表单、表格和导航发明陌生交互。
- **Don't** 使用大于 1px 的彩色侧边条、渐变文字或嵌套卡片。
