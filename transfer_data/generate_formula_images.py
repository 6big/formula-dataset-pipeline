import json
import os
import random
import re
from pathlib import Path
from typing import Tuple, List, Dict, Any
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys  # 添加 sys 模块

# --- 1. 原始辅助函数保持不变 ---
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams['font.family'] = 'serif'
rcParams['mathtext.fontset'] = 'cm'

#
def fix_latex_syntax(formula_text):
    """修复LaTeX语法中的常见问题"""
    if not isinstance(formula_text, str):
        return ""
    formula_text = re.sub(r'\\frac\s+1\s*\{', r'\\frac{1}{', formula_text)
    formula_text = re.sub(r'\\frac\s+(-\d+)\s*\{', r'\\frac{\1}{', formula_text)
    formula_text = re.sub(r'\\frac\s+(\d+)\s*\{', r'\\frac{\1}{', formula_text)
    formula_text = re.sub(r'\\begin\{array\}\s*\{([^}]+)\}', r'\\begin{array}{\1}', formula_text)
    formula_text = ' '.join(formula_text.split())
    return formula_text

def validate_latex_syntax(formula_text):
    """验证LaTeX语法括号是否匹配"""
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
    """将LaTeX公式渲染为PNG图片"""
    try:
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_axis_off()

        fixed_latex = fix_latex_syntax(latex)
        if not validate_latex_syntax(fixed_latex):
            print(f"⚠️ LaTeX 语法不合法 in process {os.getpid()}: {fixed_latex[:50]}...")
            plt.close(fig)
            return False

        display_text = f'${fixed_latex}$'

        try:
            ax.text(0.5, 0.5, display_text, fontsize=fontsize, ha='center', va='center')
        except Exception as e:
            print(f"❌ LaTeX 渲染失败 in process {os.getpid()}: {e}")
            plt.close(fig)
            return False  # 不降级为纯文本

        plt.savefig(output_path, dpi=dpi, bbox_inches='tight', pad_inches=0.1, transparent=True)
        plt.close(fig)
        return True

    except Exception as e:
        print(f"❌ 渲染失败 in process {os.getpid()} [{latex[:30]}]: {e}")
        return False


def create_placeholder_image(image_path: Path) -> bool:
    """创建占位符图片，用于表示渲染失败的情况"""
    try:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.set_axis_off()
        ax.text(0.5, 0.5, "❌", fontsize=40, ha='center', va='center', color='red')
        plt.savefig(image_path, dpi=100, bbox_inches='tight', pad_inches=0.1, transparent=True)
        plt.close(fig)
        return True
    except Exception as e:
        logging.error(f"Error creating placeholder image {image_path}: {e}")
        image_path.touch()
        return False

# --- 2. 并行处理函数 ---
def process_image_batch(batch_params: Tuple[List[Dict], Path, int, tuple, int, str, str]) -> List[Dict[str, Any]]:
    """
    处理一个批次的公式数据。

    Args:
        batch_params: (batch_items, images_dir, dpi, figsize, fontsize, failure_strategy, image_prefix)

    Returns:
        List[Dict]: 包含每个项目的处理结果。
    """
    batch_items, images_dir, dpi, figsize, fontsize, failure_strategy, image_prefix = batch_params
    batch_results = []

    for item in batch_items:
        latex = item.get('latex', '')
        img_id = item.get('id', f"{image_prefix}_unknown_{random.randint(0, 1000000)}")

        # --- 生成唯一文件名 ---
        unique_filename = f"{img_id}_w{os.getpid()}.png"
        unique_image_path = images_dir / unique_filename

        success = render_latex_to_png(latex, str(unique_image_path), dpi, figsize, fontsize)
        error_msg = None

        if not success:
            if failure_strategy == "include_failed":
                placeholder_success = create_placeholder_image(unique_image_path)
                success = placeholder_success
                if not placeholder_success:
                    error_msg = "Failed to create placeholder image"
            elif failure_strategy == "interactive":
                error_msg = "LaTeX rendering failed"
            # "skip" 策略下，success 仍为 False

        batch_results.append({
            'original_item': item,
            'unique_image_path': str(unique_image_path.relative_to(images_dir.parent)), # 相对路径
            'success': success,
            'error': error_msg,
            'img_id': img_id, # 用于排序和重命名
            'worker_pid': os.getpid()
        })

    return batch_results

