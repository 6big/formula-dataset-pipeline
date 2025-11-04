import json
from pathlib import Path


def modify_image_paths(
    input_jsonl: str,
    output_jsonl: str,
    old_prefix: str = "images/",
    new_prefix: str = "enhanced/",
) -> str:
    """
    修改 JSONL 文件中的图片路径前缀

    Args:
        input_jsonl: 输入 JSONL 文件路径
        output_jsonl: 输出 JSONL 文件路径
        old_prefix: 旧路径前缀
        new_prefix: 新路径前缀

    Returns:
        str: 处理结果信息
    """
    try:
        input_path = Path(input_jsonl)
        output_path = Path(output_jsonl)

        if not input_path.exists():
            return f"❌ 输入文件不存在: {input_jsonl}"

        # 创建输出目录
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 统计信息
        total_lines = 0
        modified_lines = 0
        modified_count = 0

        with open(input_jsonl, "r", encoding="utf-8") as infile, open(
            output_jsonl, "w", encoding="utf-8"
        ) as outfile:

            for line in infile:
                total_lines += 1
                data = json.loads(line.strip())

                # 修改图片路径
                if "images" in data:
                    original_images = data["images"][:]
                    for i, image_path in enumerate(data["images"]):
                        if image_path.startswith(old_prefix):
                            new_path = image_path.replace(old_prefix, new_prefix)
                            data["images"][i] = new_path
                            modified_count += 1

                    if data["images"] != original_images:
                        modified_lines += 1

                # 写入修改后的行
                outfile.write(json.dumps(data, ensure_ascii=False) + "\n")

        return (
            f"✅ 路径修改完成！\n"
            f"📊 总记录: {total_lines}\n"
            f"🔄 已修改: {modified_lines} 行\n"
            f"🖼️  已更新: {modified_count} 个路径\n"
            f"📁 输入: {input_jsonl}\n"
            f"📁 输出: {output_jsonl}\n"
            f"🔧 从: {old_prefix}\n"
            f"🔧 到: {new_prefix}"
        )

    except Exception as e:
        return f"❌ 修改失败: {str(e)}"


def modify_image_paths_with_validation(
    input_jsonl: str,
    output_jsonl: str,
    old_prefix: str = "images/",
    new_prefix: str = "enhanced/",
    validate_paths: bool = False,  # 是否验证新路径是否存在
) -> str:
    """
    修改图片路径（带验证功能）
    """
    try:
        input_path = Path(input_jsonl)
        output_path = Path(output_jsonl)

        if not input_path.exists():
            return f"❌ 输入文件不存在: {input_jsonl}"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_lines = 0
        modified_lines = 0
        modified_count = 0
        invalid_paths = []  # 记录无效路径

        with open(input_jsonl, "r", encoding="utf-8") as infile, open(
            output_jsonl, "w", encoding="utf-8"
        ) as outfile:

            for line in infile:
                total_lines += 1
                data = json.loads(line.strip())

                if "images" in data:
                    original_images = data["images"][:]
                    for i, image_path in enumerate(data["images"]):
                        if image_path.startswith(old_prefix):
                            new_path = image_path.replace(old_prefix, new_prefix)
                            data["images"][i] = new_path
                            modified_count += 1

                            # 验证路径是否存在（可选）
                            if validate_paths:
                                full_path = Path(new_path)
                                if not full_path.exists():
                                    invalid_paths.append(new_path)

                    if data["images"] != original_images:
                        modified_lines += 1

                outfile.write(json.dumps(data, ensure_ascii=False) + "\n")

        result = (
            f"✅ 路径修改完成！\n"
            f"📊 总记录: {total_lines}\n"
            f"🔄 已修改: {modified_lines} 行\n"
            f"🖼️  已更新: {modified_count} 个路径\n"
            f"📁 输入: {input_jsonl}\n"
            f"📁 输出: {output_jsonl}\n"
            f"🔧 从: {old_prefix}\n"
            f"🔧 到: {new_prefix}\n"
        )

        if invalid_paths:
            result += f"⚠️  找不到的路径: {len(invalid_paths)} 个\n"
            if len(invalid_paths) <= 10:  # 只显示前10个
                result += f"   {invalid_paths}\n"
            else:
                result += f"   前10个: {invalid_paths[:10]}\n"

        return result

    except Exception as e:
        return f"❌ 修改失败: {str(e)}"


def batch_modify_paths(
    jsonl_files: list, old_prefix: str, new_prefix: str, output_dir: str = None
) -> str:
    """
    批量修改多个 JSONL 文件的路径
    """
    results = []

    for jsonl_file in jsonl_files:
        input_path = Path(jsonl_file)
        if output_dir:
            output_path = Path(output_dir) / input_path.name
        else:
            output_path = input_path.with_name(f"modified_{input_path.name}")

        result = modify_image_paths(
            input_jsonl=str(input_path),
            output_jsonl=str(output_path),
            old_prefix=old_prefix,
            new_prefix=new_prefix,
        )
        results.append(f"处理 {input_path.name}: {result}")

    return "\n".join(results)
