import pandas as pd
import json
import os
import random
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Set, Tuple, Optional, Any

# LaTeX 校验函数（保持不变）
from pylatexenc.latexwalker import LatexWalker, LatexWalkerError


def is_valid_latex(latex_str: str) -> bool:
    if not isinstance(latex_str, str) or not latex_str.strip():
        return False
    try:
        walker = LatexWalker(latex_str.strip())
        walker.get_latex_nodes()
        return True
    except (LatexWalkerError, Exception):
        return False


def convert_tagged_jsonl_to_latex_jsonl(
    input_jsonl: str = "./origin_data/output/intermediate_tagged.jsonl",
    output_dir: str = "./transfer_data/input",
    target_samples: int = 300,
    sampling_strategy: str = "stratified",
    sampling_rules_path: str = "./origin_data/output/sampling_rules.json",
    exclude_other: bool = True,
    exclude_rare: bool = True,
    exclude_custom: Optional[List[str]] = None,
    rare_threshold: int = 10,
) -> str:
    """
    从带标签的 JSONL 文件中提取公式，根据标签进行采样，并生成 {id, latex} 格式的 jsonl。

    Args:
        input_jsonl: 带标签的输入 JSONL 文件路径
        output_dir: 输出目录
        target_samples: 目标样本数
        sampling_strategy: 采样策略 ("random", "stratified")
        sampling_rules_path: 采样规则文件路径
        exclude_other: 是否排除 "Other" 类别
        exclude_rare: 是否排除稀有类别
        exclude_custom: 用户自定义排除的类别列表
        rare_threshold: 稀有类别的阈值
    """
    try:
        # 读取带标签的数据
        tagged_items: List[Dict[str, Any]] = []
        with open(input_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    tagged_items.append(json.loads(line.strip()))

        if not tagged_items:
            return "❌ 输入文件为空"

        print(f"读取到 {len(tagged_items)} 条带标签数据")

        # 第一阶段：拒绝采样（基于类别）
        # 根据规则过滤数据
        filtered_items: List[Dict[str, Any]] = []
        rare_categories: Set[str] = set()

        # 获取稀有类别信息
        if exclude_rare and os.path.exists(sampling_rules_path):
            try:
                with open(sampling_rules_path, "r", encoding="utf-8") as f:
                    sampling_rules: Dict[str, Any] = json.load(f)
                rare_categories = set(
                    sampling_rules.get("rare_categories", {}).get("structure", [])
                )
                rare_categories.update(
                    sampling_rules.get("rare_categories", {}).get("domain", [])
                )
            except Exception as e:
                print(f"读取采样规则文件时出错: {e}")

        # 应用过滤规则
        for item in tagged_items:
            structure: str = item["tags"]["structure"]
            domain: str = item["tags"]["domain"]

            # 检查是否需要排除 "Other" 类别
            if exclude_other and (structure == "其他" or domain == "Other"):
                continue

            # 检查是否需要排除稀有类别
            if exclude_rare and (
                structure in rare_categories or domain in rare_categories
            ):
                continue

            # 检查是否在自定义排除列表中
            if exclude_custom:
                custom_exclude_set: Set[str] = set(exclude_custom)
                if structure in custom_exclude_set or domain in custom_exclude_set:
                    continue

            filtered_items.append(item)

        print(f"过滤后剩余 {len(filtered_items)} 条数据")

        if not filtered_items:
            return "❌ 过滤后无有效数据"

        # 第二阶段：目标数量采样（基于数量）
        selected_items: List[Dict[str, Any]] = []
        if sampling_strategy == "random":
            # 随机采样
            selected_items = random.sample(
                filtered_items, min(target_samples, len(filtered_items))
            )
        elif sampling_strategy == "stratified":
            # 分层采样 - 按比例分配采样数量
            # 统计各类别数量
            category_counts: Dict[str, int] = defaultdict(int)
            items_by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

            for item in filtered_items:
                # 使用结构类型作为主要分类标准
                category: str = item["tags"]["structure"]
                category_counts[category] += 1
                items_by_category[category].append(item)

            # 计算各类别应采样数量（按比例分配）
            total_filtered: int = len(filtered_items)
            samples_per_category: Dict[str, int] = {}
            remaining_samples: int = target_samples

            # 先按比例分配
            for category, count in category_counts.items():
                # 计算该类别应采样的数量（向下取整）
                allocated: int = int(target_samples * count / total_filtered)
                samples_per_category[category] = min(allocated, count)
                remaining_samples -= samples_per_category[category]

            # 将剩余采样数量分配给样本数最多的类别
            sorted_categories: List[Tuple[str, int]] = sorted(
                category_counts.items(), key=lambda x: x[1], reverse=True
            )
            for category, _ in sorted_categories:
                if remaining_samples <= 0:
                    break
                # 可以额外采样的数量
                additional: int = min(
                    remaining_samples,
                    category_counts[category] - samples_per_category[category],
                )
                samples_per_category[category] += additional
                remaining_samples -= additional

            # 执行采样
            for category, items in items_by_category.items():
                sample_count: int = samples_per_category.get(category, 0)
                if sample_count > 0:
                    selected_items.extend(
                        random.sample(items, min(sample_count, len(items)))
                    )

            # 如果采样数量不足，随机补充
            if len(selected_items) < target_samples:
                remaining: int = target_samples - len(selected_items)
                available_items: List[Dict[str, Any]] = [
                    item for item in filtered_items if item not in selected_items
                ]
                selected_items.extend(
                    random.sample(available_items, min(remaining, len(available_items)))
                )
        else:
            # 默认随机采样
            selected_items = random.sample(
                filtered_items, min(target_samples, len(filtered_items))
            )

        # 确保最终采样数量等于目标数量（针对非stratified策略）
        if sampling_strategy != "stratified":
            if len(selected_items) < target_samples and len(filtered_items) > 0:
                # 如果采样数量不足且还有可用数据，尝试补充
                available_items: List[Dict[str, Any]] = [
                    item for item in filtered_items if item not in selected_items
                ]
                if available_items:
                    remaining: int = target_samples - len(selected_items)
                    selected_items.extend(
                        random.sample(
                            available_items, min(remaining, len(available_items))
                        )
                    )
            elif len(selected_items) > target_samples:
                # 如果采样数量过多，随机减少到目标数量
                selected_items = random.sample(selected_items, target_samples)

        # 提取合法 LaTeX
        items: List[Dict[str, Any]] = []
        for idx, item in enumerate(selected_items):
            latex: str = item["latex"]
            if is_valid_latex(latex):
                # 保留标签信息
                new_item: Dict[str, Any] = {"id": item["id"], "latex": latex.strip()}
                # 如果原始项目中有标签，也保留标签
                if "tags" in item:
                    new_item["tags"] = item["tags"]
                items.append(new_item)

        # 保存
        # 如果output_dir参数为空，则使用默认的transfer_data/input目录
        if not output_dir:
            # 获取当前脚本所在目录的父目录，然后构建transfer_data/input路径
            current_script_dir: str = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(current_script_dir, "input")

        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        jsonl_path: str = os.path.join(output_dir, "formulas.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        # 构建相对路径返回值
        relative_output_path: str = os.path.relpath(
            jsonl_path,
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
        )
        relative_output_path = "./" + relative_output_path.replace("\\", "/")

        return (
            f"✅ 从带标签数据提取 LaTeX 完成！\n"
            f"📊 原始标签数据: {len(tagged_items)} 条\n"
            f"📊 过滤后数据: {len(filtered_items)} 条\n"
            f"📊 采样后数据: {len(selected_items)} 条\n"
            f"📊 有效公式: {len(items)} 条\n"
            f"📄 输出: {relative_output_path}"
        )

    except Exception as e:
        return f"❌ 失败: {str(e)}"


def convert_to_latex_jsonl(
    input_parquet: str,
    output_dir: str,
    sample_interval: int = 20,
    target_samples: int = 300,
    total_records_limit: int = 10000,
    id_prefix: str = "formula",
) -> str:
    """
    仅从 Parquet 提取合法 LaTeX，生成 {id, latex} 格式的 jsonl。
    不处理原始图像！
    """
    try:
        df: pd.DataFrame = pd.read_parquet(input_parquet)
        total_rows: int = len(df)

        # 采样
        sample_points: List[int] = []
        total_to_consider: int = min(total_rows, total_records_limit)
        for i in range(0, total_to_consider, sample_interval):
            end: int = min(i + sample_interval, total_to_consider)
            if i < end:
                idx: int = random.randint(i, end - 1)
                sample_points.append(idx)
        sample_points = sample_points[:target_samples]

        # 提取合法 LaTeX
        items: List[Dict[str, Any]] = []
        for idx_in_sample, original_idx in enumerate(sample_points):
            try:
                latex: str = df.iloc[original_idx]["text"]
                if is_valid_latex(latex):
                    items.append(
                        {
                            "id": f"{id_prefix}_{idx_in_sample:06d}",
                            "latex": latex.strip(),
                        }
                    )
            except Exception:
                continue

        # 保存
        # 如果output_dir参数为空，则使用默认的transfer_data/input目录
        if not output_dir:
            # 获取当前脚本所在目录，然后构建transfer_data/input路径
            current_script_dir: str = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(current_script_dir, "input")

        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        jsonl_path: str = os.path.join(output_dir, "formulas.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        # 构建相对路径返回值
        relative_output_path: str = os.path.relpath(
            jsonl_path, os.path.dirname(os.path.dirname(current_script_dir))
        )
        relative_output_path = "./" + relative_output_path.replace("\\", "/")

        return (
            f"✅ 仅提取 LaTeX 完成！\n"
            f"📊 有效公式: {len(items)} 条\n"
            f"📄 输出: {relative_output_path}"
        )

    except Exception as e:
        return f"❌ 失败: {str(e)}"
