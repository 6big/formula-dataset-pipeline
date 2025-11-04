import json
import os
import re
from pathlib import Path


def extract_image_number(filename):
    """
    从文件名中提取数字编号

    Args:
        filename: 文件名，如 "formula_000000.png"

    Returns:
        str: 数字编号，如 "000000"
    """
    # 支持多种命名格式：image_000.png, formula_000.png 等
    match = re.search(r"(\d{6})\.png$", filename)
    if match:
        return match.group(1)
    return None


def compare_and_clean(
    jsonl_file_path: str,
    images_folder_path: str,
    mode: str = "auto",  # "auto", "interactive", "skip"
    bad_images_file: str = None,  # 可选：从 bad_images.txt 读取失败列表
) -> str:
    """
    核验 JSONL 中的图片路径，清理无效条目。

    Args:
        jsonl_file_path: JSONL 文件路径
        images_folder_path: 图片文件夹路径
        mode: 处理模式
            - "auto": 自动删除不存在的图片条目
            - "interactive": 仅返回统计信息，供用户决定
            - "skip": 跳过处理
        bad_images_file: 可选，bad_images.txt 路径（从 generate 步骤生成）

    Returns:
        str: 处理结果信息
    """
    if mode == "skip":
        return "✅ 跳过核验步骤"

    try:
        # 获取所有实际存在的图片编号
        existing_image_numbers = set()
        images_dir = Path(images_folder_path)

        if not images_dir.exists():
            return f"❌ 图片目录不存在: {images_folder_path}"

        for filename in os.listdir(images_dir):
            if filename.lower().endswith(".png"):
                image_number = extract_image_number(filename)
                if image_number:
                    existing_image_numbers.add(image_number)

        print(f"文件夹中找到 {len(existing_image_numbers)} 个图片文件")

        # 读取 bad_images.txt（如果有）
        bad_image_numbers = set()
        if bad_images_file and Path(bad_images_file).exists():
            with open(bad_images_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        bad_image_numbers.add(extract_image_number(line) or line)

        # 统计信息
        total_lines = 0
        kept_lines = 0
        removed_lines = 0
        missing_images = []  # 记录缺失的图片

        # 读取 JSONL 并检查图片存在性
        with open(jsonl_file_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

        cleaned_lines = []

        for line in lines:
            total_lines += 1
            try:
                data = json.loads(line.strip())
                images = data.get("images", [])

                # 检查所有图片是否都存在
                all_images_exist = True
                for image_path in images:
                    image_filename = os.path.basename(image_path)
                    image_number = extract_image_number(image_filename)

                    if not image_number or image_number not in existing_image_numbers:
                        all_images_exist = False
                        missing_images.append(image_path)
                        break

                if all_images_exist:
                    cleaned_lines.append(line)
                    kept_lines += 1
                else:
                    removed_lines += 1

            except json.JSONDecodeError:
                removed_lines += 1  # JSON 解析失败也删除

        if mode == "auto":
            # 自动模式：直接写回文件
            with open(jsonl_file_path, "w", encoding="utf-8") as file:
                file.writelines(cleaned_lines)

            result = (
                f"✅ 自动核验完成！\n"
                f"📊 总记录: {total_lines}\n"
                f"✅ 保留记录: {kept_lines}\n"
                f"❌ 删除记录: {removed_lines}\n"
                f"📁 JSONL 已更新: {jsonl_file_path}"
            )

            if missing_images:
                result += f"\n📋 缺失图片示例: {missing_images[:5]}..."

        elif mode == "interactive":
            # 交互模式：只返回统计信息，不修改文件
            result = (
                f"🔍 交互式核验统计：\n"
                f"📊 总记录: {total_lines}\n"
                f"✅ 有效记录: {kept_lines}\n"
                f"❌ 无效记录: {removed_lines}\n"
                f"📁 请人工检查缺失图片，然后选择是否执行自动清理\n"
                f"📋 缺失图片: {missing_images[:10]}..."  # 只显示前10个
            )

        return result

    except Exception as e:
        return f"❌ 核验失败: {str(e)}"


def manual_filter_jsonl(jsonl_file_path: str, keep_ids: list) -> str:
    """
    手动过滤 JSONL，只保留指定 ID 的条目。
    供交互模式后使用。
    """
    try:
        # 读取所有行
        with open(jsonl_file_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line.strip()) for line in f if line.strip()]

        # 过滤
        filtered_lines = []
        for line in lines:
            # 从 images 路径中提取 ID
            images = line.get("images", [])
            if images:
                img_filename = os.path.basename(images[0])  # 假设只有一个图片
                img_id = extract_image_number(img_filename)
                if img_id in keep_ids:
                    filtered_lines.append(line)

        # 写回
        with open(jsonl_file_path, "w", encoding="utf-8") as f:
            for item in filtered_lines:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        return f"✅ 手动过滤完成！保留 {len(filtered_lines)} 条记录"

    except Exception as e:
        return f"❌ 手动过滤失败: {str(e)}"
