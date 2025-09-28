import json
import os
import random
import re
from pathlib import Path
from typing import Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams['font.family'] = 'serif'
rcParams['mathtext.fontset'] = 'cm'

def fix_latex_syntax(formula_text):
    if not isinstance(formula_text, str):
        return ""
    formula_text = re.sub(r'\\frac\s+1\s*\{', r'\\frac{1}{', formula_text)
    formula_text = re.sub(r'\\frac\s+(-\d+)\s*\{', r'\\frac{\1}{', formula_text)
    formula_text = re.sub(r'\\frac\s+(\d+)\s*\{', r'\\frac{\1}{', formula_text)
    formula_text = re.sub(r'\\begin\{array\}\s*\{([^}]+)\}', r'\\begin{array}{\1}', formula_text)
    formula_text = ' '.join(formula_text.split())
    return formula_text

def validate_latex_syntax(formula_text):
    if not formula_text or not isinstance(formula_text, str):
        return False
    bracket_count = 0
    for char in formula_text:
        if char == '{':
            bracket_count += 1
        elif char == '}':
            bracket_count -= 1
            if bracket_count < 0:
                return False
    return bracket_count == 0

def render_latex_to_png(latex: str, output_path: str, dpi=100, figsize=(5, 3), fontsize=20) -> bool:
    """只渲染 LaTeX，不降级为纯文本"""
    try:
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_axis_off()
        
        fixed_latex = fix_latex_syntax(latex)
        if not validate_latex_syntax(fixed_latex):
            print(f"⚠️ LaTeX 语法不合法: {fixed_latex[:50]}...")
            plt.close(fig)
            return False
        
        display_text = f'${fixed_latex}$'
        
        try:
            ax.text(0.5, 0.5, display_text, fontsize=fontsize, ha='center', va='center')
        except Exception as e:
            print(f"❌ LaTeX 渲染失败: {e}")
            plt.close(fig)
            return False  # ❌ 不降级为纯文本
        
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight', pad_inches=0.1, transparent=True)
        plt.close(fig)
        return True
        
    except Exception as e:
        print(f"❌ 渲染失败 [{latex[:30]}]: {e}")
        return False

def generate_formula_images(
    output_dir: str,
    # 修改默认路径，使其与convert.py输出路径一致
    input_jsonl: str = "origin_data/output/formulas.jsonl",
    user_prompt: str = "请根据以下 LaTeX 公式生成相应的数学表达式图片。",
    image_prefix: str = "formula",
    dpi: int = 100,
    figsize: tuple = (5, 3),
    fontsize: int = 20,
    failure_strategy: str = "skip"  # 新增：失败处理策略
) -> str:
    """
    读取 formulas.jsonl，为每个 LaTeX 渲染 PNG，并生成最终 JSONL。
    
    Args:
        output_dir: 输出目录
        input_jsonl: 输入的jsonl文件路径，默认为"origin_data/output/formulas.jsonl"
        user_prompt: 用户提示语
        image_prefix: 图片文件名前缀
        dpi, figsize, fontsize: 渲染参数
        failure_strategy: 失败处理策略
            - "skip": 跳过失败样本（默认）
            - "include_failed": 保留失败样本（生成占位符图片）
            - "interactive": 记录失败ID，供后续 compare 处理
    """
    try:
        output_dir = Path(output_dir)
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用参数传递的input_jsonl路径
        with open(input_jsonl, 'r', encoding='utf-8') as f:
            items = [json.loads(line.strip()) for line in f if line.strip()]
        
        final_items = []
        bad_ids = []
        success_count = 0
        processed_count = 0
        
        for item in items:
            latex = item.get('latex', '')
            img_id = item.get('id', f"{image_prefix}_{processed_count:06d}")
            processed_count += 1
            
            image_filename = f"{img_id}.png"
            image_path = images_dir / image_filename
            
            if render_latex_to_png(latex, image_path, dpi, figsize, fontsize):
                # 成功渲染
                final_item = {
                    "messages": [
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": latex}
                    ],
                    "images": [f"images/{image_filename}"]
                }
                final_items.append(final_item)
                success_count += 1
            else:
                # 处理失败样本
                bad_ids.append(img_id)
                
                if failure_strategy == "include_failed":
                    # 生成占位符图片（比如一个红色的 X）
                    create_placeholder_image(image_path)
                    final_item = {
                        "messages": [
                            {"role": "user", "content": user_prompt},
                            {"role": "assistant", "content": latex}
                        ],
                        "images": [f"images/{image_filename}"]
                    }
                    final_items.append(final_item)
                    success_count += 1  # 占位符也算成功
                    bad_ids.pop()  # 从失败列表中移除（因为它被包含在结果中）
                elif failure_strategy == "interactive":
                    # 保持在失败列表中，供 compare 处理
                    pass
                # "skip" 策略：什么都不做，跳过该样本
        
        # 保存最终 JSONL
        final_jsonl = output_dir / "dataset.jsonl"
        with open(final_jsonl, 'w', encoding='utf-8') as f:
            for item in final_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        # 只有在需要时才保存失败列表
        bad_ids_path = None
        if failure_strategy in ["interactive", "skip"]:
            bad_ids_path = output_dir / "bad_images.txt"
            with open(bad_ids_path, 'w', encoding='utf-8') as f:
                for bid in bad_ids:
                    f.write(bid + "\n")
        
        strategy_desc = {
            "skip": "跳过失败样本",
            "include_failed": "包含占位符",
            "interactive": "记录失败ID供后续处理"
        }
        
        result = (
            f"✅ 公式图像生成完成！\n"
            f"📊 总记录: {len(items)}\n"
            f"✅ 成功处理: {success_count}\n"
            f"❌ 失败样本: {len(bad_ids)}\n"
            f"🔧 策略: {strategy_desc[failure_strategy]}\n"
            f"📁 图片目录: {images_dir}\n"
            f"📄 最终数据集: {final_jsonl}\n"
        )
        
        if bad_ids_path:
            result += f"📋 失败列表: {bad_ids_path}\n"
        
        return result
        
    except Exception as e:
        return f"❌ 渲染失败: {str(e)}"

def create_placeholder_image(image_path: Path) -> bool:
    """创建占位符图片（红色 X）"""
    try:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.set_axis_off()
        ax.text(0.5, 0.5, "❌", fontsize=40, ha='center', va='center', color='red')
        plt.savefig(image_path, dpi=100, bbox_inches='tight', pad_inches=0.1, transparent=True)
        plt.close(fig)
        return True
    except Exception:
        # 如果占位符也失败，至少创建一个空文件
        image_path.touch()
        return False