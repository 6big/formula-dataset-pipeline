"""
采样前分析模块。

提供对原始 Parquet 数据中 LaTeX 公式分布的分析功能，
用于指导后续智能采样策略。
纯函数设计，无副作用，符合后端API规范。
"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import Counter

# --- 严格复用 worked_data.analyze_jsonl 中的分类逻辑 ---
from worked_data.analyze_jsonl import (
    classify_formula_type,
    classify_formula_domain,
    FORMULA_TYPE_PATTERNS,  # ← 确保常量也被复用
    FORMULA_DOMAIN_PATTERNS,
)

# --- 第三方依赖 ---
try:
    import pandas as pd
except ImportError:
    raise ImportError("pandas is required for reading Parquet files.")


def extract_latex_formulas(text: str) -> List[str]:
    """
    从单行文本中提取所有 LaTeX 公式片段。

    Args:
        text: 原始文本字符串。

    Returns:
        提取出的 LaTeX 公式列表（不含包裹符号）。
    """
    if not text or not isinstance(text, str):
        return []

    # 检查是否是纯LaTeX公式（没有包裹符号）
    # 如果文本中包含常见的LaTeX命令，我们假设整个文本就是一个公式
    latex_indicators = [
        r"\\[a-zA-Z]+",  # LaTeX命令
        r"\{",  # 花括号
        r"\}",  # 花括号
        r"\^",  # 上标
        r"_",  # 下标
        r"\\frac",  # 分数
        r"\\sum",  # 求和
        r"\\int",  # 积分
        r"\\infty",  # 无穷
    ]

    # 检查是否包含LaTeX特征
    is_latex = any(re.search(indicator, text) for indicator in latex_indicators)

    # 检查是否被常见的公式包裹符号包围
    # 修正逻辑：使用更精确的正则匹配来检测包裹符号
    wrapped_patterns = [
        r"^\$\$.*\$\$$",         # 双美元符号完整包裹整个文本
        r"^\$.*\$$",             # 单美元符号完整包裹整个文本
        r"^\\\((.*)\\\)$",       # \( ... \) 完整包裹整个文本
        r"^\\\[(.*)\\\]$",       # \[ ... \] 完整包裹整个文本
    ]
    is_wrapped = False
    for pattern in wrapped_patterns:
        try:
            if re.match(pattern, text.strip()):
                is_wrapped = True
                break
        except re.error:
            # 如果正则表达式有问题，跳过这个模式
            continue

    # 如果看起来像LaTeX且没有被包裹，则认为整个文本就是一个公式
    if is_latex and not is_wrapped:
        return [text.strip()]

    # 否则使用原来的提取逻辑
    patterns = [
        r"\$\$(.*?)\$\$",      # 双美元符号: $$...$$
        r"(?<!\$)\$(.*?)(?<!\$)\$(?!\$)",  # 单美元符号: $...$ (避免匹配$$...$$)
        r"\\\((.*?)\\\)",      # 圆括号形式: \(...\)
        r"\\\[(.*?)\\\]",      # 方括号形式: \[...\]
    ]
    formulas = []
    for pattern in patterns:
        try:
            matches = re.findall(pattern, text, re.DOTALL)
            formulas.extend([m.strip() for m in matches if m.strip()])
        except re.error:
            # 如果正则表达式有问题，跳过这个模式
            continue

    # 去重保持顺序
    seen = set()
    unique_formulas = []
    for formula in formulas:
        if formula not in seen:
            seen.add(formula)
            unique_formulas.append(formula)

    return unique_formulas


def analyze_formula_distribution(
    parquet_path: str,
    text_column: str = "text",
    rare_count_threshold: int = 10,
    rare_ratio_threshold: float = 0.05,
    target_min_per_class: int = 30,
) -> Dict[str, object]:
    """
    对 Parquet 文件中的公式进行分布分析，返回结构化结果。
    纯函数，无副作用。

    Args:
        parquet_path: Parquet 文件的本地路径。
        text_column: 包含 LaTeX 公式的列名，默认为 "text"。
        rare_count_threshold: 判断稀有类别的最小样本数阈值。
        rare_ratio_threshold: 判断稀有类别的最小占比阈值。
        target_min_per_class: 目标最小样本数（用于采样建议）。

    Returns:
        包含分析结果的字典。
    """
    path = Path(parquet_path)
    if not path.exists():
        raise FileNotFoundError(f"Parquet not found: {parquet_path}")

    # 1. 加载数据
    try:
        df = pd.read_parquet(parquet_path)
    except Exception as e:
        raise FileNotFoundError(f"Cannot read Parquet file: {e}")

    if text_column not in df.columns:
        raise ValueError(f"Column '{text_column}' not found in Parquet file.")

    # 2. 提取公式
    total_rows = len(df)
    empty_row_count = 0
    all_formulas = []
    doc_structures: List[Set[str]] = []
    doc_domains: List[Set[str]] = []

    for idx, row_text in df[text_column].items():
        if pd.isna(row_text):
            empty_row_count += 1
            continue
        text_str = str(row_text)
        formulas = extract_latex_formulas(text_str)
        if not formulas:
            empty_row_count += 1
            continue

        # 记录当前文档的类别（用于覆盖率计算）
        structures = set()
        domains = set()
        for f in formulas:
            s = classify_formula_type(f)  # ← 复用
            d = classify_formula_domain(f)  # ← 复用
            structures.add(s)
            domains.add(d)
            all_formulas.append((f, s, d))  # 保存公式及其分类

        if structures:
            doc_structures.append(structures)
        if domains:
            doc_domains.append(domains)

    total_formulas = len(all_formulas)

    if total_formulas == 0:
        raise ValueError("No formulas found in the specified column.")

    # 3. 分类统计
    structure_counter = Counter()
    domain_counter = Counter()
    for _, s, d in all_formulas:
        structure_counter[s] += 1
        domain_counter[d] += 1

    # 4. 计算文档覆盖率
    def coverage(cats: List[Set[str]], cat: str) -> float:
        if not cats:
            return 0.0
        return sum(1 for s in cats if cat in s) / len(cats)

    doc_cov_s = {c: coverage(doc_structures, c) for c in structure_counter}
    doc_cov_d = {c: coverage(doc_domains, c) for c in domain_counter}

    # 5. 识别稀有类别
    def is_rare(cnt: int, total: int) -> bool:
        return cnt < rare_count_threshold or (cnt / total) < rare_ratio_threshold

    rare_structures = [
        c for c, n in structure_counter.items() if is_rare(n, total_formulas)
    ]
    rare_domains = [c for c, n in domain_counter.items() if is_rare(n, total_formulas)]
    oversample_categories = list(set(rare_structures + rare_domains))

    # 6. 计算采样权重
    weights = {}
    for cat in oversample_categories:
        cnt = structure_counter.get(cat, 0) or domain_counter.get(cat, 0)
        weights[cat] = round(max(2.0, target_min_per_class / max(1, cnt)), 2)

    # 7. 组装结果
    result = {
        "metadata": {
            "analysis_time": datetime.utcnow().isoformat() + "Z",
            "parquet_path": str(path.resolve()),
            "text_column": text_column,
            "total_rows": total_rows,
            "empty_rows": empty_row_count,
            "non_empty_rows": total_rows - empty_row_count,
            "total_formulas": total_formulas,
        },
        "distributions": {
            "structure": dict(structure_counter),
            "domain": dict(domain_counter),
        },
        "coverage": {
            "document_structure": {k: round(v, 4) for k, v in doc_cov_s.items()},
            "document_domain": {k: round(v, 4) for k, v in doc_cov_d.items()},
        },
        "rare_categories": {
            "structure": rare_structures,
            "domain": rare_domains,
        },
        "sampling_recommendations": {
            "strategy": "stratified_oversample",
            "target_min_per_class": target_min_per_class,
            "oversample_weights": weights,
            "oversample_categories": oversample_categories,
            "undersample_categories": (
                ["Other"]
                if "Other" in structure_counter or "Other" in domain_counter
                else []
            ),
            "max_total_samples": min(total_rows, 50_000),
        },
        "summary": {
            "structure_ratio_%": {
                k: round(v / total_formulas * 100, 2)
                for k, v in structure_counter.items()
            },
            "domain_ratio_%": {
                k: round(v / total_formulas * 100, 2) for k, v in domain_counter.items()
            },
        },
    }

    return result


def tag_and_save_intermediate_data(
    parquet_path: str,
    text_column: str = "text",
    output_path: str = "origin_data/output/intermediate_tagged.jsonl",
) -> str:
    """
    为 Parquet 数据打标签并保存为带标签的中间 JSONL 文件。

    Args:
        parquet_path: 原始 Parquet 文件路径
        text_column: 包含 LaTeX 公式的列名
        output_path: 带标签的中间 JSONL 文件输出路径

    Returns:
        处理结果信息
    """
    print(f"开始为数据打标签: {parquet_path}")

    # 加载数据
    path = Path(parquet_path)
    if not path.exists():
        raise FileNotFoundError(f"Parquet not found: {parquet_path}")

    try:
        df = pd.read_parquet(parquet_path)
    except Exception as e:
        raise FileNotFoundError(f"Cannot read Parquet file: {e}")

    if text_column not in df.columns:
        raise ValueError(f"Column '{text_column}' not found in Parquet file.")

    # 创建输出目录
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 处理每一行数据并打标签
    tagged_count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for idx, row_text in df[text_column].items():
            if pd.isna(row_text):
                continue

            text_str = str(row_text)
            formulas = extract_latex_formulas(text_str)

            if not formulas:
                continue

            # 为每个公式打标签
            for formula in formulas:
                structure_tag = classify_formula_type(formula)
                domain_tag = classify_formula_domain(formula)

                # 保存带标签的数据
                tagged_item = {
                    "id": f"formula_{idx:06d}",
                    "latex": formula,
                    "tags": {"structure": structure_tag, "domain": domain_tag},
                }

                f.write(json.dumps(tagged_item, ensure_ascii=False) + "\n")
                tagged_count += 1

    print(f"标签数据已保存到: {out_path.resolve()}")
    return f"✅ 成功为 {tagged_count} 个公式打标签并保存到 {out_path.resolve()}"


def run_pre_sampling_analysis(
    parquet_path: str,
    text_column: str = "text",
    output_path: str = "./origin_data/output/sampling_rules.json",
    rare_count_threshold: int = 10,
    rare_ratio_threshold: float = 0.05,
    target_min_per_class: int = 30,
) -> Dict[str, object]:
    """
    分析 + 保存文件的封装函数。
    供 CLI 或 demo.py 使用。

    Args:
        parquet_path: 原始 Parquet 文件
        text_column: 包含公式的列名
        output_path: sampling_rules.json 输出路径
        intermediate_output: 中间带标签数据的 JSONL 输出路径
        rare_count_threshold: 稀有类最小计数
        rare_ratio_threshold: 稀有类最小占比
        target_min_per_class: 每类目标最小样本数

    Returns:
        分析结果字典（已保存到 output_path）
    """
    print(f"Starting pre-sampling analysis on: {parquet_path}")

    # 调用纯分析函数
    result = analyze_formula_distribution(
        parquet_path=parquet_path,
        text_column=text_column,
        rare_count_threshold=rare_count_threshold,
        rare_ratio_threshold=rare_ratio_threshold,
        target_min_per_class=target_min_per_class,
    )

    # 保存采样规则
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Sampling rules saved to: {out_path.resolve()}")

    # 生成带标签的中间JSONL文件
    tag_result = tag_and_save_intermediate_data(
        parquet_path=parquet_path, text_column=text_column
    )
    print(tag_result)

    return result
