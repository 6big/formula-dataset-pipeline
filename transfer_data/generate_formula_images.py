import json
import matplotlib
matplotlib.use('Agg')  # 添加这行，确保在无GUI环境下也能生成图片
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import re
from matplotlib import rcParams


# 设置数学字体
rcParams['font.family'] = 'serif'
rcParams['mathtext.fontset'] = 'cm'  # 使用Computer Modern字体渲染数学公式

def extract_content_annotations(jsonl_file):
    """
    从jsonl文件中提取所有role为assistant的content内容
    """
    content_annotations = []
    
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                # 处理嵌套的messages结构
                if 'messages' in data:
                    for message in data['messages']:
                        if 'role' in message and message['role'] == 'assistant' and 'content' in message:
                            content_annotations.append(message['content'])
                # 兼容原来的扁平结构
                elif 'role' in data and data['role'] == 'assistant' and 'content' in data:
                    content_annotations.append(data['content'])
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
                continue
    
    return content_annotations

def fix_latex_syntax(formula_text):
    """
    修复常见的LaTeX语法错误
    """
    # 修复 \frac 1 {denominator} -> \frac{1}{denominator}
    formula_text = re.sub(r'\\frac\s+1\s*\{', r'\\frac{1}{', formula_text)
    formula_text = re.sub(r'\\frac\s+(-\d+)\s*\{', r'\\frac{\1}{', formula_text)
    formula_text = re.sub(r'\\frac\s+(\d+)\s*\{', r'\\frac{\1}{', formula_text)
    
    # 修复数组环境
    formula_text = re.sub(r'\\begin\{array\}\s*\{([^}]+)\}', r'\\begin{array}{\1}', formula_text)
    
    # 修复换行符
    formula_text = re.sub(r'\\\\\s*\\', r'\\\\', formula_text)
    
    # 修复 \mathrm{w h e r e} -> \mathrm{where}
    formula_text = re.sub(r'\\mathrm\s*\{w\s+h\s+e\s+r\s+e\}', r'\\mathrm{where}', formula_text)
    
    # 修复 \partial 被转义的问题
    formula_text = re.sub(r'{\\backslash partial', r'{\\partial', formula_text)
    formula_text = re.sub(r'\\backslash partial', r'\\partial', formula_text)
    
    # 清理多余空格和换行
    formula_text = ' '.join(formula_text.split())
    
    # 去除末尾逗号和多余标点
    formula_text = formula_text.rstrip('.,;').strip()
    
    return formula_text

def validate_latex_syntax(formula_text):
    """
    验证LaTeX语法是否正确
    """
    try:
        # 简单的语法检查
        if not formula_text or not isinstance(formula_text, str):
            return False
            
        # 检查括号匹配
        bracket_count = 0
        for char in formula_text:
            if char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count < 0:
                    return False
        
        if bracket_count != 0:
            return False
            
        # 检查常见的LaTeX命令格式
        commands = ['\\frac', '\\sqrt', '\\sum', '\\int', '\\lim', '\\infty', '\\partial']
        for cmd in commands:
            if cmd in formula_text:
                # 检查命令后面是否有必要的参数
                pattern = rf'{cmd}\s*(?:\{{[^}}]*\}})?\s*(?:\{{[^}}]*\}})?'
                # 这里简化处理，主要检查基本格式
                break
                
        return True
    except Exception:
        return False