# --- 3. 核心生成函数 ---
def generate_formula_images(
    output_dir: str,
    input_jsonl: str = "origin_data/output/formulas.jsonl",
    user_prompt: str = "请根据以下 LaTeX 公式生成相应的数学表达式图片。",
    image_prefix: str = "sample", # 修改默认前缀
    dpi: int = 100,
    figsize: tuple = (5, 3),
    fontsize: int = 20,
    failure_strategy: str = "skip",
    num_processes: int = None, # 并行进程数
    serial_threshold: int = 200 # 串行阈值
) -> str:
    """
    读取 formulas.jsonl，为每个 LaTeX 渲染 PNG，并生成最终 JSONL。
    根据任务数量决定使用串行或并行处理。
    """
    print("=== 开始生成公式图片 ===")  # 调试输出
    sys.stdout.flush()
    
    if num_processes is None:
        num_processes = os.cpu_count()

    try:
        output_dir = Path(output_dir)
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # 读取输入数据
        with open(input_jsonl, 'r', encoding='utf-8') as f:
            items = [json.loads(line.strip()) for line in f if line.strip()]

        if not items:
            return "⚠️ 输入 JSONL 文件为空或格式错误。"

        total_items = len(items)
        print(f"📊 待处理项目总数: {total_items}")

        # --- 决定处理策略 ---
        if total_items < serial_threshold:
            print(f"📝 任务数量 ({total_items}) 少于阈值 ({serial_threshold})，使用串行处理...")
            # --- 串行处理逻辑 ---
            final_items = []
            bad_ids = []
            success_count = 0
            processed_count = 0

            for item in items:
                latex = item.get('latex', '')
                img_id = item.get('id', f"{image_prefix}_{processed_count:06d}")
                processed_count += 1

                image_filename = f"{img_id}.png" # 串行时直接使用最终格式
                image_path = images_dir / image_filename

                if render_latex_to_png(latex, image_path, dpi, figsize, fontsize):
                    final_item = {
                        "messages": [
                            {"role": "user", "content": user_prompt},
                            {"role": "assistant", "content": latex}
                        ],
                        "images": [f"images/{image_filename}"] # 引用最终格式
                    }
                    final_items.append(final_item)
                    success_count += 1
                else:
                    bad_ids.append(img_id)

                    if failure_strategy == "include_failed":
                        create_placeholder_image(image_path)
                        final_item = {
                            "messages": [
                                {"role": "user", "content": user_prompt},
                                {"role": "assistant", "content": latex}
                            ],
                            "images": [f"images/{image_filename}"]
                        }
                        final_items.append(final_item)
                        success_count += 1
                        bad_ids.pop()
                    elif failure_strategy == "interactive":
                        pass # 保留在 bad_ids
                    # "skip" 策略：跳过

            # 串行处理后直接生成 JSONL
            final_jsonl = output_dir / "dataset.jsonl"
            with open(final_jsonl, 'w', encoding='utf-8') as f:
                for item in final_items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")

            # 记录失败 ID
            bad_ids_path = None
            if bad_ids and failure_strategy in ["interactive", "skip"]:
                bad_ids_path = output_dir / "bad_images.txt"
                with open(bad_ids_path, 'w', encoding='utf-8') as f:
                    for bid in bad_ids:
                        f.write(bid + "\n")

        else: # --- 并行处理逻辑 ---
            print(f"🚀 任务数量 ({total_items}) >= 阈值 ({serial_threshold})，使用 {num_processes} 个进程并行处理...")
            all_batch_results = []

            # 分块
            chunk_size = total_items // num_processes
            if chunk_size == 0:
                chunks = [[item] for item in items]
            else:
                chunks = [items[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
                if len(chunks) > num_processes:
                    last_chunk = chunks.pop()
                    chunks[-1].extend(last_chunk)

            # 准备参数
            batch_params_list = [
                (chunk, images_dir, dpi, figsize, fontsize, failure_strategy, image_prefix)
                for chunk in chunks
            ]

            # 提交任务
            with ProcessPoolExecutor(max_workers=num_processes) as executor:
                future_to_batch_idx = {
                    executor.submit(process_image_batch, params): i
                    for i, params in enumerate(batch_params_list)
                }

                # 收集结果
                for future in as_completed(future_to_batch_idx):
                    batch_idx = future_to_batch_idx[future]
                    try:
                        batch_result = future.result()
                        all_batch_results.extend(batch_result)
                        if batch_result: # 打印第一个处理的 worker ID
                            print(f"✅ 进程 {batch_result[0]['worker_pid']} 完成了批次 {batch_idx}")
                    except Exception as exc:
                        batch_idx = future_to_batch_idx[future]
                        print(f'❌ 批次 {batch_idx} 生成时发生异常: {exc}')

            # --- 汇总、排序、重命名、生成 JSONL ---
            successful_results = [r for r in all_batch_results if r['success']]
            failed_results = [r for r in all_batch_results if not r['success']]

            # 根据 img_id 排序
            try:
                successful_results.sort(key=lambda x: int(x['img_id'].split('_')[-1]))
            except (ValueError, IndexError):
                successful_results.sort(key=lambda x: x['img_id'])

            print(f"🔄 开始重命名 {len(successful_results)} 个成功生成的图片...")
            final_items = []
            rename_success_count = 0

            total_renames = len(successful_results)
            for i, result in enumerate(successful_results, 1):
                # 进度提示
                if i % 50 == 0 or i == total_renames:
                    print(f"🔄 重命名进度: {i}/{total_renames} ({i/total_renames*100:.1f}%)")
                    sys.stdout.flush()  # 强制刷新输出

                unique_path = Path(output_dir) / result['unique_image_path']
                final_filename = f"{result['img_id']}.png"
                final_path = images_dir / final_filename

                try:
                    if unique_path.exists():
                        # 确保目标目录存在
                        final_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # 使用 pathlib.rename 替代 shutil.move（更可靠）
                        unique_path.rename(final_path)
                        rename_success_count += 1

                        final_item = {
                            "messages": [
                                {"role": "user", "content": user_prompt},
                                {"role": "assistant", "content": result['original_item'].get('latex', '')}
                            ],
                            "images": [f"images/{final_filename}"] # 引用重命名后的路径
                        }
                        final_items.append(final_item)
                    else:
                        print(f"    ⚠️ 警告: 预期的唯一文件不存在: {unique_path}")
                except Exception as e:
                    print(f"    ❌ 重命名失败 {unique_path} -> {final_path}: {e}")
                    continue

            print(f"✅ 重命名完成: {rename_success_count}/{total_renames} 成功")

            # 生成 JSONL
            final_jsonl = output_dir / "dataset.jsonl"
            with open(final_jsonl, 'w', encoding='utf-8') as f:
                for item in final_items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")

            # 记录失败 ID
            bad_ids_path = None
            if failed_results and failure_strategy in ["interactive", "skip"]:
                bad_ids = [r['img_id'] for r in failed_results]
                bad_ids_path = output_dir / "bad_images.txt"
                with open(bad_ids_path, 'w', encoding='utf-8') as f:
                    for bid in bad_ids:
                        f.write(bid + "\n")

            success_count = rename_success_count # 重命名成功的数量即最终成功数量
            bad_ids = [r['img_id'] for r in failed_results] # 更新 bad_ids 为失败的原始 ID

        # --- 汇总结果信息 ---
        strategy_desc = {
            "skip": "跳过失败样本",
            "include_failed": "包含占位符",
            "interactive": "记录失败ID供后续处理"
        }

        result = (
            f"✅ 公式图像生成完成！\n"
            f"📊 总记录: {total_items}\n"
            f"✅ 成功处理: {success_count}\n"
            f"❌ 失败样本: {len(bad_ids)}\n"
            f"🔧 策略: {strategy_desc[failure_strategy]}\n"
            f"📁 图片目录: {images_dir}\n"
            f"📄 最终数据集: {final_jsonl}\n"
        )

        if 'bad_ids_path' in locals() and bad_ids_path: # 检查变量是否在当前作用域定义
            result += f"📋 失败列表: {bad_ids_path}\n"

        print("=== 函数执行完成 ===")  # 调试输出
        sys.stdout.flush()
        
        return result

    except Exception as e:
        print(f"❌ 渲染失败: {str(e)}")  # 调试输出
        sys.stdout.flush()
        return f"❌ 渲染失败: {str(e)}"