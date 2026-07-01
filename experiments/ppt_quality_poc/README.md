# PPT Quality POC

这个目录是一个和当前 tokenvizPPT 主系统隔离的最小验证沙盒。

目标不是做完整产品，而是验证一件事：在抛开前端、队列、账户、数据库、编辑器和现有版式约束后，只用 Python + AI + 可选 PPT 模板，能不能把一份文档理解清楚，并生成一份更好看的 PPT。

## 目录结构

```text
experiments/ppt_quality_poc/
  generate_ppt.py          # 一键生成脚本
  sample_input.md          # 示例输入文档
  requirements.txt         # 额外依赖
  inputs/                  # 你可以放真实文档
  templates/               # 你可以放 PPTX 模板
  outputs/                 # 生成结果
```

## 安装依赖

建议在当前 conda 环境里执行：

```bash
conda activate tokenvizppt
cd /home/ubuntu/tokenvizppt/experiments/ppt_quality_poc
python -m pip install -r requirements.txt
```

如果主项目后端依赖已经安装过，大概率只需要确认 `openai`、`python-pptx`、`python-docx`、`pypdf` 存在。

## 配置模型

脚本默认读取 `backend/.env` 里的这些变量：

```bash
TOKENVIZPPT_LLM_MODEL=
TOKENVIZPPT_LLM_API_KEY=
TOKENVIZPPT_LLM_BASE_URL=
TOKENVIZPPT_AI_IMAGE_ENABLED=false
TOKENVIZPPT_AI_IMAGE_MODEL=
TOKENVIZPPT_AI_IMAGE_API_KEY=
TOKENVIZPPT_AI_IMAGE_BASE_URL=
```

也可以直接在命令行前面临时传环境变量。

## 运行

先用示例文档跑：

```bash
python generate_ppt.py \
  --input sample_input.md \
  --topic "AI 产品发布策略" \
  --slides 8 \
  --output outputs/sample_deck.pptx
```

使用你自己的文档：

```bash
python generate_ppt.py \
  --input inputs/your_doc.pdf \
  --topic "你的主题" \
  --slides 10 \
  --output outputs/your_deck.pptx
```

使用 PPTX 模板：

```bash
python generate_ppt.py \
  --input inputs/your_doc.docx \
  --template templates/your_template.pptx \
  --topic "你的主题" \
  --slides 10 \
  --output outputs/from_template.pptx
```

开启 AI 生图：

```bash
python generate_ppt.py \
  --input sample_input.md \
  --topic "AI 产品发布策略" \
  --slides 8 \
  --with-images \
  --output outputs/sample_with_images.pptx
```

## 当前 POC 做了什么

- 解析 `txt/md/csv/pdf/docx`。
- 让大模型先把长文档压缩成结构化洞察。
- 再生成完整 deck plan，包括每页标题、要点、讲述逻辑、视觉建议和生图提示。
- 可选调用 AI 生图。
- 用 `python-pptx` 直接生成 PPTX。
- 如果传入 PPTX 模板，会基于模板创建，并尽量复用模板的主题、母版和尺寸。

## 不做什么

- 不接入当前 FastAPI 后端。
- 不接入数据库、Redis、Celery。
- 不消耗用户积分。
- 不做登录、历史、编辑器。
- 不保证导出的每个元素都可由当前系统编辑。

这个 POC 的价值是让我们快速观察“模型理解 + 设计策略 + 模板约束”本身能做到什么水平，然后再把好用的策略迁回主系统。
