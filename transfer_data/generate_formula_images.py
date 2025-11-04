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

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams["font.family"] = "serif"
rcParams["mathtext.fontset"] = "cm"


def fix_latex_for_mathtext(formula_text):
    """
    将 LaTeX 公式转换为 Matplotlib mathtext 兼容格式。

    修复内容：
    - \\frac a b → \\frac{a}{b}
    - \\cal → \\mathcal
    - 移除 \\big/\\Big/\\bigg/... 等尺寸命令（mathtext 不支持）
    - \\stackrel → \\overset
    - \\sp → ^
    - \\phantom{...} → 移除
    - 清理不可见字符和多余空格
    - 确保 \\ge, \\le 等符号前后有空格

    Args:
        formula_text (str): 原始 LaTeX 公式字符串。

    Returns:
        str: 修复后的 mathtext 兼容字符串。
    """
    if not isinstance(formula_text, str):
        return ""

    try:
        # 1. 清理不可见字符
        formula_text = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad]", "", formula_text)

        # 2. 修复不规范的 \frac 语法
        # 处理 \frac num}{} { den} 这种错误格式
        def _fix_bad_frac1(match):
            try:
                # 提取 numerator 和 denominator
                num = match.group(1).strip()
                den = match.group(2).strip()
                # 确保用花括号包围
                num = (
                    f"{{{num}}}"
                    if not (num.startswith("{") and num.endswith("}"))
                    else num
                )
                den = (
                    f"{{{den}}}"
                    if not (den.startswith("{") and den.endswith("}"))
                    else den
                )
                return f"\\frac{num}{den}"
            except:
                # 如果修复失败，返回原始匹配内容
                return match.group(0)

        # 匹配 \frac num}{} { den} 这样的模式
        formula_text = re.sub(
            r"\\frac\s+([^}]*)\}\s*\{\s*\}\s*\{\s*([^}]*)\}",
            _fix_bad_frac1,
            formula_text,
        )

        # 匹配 \frac{num}{} {den} 这样的模式
        formula_text = re.sub(
            r"\\frac\s*\{([^}]*)\}\s*\{\s*\}\s*\{\s*([^}]*)\}",
            _fix_bad_frac1,
            formula_text,
        )

        # 处理 \frac{num}{den} 中间有空格的情况
        formula_text = re.sub(
            r"\\frac\s*\{([^}]*)\}\s*\{([^}]*)\}", r"\\frac{\1}{\2}", formula_text
        )

        # 2.1 规范化正常的 \frac（仅处理简单情况，复杂表达式需手动加花括号）
        def _fix_frac(match):
            try:
                num = match.group(1).strip()
                den = match.group(2).strip()
                num = (
                    f"{{{num}}}"
                    if not (num.startswith("{") and num.endswith("}"))
                    else num
                )
                den = (
                    f"{{{den}}}"
                    if not (den.startswith("{") and den.endswith("}"))
                    else den
                )
                return f"\\frac{num}{den}"
            except:
                # 如果规范化失败，返回原始匹配内容
                return match.group(0)

        formula_text = re.sub(
            r"\\frac\s*(\S(?:[^{}]|{[^}]*})*)\s*(\S(?:[^{}]|{[^}]*})*)",
            _fix_frac,
            formula_text,
        )

        # 3. 替换 \cal → \mathcal
        try:
            formula_text = re.sub(
                r"\\cal\s*\{([^}]*)\}", r"\\mathcal{\1}", formula_text
            )
            formula_text = re.sub(
                r"\{\s*\\cal\s+([A-Za-z])\s*\}", r"\\mathcal{\1}", formula_text
            )
        except:
            pass  # 如果替换失败，保持原样

        # 4. 移除所有 \big...\Big 命令（最安全做法）
        big_commands = [
            r"\\bigl",
            r"\\bigr",
            r"\\Bigl",
            r"\\Bigr",
            r"\\biggl",
            r"\\biggr",
            r"\\Biggl",
            r"\\Biggr",
            r"\\big",
            r"\\Big",
            r"\\bigg",
            r"\\Bigg",
        ]
        for cmd in big_commands:
            formula_text = formula_text.replace(cmd, "")

        # 5. \stackrel → \overset
        try:
            formula_text = re.sub(
                r"\\stackrel\s*\{([^}]*)\}\s*\{([^}]*)\}",
                r"\\overset{\1}{\2}",
                formula_text,
            )
        except:
            pass  # 如果替换失败，保持原样

        # 6. \sp → ^
        try:
            formula_text = re.sub(r"\\sp\s*\{([^}]*)\}", r"^{\1}", formula_text)
            formula_text = re.sub(r"\\sp\s+(\S+)", r"^{\1}", formula_text)
        except:
            pass  # 如果替换失败，保持原样

        # 7. 移除 \phantom
        try:
            formula_text = re.sub(r"\\phantom\s*\{[^}]*\}", "", formula_text)
        except:
            pass  # 如果替换失败，保持原样

        # 8. 修复 \le ft 和 \ri ght 错误（应该是 \left 和 \right）
        formula_text = re.sub(r"\\le\s*ft", r"\\left", formula_text)
        formula_text = re.sub(r"\\ri\s*ght", r"\\right", formula_text)

        # 修复其他不完整的 LaTeX 命令
        formula_text = re.sub(r"\\no\s*number", r"\\nonumber", formula_text)
        formula_text = re.sub(r"\\ma\s*thrm", r"\\mathrm", formula_text)
        formula_text = re.sub(r"\\wi\s*detilde", r"\\widetilde", formula_text)
        formula_text = re.sub(r"\\bar\s*\{\s*A\s*\}", r"\\bar{A}", formula_text)

        # 9. 确保关系符前后有空格（避免 \ge0）
        rel_ops = [r"\\ge", r"\\le", r"\\ne", r"\\approx", r"\\equiv"]
        for op in rel_ops:
            try:
                # 在操作符前加空格（如果前面是非空格）
                formula_text = re.sub(rf"(\S)({op})", r"\1 \2", formula_text)
                # 在操作符后加空格（如果后面是非空格）
                formula_text = re.sub(rf"({op})(\S)", r"\1 \2", formula_text)
            except:
                pass  # 如果替换失败，保持原样

        # 10. 清理多余空白
        formula_text = " ".join(formula_text.split())

    except Exception as e:
        print(f"⚠️ 修复LaTeX时出错: {e}, 使用原始文本")
        return formula_text  # 出错时返回原始文本

    return formula_text


