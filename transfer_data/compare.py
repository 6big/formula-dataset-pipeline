import json
import os
import re

def extract_image_number(filename):
    """
    从文件名中提取3位数字编号
    
    Args:
        filename: 文件名，如 "image_001.png"
    
    Returns:
        str: 3位数字编号，如 "001"
    """
    match = re.search(r'image_(\d{3})\.png', filename)
    if match:
        return match.group(1)
    return None

def clean_jsonl_by_image_numbers(jsonl_file_path, images_folder_path):
    """
    根据图片编号清理jsonl文件，只保留图片实际存在的行
    
    Args:
        jsonl_file_path: jsonl文件路径
        images_folder_path: 图片文件夹路径
    """
    # 获取所有实际存在的图片编号
    existing_image_numbers = set()
    for filename in os.listdir(images_folder_path):
        image_number = extract_image_number(filename)
        if image_number:
            existing_image_numbers.add(image_number)
    
    print(f"文件夹中找到 {len(existing_image_numbers)} 个图片文件")
    
    # 用于临时存储处理后的内容
    cleaned_lines = []
    
    # 统计信息
    total_lines = 0
    kept_lines = 0
    removed_lines = 0
    
    # 读取并处理jsonl文件
    with open(jsonl_file_path, 'r', encoding='utf-8') as file:
        for line in file:
            total_lines += 1
            try:
                # 解析JSON行
                data = json.loads(line.strip())
                
                # 获取图片路径
                images = data.get('images', [])
                
                # 检查所有图片编号是否都存在
                all_images_exist = True
                for image_path in images:
                    # 从路径中提取文件名
                    image_filename = os.path.basename(image_path)
                    image_number = extract_image_number(image_filename)
                    
                    if not image_number or image_number not in existing_image_numbers:
                        all_images_exist = False
                        break
                
                # 如果所有图片都存在，则保留该行
                if all_images_exist and images:
                    cleaned_lines.append(line)
                    kept_lines += 1
                else:
                    removed_lines += 1
                    
            except json.JSONDecodeError:
                # 如果JSON解析失败，删除该行
                removed_lines += 1
    
    # 将清理后的内容写回原文件
    with open(jsonl_file_path, 'w', encoding='utf-8') as file:
        file.writelines(cleaned_lines)
    
    print(f"处理完成:")
    print(f"  总行数: {total_lines}")
    print(f"  保留行数: {kept_lines}")
    print(f"  删除行数: {removed_lines}")

if __name__ == "__main__":
    # 定义路径
    jsonl_file = r"d:\pythonproject\dataset_convert\transfer_data\best_output.jsonl"
    images_folder = r"d:\pythonproject\dataset_convert\transfer_data\generate_images"
    
    # 执行清理
    clean_jsonl_by_image_numbers(jsonl_file, images_folder)