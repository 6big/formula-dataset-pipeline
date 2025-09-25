# Formula Dataset Pipeline

一个轻量级、端到端的合成数学公式数据集生成流水线，专为**构建公式识别数据集（Mathematical Expression Recognition / Math OCR）**任务设计。

> ✨ **无需安装系统级 LaTeX！仅依赖 `matplotlib` 即可渲染公式图像，开箱即用。**  
> 已在 **Python 3.10（Anaconda 3.10.18）** 环境下验证通过。
---

## 项目结构

本项目采用三阶段工作流，确保数据质量与流程清晰：
## 项目结构

本项目采用三阶段工作流，确保数据质量与流程清晰：


- `origin_data/`：原始数据输入区  
  - `check.py`：检查原始数据列名与内容合法性  
  - `convert.py`：转换为标准 `jsonl` 标注 + `images` 文件夹  

- `transfer_data/`：中转处理区（含人工核验）  
  - `generate_formula_images.py`：根据 LaTeX 生成透明背景公式图  
  - `compare.py`：人工筛选后，清理无效样本，确保标注与图像一致  

- `worked_data/`：最终成品区  
  - `enhance_image.py`：对图像做 ±5° 随机旋转（保持透明背景）  
  - `modify_image_paths.py`：修正标注中的图像路径，确保与文件位置匹配  

---

## 输出成果

最终生成：

- `worked_data/images/`：增强后的 PNG 公式图像（透明背景）  
- `worked_data/add_train.jsonl`：与图像严格对应的标注文件，格式如下：

```json
{"image": "images/00001.png", "latex": "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}"}
```

## 环境要求

- Python 3.10  
- 仅需 Python 库依赖（见 `requirements.txt`）  
- 无需安装任何系统级 LaTeX 发行版（如 TeX Live、MiKTeX）  

> 公式渲染完全由 `matplotlib` 的 mathtext 引擎处理，纯 Python 实现，跨平台兼容。

## 注意事项：mathtext 的 LaTeX 支持范围

`matplotlib` 的 mathtext 支持绝大多数标准数学符号，但不支持：

- 自定义宏（如 `\newcommand`）  
- 复杂排版环境（如 `align`、`gather`）  
- `\text{}` 命令（建议改用 `\mathrm{}`）  

✅ 完全支持的示例：

- `x = \frac{a}{b}`  
- `\sqrt{x^2 + y^2}`  
- `\sum_{i=1}^n x_i`  
- `\int_0^\infty e^{-x^2} dx`  

> 如果原始数据包含不支持的语法，`generate_formula_images.py` 会报错。建议在 `convert.py` 阶段做预处理或过滤。