def validate_latex_syntax(formula_text):
    """验证LaTeX语法括号是否匹配"""
    if not formula_text or not isinstance(formula_text, str):
        return False

    # 对于空公式或非常短的公式，认为是有效的
    if len(formula_text.strip()) < 2:
        return True

    try:
        bracket_count = 0
        for char in formula_text:
            if char == "{":
                bracket_count += 1
            elif char == "}":
                bracket_count -= 1
                if bracket_count < 0:
                    return False

        # 允许轻微的括号不匹配，增加容错性
        return bracket_count <= 2 and bracket_count >= -2
    except:
        # 如果验证过程出错，返回True，让后续渲染过程决定
        return True


def render_latex_to_png(
    latex: str, output_path: str, dpi=100, figsize=(5, 3), fontsize=20
) -> bool:
    """将LaTeX公式渲染为PNG图片"""
    try:
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_axis_off()

        #    fixed_latex = fix_latex_for_mathtext(latex)
        fixed_latex = latex
        if not validate_latex_syntax(fixed_latex):
            print(f"⚠️ LaTeX 语法不合法 in process {os.getpid()}: {fixed_latex[:50]}...")
            plt.close(fig)
            return False

        display_text = f"${fixed_latex}$"

        try:
            ax.text(0.5, 0.5, display_text, fontsize=fontsize, ha="center", va="center")
        except Exception as e:
            print(f"❌ LaTeX 渲染失败 in process {os.getpid()}: {e}")
            plt.close(fig)
            # 尝试更简单的渲染方式
            try:
                # 如果复杂公式失败，尝试只渲染纯文本部分
                simple_text = latex[:50] + "..." if len(latex) > 50 else latex
                ax.text(
                    0.5, 0.5, simple_text, fontsize=fontsize, ha="center", va="center"
                )
                print(f"⚠️ 使用简化文本渲染 in process {os.getpid()}: {simple_text}")
            except Exception as e2:
                print(f"❌ 简化文本渲染也失败 in process {os.getpid()}: {e2}")
                plt.close(fig)
                return False  # 直接返回False，不创建占位符

        plt.savefig(
            output_path, dpi=dpi, bbox_inches="tight", pad_inches=0.1, transparent=True
        )
        plt.close(fig)
        return True

    except Exception as e:
        print(f"❌ 渲染失败 in process {os.getpid()} [{latex[:30]}]: {e}")
        return False  # 直接返回False，不创建占位符