def generate_formula_image(formula_text, output_path, index):
    """
    使用matplotlib生成公式图片
    """
    # 修复LaTeX语法
    formula_text = fix_latex_syntax(formula_text)
    
    # 清理公式文本
    formula_text = formula_text.strip().rstrip(',')
    
    # 处理多行公式和多余空格
    formula_text = ' '.join(formula_text.split())
    
    # 验证LaTeX语法
    if not validate_latex_syntax(formula_text):
        print(f"❌ LaTeX语法验证失败: {formula_text[:50]}...")
        return None
    
    # 创建图形和轴
    fig, ax = plt.subplots(figsize=(5, 3))  # 增加一些宽度和高度
    
    # 移除坐标轴
    ax.set_axis_off()
    
    # 包装在数学模式中
    display_text = f'${formula_text}$'
    
    # 显示文本，添加错误处理
    try:
        ax.text(0.5, 0.5, display_text, fontsize=20, ha='center', va='center')
    except Exception as e:
        print(f"❌ LaTeX渲染错误，使用纯文本显示: {str(e)[:50]}...")
        # 如果LaTeX渲染失败，尝试显示为普通文本
        ax.text(0.5, 0.5, formula_text, fontsize=16, ha='center', va='center')
        # 返回None表示渲染失败
        plt.close(fig)
        return None
    
    # 保存图片，设置透明背景
    image_path = os.path.join(output_path, f'image_{index:03d}.png')
    try:
        plt.savefig(image_path, dpi=300, bbox_inches='tight', pad_inches=0.1, transparent=True)
        plt.close(fig)
        return image_path
    except Exception as e:
        print(f"❌ 保存图片失败 {image_path}: {e}")
        plt.close(fig)
        return None

def create_validated_jsonl(original_jsonl_path, output_jsonl_path, valid_indices):
    """
    创建只包含成功生成图片的记录的新的jsonl文件
    """
    valid_records = []
    
    with open(original_jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                data = json.loads(line)
                # 检查当前行是否在有效索引列表中
                if line_num - 1 in valid_indices:
                    valid_records.append(data)
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
                continue
    
    # 写入新的jsonl文件
    with open(output_jsonl_path, 'w', encoding='utf-8') as f:
        for record in valid_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"✅ 已创建新的jsonl文件: {output_jsonl_path}")
    print(f"📊 共包含 {len(valid_records)} 条有效记录")

def main():
    # 输入文件路径
    input_file = r'd:\pythonproject\dataset_convert\transfer_data\output.jsonl'
    
    # 输出图片目录
    output_dir = r'd:\pythonproject\dataset_convert\transfer_data\generate_images'
    os.makedirs(output_dir, exist_ok=True)
    
    # 创建保存有效索引的文件
    valid_indices_file = os.path.join(os.path.dirname(output_dir), 'valid_indices.txt')
    
    # 提取content标注
    content_annotations = extract_content_annotations(input_file)
    print(f"共提取到 {len(content_annotations)} 条公式内容")
    
    # 显示前几个公式内容用于调试
    for i, content in enumerate(content_annotations[:3]):
        print(f"公式 {i}: {content[:100]}...")
    
    # 生成公式图片并记录成功索引
    success_indices = []
    success_count = 0
    
    for i, content in enumerate(content_annotations):
        try:
            image_path = generate_formula_image(content, output_dir, i)
            if image_path:
                success_indices.append(i)
                print(f"✅ 成功生成: {image_path}")
                success_count += 1
            else:
                print(f"❌ 生成失败: 公式 {i}")
        except Exception as e:
            print(f"❌ 错误生成公式 {i}: {e}")
    
    print(f"\n🎉 成功生成了 {success_count} 张公式图片")
    print(f"📋 有效索引: {success_indices}")
    
    # 保存有效索引到文件
    with open(valid_indices_file, 'w', encoding='utf-8') as f:
        for idx in success_indices:
            f.write(f"{idx}\n")
    
    print(f"✅ 已保存有效索引到: {valid_indices_file}")
    
    # 创建只包含成功生成图片的记录的新jsonl文件
    output_jsonl_path = os.path.join(os.path.dirname(output_dir), 'best_output.jsonl')
    create_validated_jsonl(input_file, output_jsonl_path, set(success_indices))
    
    print("\n" + "="*50)
    print("✅ 处理完成！")
    print(f"📊 总共处理: {len(content_annotations)} 条记录")
    print(f"📊 成功生成: {success_count} 张图片")
    print(f"📊 有效记录: {len(success_indices)} 条")


if __name__ == "__main__":
    main()