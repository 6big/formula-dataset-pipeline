#dataset环境下运行
import pandas as pd
import os
import json
from PIL import Image
import io
import random

# 添加 LaTeX 校验函数
from pylatexenc.latexwalker import LatexWalker, LatexWalkerError

def is_valid_latex(latex_str):
    """
    检查 LaTeX 字符串是否基本合法
    """
    if not isinstance(latex_str, str) or not latex_str.strip():
        return False
    try:
        # 尝试解析 LaTeX
        walker = LatexWalker(latex_str.strip())
        walker.get_latex_nodes()
        return True
    except (LatexWalkerError, Exception) as e:
        # print(f"LaTeX 解析失败: {e}")  # 可选：打印错误
        return False

def save_as_png_high_quality(image_bytes, output_path):
    """
    将图片高质量转换为PNG格式
    """
    try:
        # 打开原始图片
        image = Image.open(io.BytesIO(image_bytes))
            
        # 高质量PNG保存参数
        png_kwargs = {
            'format': 'PNG',
            'optimize': True,
            'compress_level': 1
        }
        
        # 保存为PNG
        image.save(output_path, **png_kwargs)
        return True, image.size, image.mode
        
    except Exception as e:
        print(f"转换PNG失败: {e}")
        return False, None, None

# ========== 配置区 ==========
PARQUET_PATH = "./origin_data/test-00000-of-00001.parquet"
OUTPUT_DIR = "./transfer_data"
FIXED_USER_PROMPT = "<image>请根据图片中的公式生成对应的 latex 公式文本"
TEXT_COLUMN = "text"
IMAGE_COLUMN = "image"
# 采样配置
TOTAL_RECORDS = 7631
SAMPLE_INTERVAL = 20  # 每110条抽取一次
TARGET_SAMPLES = 310    # 目标样本数
# ===========================

# 创建输出目录
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/images", exist_ok=True)

# 读取Parquet文件
print("正在读取Parquet文件...")
df = pd.read_parquet(PARQUET_PATH)
print(f"共找到 {len(df)} 条记录")

# ========== 采样逻辑 ==========
# 计算采样点
sample_points = []
for i in range(0, min(len(df), TOTAL_RECORDS), SAMPLE_INTERVAL):
    # 在每个间隔内随机选择一个点
    start_idx = i
    end_idx = min(i + SAMPLE_INTERVAL - 1, len(df) - 1)
    if start_idx <= end_idx:
        random_idx = random.randint(start_idx, end_idx)
        if random_idx < len(df):  # 确保索引有效
            sample_points.append(random_idx)

# 限制样本数量
sample_points = sample_points[:TARGET_SAMPLES]
print(f"采样点: {sample_points[:10]}... (共{len(sample_points)}个)")

# ========== 处理采样数据 ==========
jsonl_lines = []
successful_count = 0

for sample_idx, original_idx in enumerate(sample_points):
    try:
        # 获取指定行的数据
        row = df.iloc[original_idx]
        
        # 获取数据
        user_content = FIXED_USER_PROMPT
        assistant_content = getattr(row, TEXT_COLUMN)
        image_dict = getattr(row, IMAGE_COLUMN)
        image_bytes = image_dict.get('bytes', b'')

        # >>>>>>>> 新增：校验 LaTeX 格式 <<<<<<<<
        if not is_valid_latex(assistant_content):
            print(f"⚠️ 第 {original_idx} 条记录 LaTeX 格式无效，跳过采样")
            continue
        # >>>>>>>> 结束新增 <<<<<<<<

        if not image_bytes:
            print(f"⚠️ 第 {original_idx} 条记录没有图片数据")
            continue

        # 使用采样索引命名文件
        image_filename = f"images/image_{sample_idx:03d}.png"
        full_image_path = os.path.join(OUTPUT_DIR, image_filename)

        # 转换为高质量PNG
        success, size, mode = save_as_png_high_quality(image_bytes, full_image_path)
        
        if success:
            print(f"✅ 转换PNG {sample_idx:03d} (原索引{original_idx}): {size} {mode}")
            successful_count += 1
            
            # 构建JSON对象
            json_obj = {
                "messages": [
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": assistant_content}
                ],
                "images": [image_filename]
            }
            jsonl_lines.append(json.dumps(json_obj, ensure_ascii=False))
        else:
            print(f"❌ 转换失败 {sample_idx:03d} (原索引{original_idx})")

        # 显示进度
        if (sample_idx + 1) % 10 == 0:
            print(f"进度: {sample_idx + 1}/{len(sample_points)} (成功: {successful_count})")

    except Exception as e:
        print(f"❌ 处理第 {sample_idx} 个样本(原索引{original_idx})时出错: {e}")
        continue

# 写入JSONL文件
jsonl_path = os.path.join(OUTPUT_DIR, "output.jsonl")
with open(jsonl_path, "w", encoding="utf-8") as f:
    f.write("\n".join(jsonl_lines))

print("\n" + "="*50)
print("✅ 转换完成！")
print(f"📊 成功处理 {successful_count}/{len(sample_points)} 条记录")
print(f"📊 实际采样率: {len(sample_points)}/{len(df)} = {len(sample_points)/len(df)*100:.2f}%")
print(f"📁 图片已保存至: {os.path.abspath(os.path.join(OUTPUT_DIR, 'images'))}")
print(f"📄 JSONL 文件已生成: {os.path.abspath(jsonl_path)}")