def create_placeholder_image(image_path: Path) -> bool:
    """创建占位符图片，用于表示渲染失败的情况"""
    try:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.set_axis_off()
        ax.text(0.5, 0.5, "❌", fontsize=40, ha="center", va="center", color="red")
        plt.savefig(
            image_path, dpi=100, bbox_inches="tight", pad_inches=0.1, transparent=True
        )
        plt.close(fig)
        return True
    except Exception as e:
        logging.error(f"Error creating placeholder image {image_path}: {e}")
        image_path.touch()
        return False


# --- 2. 并行处理函数 ---
def process_image_batch(
    batch_params: Tuple[List[Dict], Path, int, tuple, int, str, str],
) -> List[Dict[str, Any]]:
    """
    处理一个批次的公式数据。

    Args:
        batch_params: (batch_items, images_dir, dpi, figsize, fontsize, failure_strategy, image_prefix)

    Returns:
        List[Dict]: 包含每个项目的处理结果。
    """
    batch_items, images_dir, dpi, figsize, fontsize, failure_strategy, image_prefix = (
        batch_params
    )
    batch_results = []

    for item in batch_items:
        latex = item.get("latex", "")
        img_id = item.get("id", f"{image_prefix}_unknown_{random.randint(0, 1000000)}")

        # --- 生成唯一文件名 ---
        unique_filename = f"{img_id}_w{os.getpid()}.png"
        unique_image_path = images_dir / unique_filename

        success = False
        error_msg = None

        try:
            success = render_latex_to_png(
                latex, str(unique_image_path), dpi, figsize, fontsize
            )
            if not success:
                error_msg = "LaTeX rendering failed"
        except Exception as e:
            error_msg = f"Exception during rendering: {str(e)}"
            print(f"❌ 处理条目时发生异常 in process {os.getpid()}: {e}")

        if not success:
            if failure_strategy == "create_placeholder":
                # 创建占位符图像以表示渲染失败
                try:
                    placeholder_success = create_placeholder_image(unique_image_path)
                    success = placeholder_success
                    if not placeholder_success:
                        error_msg = "Failed to create placeholder image"
                except Exception as e:
                    error_msg = f"Exception creating placeholder: {str(e)}"
                    print(f"❌ 创建占位符时发生异常 in process {os.getpid()}: {e}")
            elif failure_strategy == "skip" or failure_strategy == "interactive":
                # 对于 skip 和 interactive 模式，保持 success = False，由上层逻辑处理
                pass
            else:
                # 容错：处理未知策略
                print(f"⚠️ 未知的 failure_strategy: {failure_strategy}, 默认跳过")
                pass

        batch_results.append(
            {
                "original_item": item,
                "unique_image_path": str(
                    unique_image_path.relative_to(images_dir.parent)
                ),  # 相对路径
                "success": success,
                "error": error_msg,
                "img_id": img_id,  # 用于排序和重命名
                "worker_pid": os.getpid(),
            }
        )

    return batch_results


