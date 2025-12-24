# Formula Dataset Pipeline — 架构概览

本文档简要说明项目的模块划分、数据流、关键文件与输出、已知风险与改进建议，便于维护与扩展。

## 项目概览

- **目标**：从原始 Parquet 数据构建数学公式识别数据集（JSONL + PNG），包含采样、渲染、人工核验、增强与分析等步骤。
- **风格**：按功能分层的轻量流水线，配套一个基于 `gradio` 的 GUI（`demo.py`）用于手工驱动与参数配置。

## 目录与职责一览

- `origin_data/`：原始数据检查与采样预分析
  - `check.py`：校验 Parquet 列名/基本统计
  - `analyze_pre_sampling.py`：从 Parquet 提取公式、分类、输出 `sampling_rules.json` 与 `intermediate_tagged.jsonl`

- `transfer_data/`：转换与图像生成
  - `convert.py`：将带标签 JSONL 或 Parquet 采样为 `{id, latex}` 的 `formulas.jsonl`
  - `generate_formula_images.py`：根据 LaTeX 或 Parquet 提取生成 PNG，并产出 `dataset.jsonl`
  - `compare.py`：人工核验/清理图集（比对 JSONL 与文件系统）

- `worked_data/`：增强、路径修改与分析
  - `enhance_image.py`：对图片进行增强（旋转等）
  - `modify_image_paths.py`：修改 JSONL 中的图片路径为最终位置
  - `analyze_jsonl.py`：统计、绘图并可生成 AI 报告（可选）

- 其他
  - `demo.py`：Gradio UI，串联各步骤、作为交互入口
  - `requirements.txt`：依赖清单（目标 Python 3.11）

## 数据流（概要）

1. 原始 Parquet → `origin_data/check.py`（检查）
2. Parquet → `origin_data/analyze_pre_sampling.py`（提取公式、分类、输出 `sampling_rules.json` + `intermediate_tagged.jsonl`）
3. `intermediate_tagged.jsonl` 或 Parquet → `transfer_data/convert.py` → `transfer_data/input/formulas.jsonl`
4. `formulas.jsonl` → `transfer_data/generate_formula_images.py` → `transfer_data/output/images/` + `transfer_data/output/dataset.jsonl`
5. `transfer_data/compare.py`：人工核验并清理无效样本
6. 清理后数据 + 图片 → `worked_data/enhance_image.py` → `worked_data/output/images/`
7. `worked_data/modify_image_paths.py`：修正 JSONL 中图片路径 → `worked_data/output/modified_dataset.jsonl`
8. `worked_data/analyze_jsonl.py`：分析最终 JSONL，输出图表与可选 HTML 报告（`worked_data/output/*.png`, `analysis_report.html`）

## 关键产物

- `origin_data/output/sampling_rules.json`
- `origin_data/output/intermediate_tagged.jsonl`
- `transfer_data/input/formulas.jsonl`
- `transfer_data/output/images/`、`transfer_data/output/dataset.jsonl`
- `worked_data/output/images/`、`worked_data/output/modified_dataset.jsonl`
- 分析图：`worked_data/output/latex_length_dist.png`、`worked_data/output/formula_type_dist.png`

## 设计决策与实现要点

- 将“分类/标签”逻辑复用在 `analyze_pre_sampling.py` 与 `analyze_jsonl.py` 中，保证一致性。
- 使用 `matplotlib` 的 mathtext 渲染公式，避免安装系统 LaTeX（跨平台但功能受限）。
- `generate_formula_images.py` 提供两种模式：LaTeX 渲染或从 Parquet 提取图像（支持并行处理与串行阈值切换）。
- `demo.py` 作为 UI 层，直接把后端函数绑定为回调，便于交互式测试与参数调优。

## 已识别风险与改进建议（优先级排序）

- **路径与平台兼容性（高）**：项目混合使用字符串路径与 `pathlib`，并在 Windows 上存在 `\` vs `/` 问题。建议统一使用 `pathlib.Path` 并在 I/O 处显式处理跨平台路径。

- **内存与大文件处理（高）**：`pandas.read_parquet` 在大数据上可能 OOM。建议提供分块处理或基于 `pyarrow` 的流式读取选项。

- **并发与原子性（中）**：并行渲染产生临时文件后重命名为最终文件，Windows 上 rename/replace 语义与权限可能导致失败。建议使用 `tempfile` 且在重命名处增加重试与日志。

- **日志与可观测性（中）**：大量 `print` 调试信息建议替换为 `logging`（可配置级别与输出位置），便于 CI/容器环境诊断。

- **配置集中化（中）**：把目录、阈值、并发数等放到 `config.yaml` 或 `pyproject.toml`，`demo.py` 和后端模块读取同一配置，减少硬编码。

- **测试覆盖（中）**：已有单测较好，建议增加对并发渲染、Parquet 提取（多种 image 列类型）和失败恢复路径的单元/集成测试。

- **渲染容错（低）**：`fix_latex_for_mathtext` 是 heuristic，无法覆盖自定义宏。若需完整 LaTeX 支持，考虑可选地在有能力的环境中提供系统 LaTeX 渲染作为降级选项。

## 建议的短期改进任务（可执行清单）

1. 统一路径处理：替换关键模块中的字符串拼接为 `pathlib.Path`。
2. 引入 `logging`，替换 `print`，并在 `demo.py` 可配置日志级别。
3. 为 `generate_formula_images.py` 添加文件重命名重试逻辑与失败记录（Windows 兼容）。
4. 增加对大 Parquet 的分块读取示例与文档说明。
5. 将本文件保存到仓库根目录（已完成）。

## 下步建议

- 若你希望我继续：我可以把上述改进（1-3）按小步提交为 PR，或仅生成一个 `config.yaml` 与示例变更分支供你审阅。

---

文件位置：`./ARCHITECTURE.md`
