#dataset环境下运行
import pandas as pd
df = pd.read_parquet("D:\pythonproject\dataset_convert\origin_data/test-00000-of-00001.parquet")  # 替换为实际文件名
print("✅ 列名列表:", df.columns.tolist())
print("\n🔍 text列示例类型:", type(df['text'].iloc[0]))
print("🔍 text列示例内容:", df['text'].iloc[0])
print("\n🔍 image列示例类型:", type(df['image'].iloc[0]))
print("🔍 image列示例内容:", df['image'].iloc[0])

# 添加以下代码查看image字典的详细结构
image_data = df['image'].iloc[0]
if isinstance(image_data, dict):
    print("\n🔍 image字典键值:")
    for key, value in image_data.items():
        print(f"  键: {key}, 类型: {type(value)}, 内容预览: {str(value)[:100]}...")