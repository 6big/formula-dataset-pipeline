import pandas as pd
import json
import os
import random
from pathlib import Path

# LaTeX 校验函数（保持不变）
from pylatexenc.latexwalker import LatexWalker, LatexWalkerError

def is_valid_latex(latex_str):
    if not isinstance(latex_str, str) or not latex_str.strip():
        return False
    try:
        walker = LatexWalker(latex_str.strip())
        walker.get_latex_nodes()
        return True
    except (LatexWalkerError, Exception):
        return False

def convert_to_latex_jsonl(
    input_parquet: str,
    output_dir: str,
    sample_interval: int = 20,
    target_samples: int = 300,
    total_records_limit: int = 10000,
    id_prefix: str = "formula"
) -> str:
    """
    仅从 Parquet 提取合法 LaTeX，生成 {id, latex} 格式的 jsonl。
    不处理原始图像！
    """
    try:
        df = pd.read_parquet(input_parquet)
        total_rows = len(df)
        
        # 采样
        sample_points = []
        total_to_consider = min(total_rows, total_records_limit)
        for i in range(0, total_to_consider, sample_interval):
            end = min(i + sample_interval, total_to_consider)
            if i < end:
                idx = random.randint(i, end - 1)
                sample_points.append(idx)
        sample_points = sample_points[:target_samples]

        # 提取合法 LaTeX
        items = []
        for idx_in_sample, original_idx in enumerate(sample_points):
            try:
                latex = df.iloc[original_idx]['text']
                if is_valid_latex(latex):
                    items.append({
                        "id": f"{id_prefix}_{idx_in_sample:06d}",
                        "latex": latex.strip()
                    })
            except Exception:
                continue

        # 保存
        # 如果output_dir参数为空，则使用默认的transfer_data/input目录
        if not output_dir:
            # 获取当前脚本所在目录的父目录，然后构建transfer_data/input路径
            current_script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(current_script_dir, "input")
        
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        jsonl_path = os.path.join(output_dir, "formulas.jsonl")
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        return (
            f"✅ 仅提取 LaTeX 完成！\n"
            f"📊 有效公式: {len(items)} 条\n"
            f"📄 输出: {jsonl_path}"
        )

    except Exception as e:
        return f"❌ 失败: {str(e)}"