# --- 3. 核心生成函数 ---
def generate_formula_images(
    output_dir: str,
    input_jsonl: str = "transfer_data/input/formulas.jsonl",
    user_prompt: str = "请根据以下 LaTeX 公式生成相应的数学表达式图片。",
    image_prefix: str = "sample",  # 修改默认前缀
    dpi: int = 100,
    figsize: tuple = (5, 3),
    fontsize: int = 20,
    failure_strategy: str = "skip",
    record_failed_ids: bool = False,
    num_processes: int = None,  # 并行进程数
    serial_threshold: int = 200,  # 串行阈值
) -> str:
    """
    读取 formulas.jsonl，为每个 LaTeX 渲染 PNG，并生成最终 JSONL。
    根据任务数量决定使用串行或并行处理。

    Args:
        output_dir: 输出目录
        input_jsonl: 输入JSONL文件路径
        user_prompt: 用户提示词
        image_prefix: 图像文件前缀
        dpi: 图像DPI
        figsize: 图像尺寸
        fontsize: 字体大小
        failure_strategy: 失败处理策略 ("skip", "create_placeholder", "interactive")
        record_failed_ids: 是否记录失败样本ID（当failure_strategy为"skip"或"interactive"时有效）
        num_processes: 并行进程数
        serial_threshold: 串行处理阈值
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
        with open(input_jsonl, "r", encoding="utf-8") as f:
            items = [json.loads(line.strip()) for line in f if line.strip()]

        if not items:
            return "⚠️ 输入 JSONL 文件为空或格式错误。"

        total_items = len(items)
        print(f"📊 待处理项目总数: {total_items}")

        # --- 决定处理策略 ---
        if total_items < serial_threshold:
            print(
                f"📝 任务数量 ({total_items}) 少于阈值 ({serial_threshold})，使用串行处理..."
            )
            # --- 串行处理逻辑 ---
            final_items = []
            bad_ids = []
            success_count = 0
            processed_count = 0

            for item in items:
                latex = item.get("latex", "")
                img_id = item.get("id", f"{image_prefix}_{processed_count:06d}")
                processed_count += 1

                image_filename = f"{img_id}.png"  # 串行时直接使用最终格式
                image_path = images_dir / image_filename

                if render_latex_to_png(latex, image_path, dpi, figsize, fontsize):
                    final_item = {
                        "messages": [
                            {"role": "user", "content": user_prompt},
                            {"role": "assistant", "content": latex},
                        ],
                        "images": [f"images/{image_filename}"],  # 引用最终格式
                    }
                    final_items.append(final_item)
                    success_count += 1
                else:
                    bad_ids.append(img_id)

                    if failure_strategy == "create_placeholder":
                        # 创建占位符图像
                        create_placeholder_image(image_path)
                        final_item = {
                            "messages": [
                                {"role": "user", "content": user_prompt},
                                {"role": "assistant", "content": latex},
                            ],
                            "images": [f"images/{image_filename}"],
                        }
                        final_items.append(final_item)
                        success_count += 1
                        bad_ids.pop()  # 移除已处理的失败ID
                    # 其他策略（"skip" 和 "interactive"）会保留失败ID

            # 串行处理后直接生成 JSONL
            final_jsonl = output_dir / "dataset.jsonl"
            with open(final_jsonl, "w", encoding="utf-8") as f:
                for item in final_items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")

            # 记录失败 ID
            bad_ids_path = None
            if bad_ids and record_failed_ids:
                bad_ids_path = output_dir / "bad_images.txt"
                with open(bad_ids_path, "w", encoding="utf-8") as f:
                    for bid in bad_ids:
                        f.write(bid + "\n")

        else:  # --- 并行处理逻辑 ---
            print(
                f"🚀 任务数量 ({total_items}) >= 阈值 ({serial_threshold})，使用 {num_processes} 个进程并行处理..."
            )
            all_batch_results = []

            # 分块
            chunk_size = total_items // num_processes
            if chunk_size == 0:
                chunks = [[item] for item in items]
            else:
                chunks = [
                    items[i : i + chunk_size] for i in range(0, total_items, chunk_size)
                ]
                if len(chunks) > num_processes:
                    last_chunk = chunks.pop()
                    chunks[-1].extend(last_chunk)

            # 准备参数
            batch_params_list = [
                (
                    chunk,
                    images_dir,
                    dpi,
                    figsize,
                    fontsize,
                    failure_strategy,
                    image_prefix,
                )
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
                        if batch_result:  # 打印第一个处理的 worker ID
                            print(
                                f"✅ 进程 {batch_result[0]['worker_pid']} 完成了批次 {batch_idx}"
                            )
                    except Exception as exc:
                        batch_idx = future_to_batch_idx[future]
                        print(f"❌ 批次 {batch_idx} 生成时发生异常: {exc}")

            # --- 汇总、排序、重命名、生成 JSONL ---
            successful_results = [r for r in all_batch_results if r["success"]]
            failed_results = [r for r in all_batch_results if not r["success"]]

            # 根据 img_id 排序
            try:
                successful_results.sort(key=lambda x: int(x["img_id"].split("_")[-1]))
            except (ValueError, IndexError):
                successful_results.sort(key=lambda x: x["img_id"])

            print(f"🔄 开始重命名 {len(successful_results)} 个成功生成的图片...")
            final_items = []
            rename_success_count = 0

            total_renames = len(successful_results)
            for i, result in enumerate(successful_results, 1):
                # 进度提示
                if i % 50 == 0 or i == total_renames:
                    print(
                        f"🔄 重命名进度: {i}/{total_renames} ({i/total_renames*100:.1f}%)"
                    )
                    sys.stdout.flush()  # 强制刷新输出

                unique_path = Path(output_dir) / result["unique_image_path"]
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
                                {
                                    "role": "assistant",
                                    "content": result["original_item"].get("latex", ""),
                                },
                            ],
                            "images": [
                                f"images/{final_filename}"
                            ],  # 引用重命名后的路径
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
            with open(final_jsonl, "w", encoding="utf-8") as f:
                for item in final_items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")

            # 记录失败 ID
            bad_ids_path = None
            if failed_results and record_failed_ids:
                bad_ids = [r["img_id"] for r in failed_results]
                bad_ids_path = output_dir / "bad_images.txt"
                with open(bad_ids_path, "w", encoding="utf-8") as f:
                    for bid in bad_ids:
                        f.write(bid + "\n")

            success_count = rename_success_count  # 重命名成功的数量即最终成功数量
            bad_ids = [
                r["img_id"] for r in failed_results
            ]  # 更新 bad_ids 为失败的原始 ID

        # --- 汇总结果信息 ---
        strategy_desc = {"skip": "跳过失败样本", "create_placeholder": "创建占位符图像"}

        result = (
            f"✅ 公式图像生成完成！\n"
            f"📊 总记录: {total_items}\n"
            f"✅ 成功处理: {success_count}\n"
            f"❌ 失败样本: {len(bad_ids)}\n"
            f"🔧 策略: {strategy_desc[failure_strategy]}\n"
            f"📁 图片目录: {images_dir}\n"
            f"📄 最终数据集: {final_jsonl}\n"
        )

        if record_failed_ids and bad_ids_path:  # 检查变量是否在当前作用域定义
            result += f"📋 失败列表: {bad_ids_path}\n"

        print("=== 函数执行完成 ===")  # 调试输出
        sys.stdout.flush()

        return result

    except Exception as e:
        print(f"❌ 渲染失败: {str(e)}")  # 调试输出
        sys.stdout.flush()
        return f"❌ 渲染失败: {str(e)}"
