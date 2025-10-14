import os
import pandas as pd

def check_columns(file_path: str) -> str:
    """
    检查 Parquet 文件的结构是否符合预期。
    
    预期结构：
      - 必须包含 'text' 列（字符串，LaTeX 公式）
      - 必须包含 'image' 列（字典，含 'bytes' 或 'path' 等）
    
    Args:
        file_path (str): 上传的 .parquet 文件路径
    
    Returns:
        str: 格式化的检查报告
    """
    try:
        # 检查文件扩展名
        if not file_path.endswith('.parquet'):
            return "❌ 仅支持 .parquet 文件！请上传 Parquet 格式数据。"

        # 读取 Parquet
        df = pd.read_parquet(file_path)
        
        # 检查是否为空
        if df.empty:
            return "⚠️ 文件为空，无数据行。"

        # 检查必要列
        required_cols = {'text', 'image'}
        missing = required_cols - set(df.columns)
        if missing:
            return f"❌ 缺少必要列: {missing}. 当前列: {list(df.columns)}"

        # 获取第一行示例
        first_row = df.iloc[0]
        text_sample = first_row['text']
        image_sample = first_row['image']

        # 构建报告
        report = []
        report.append("✅ 列名检查通过！")
        report.append(f"📊 总行数: {len(df)}")
        report.append(f"📋 所有列: {list(df.columns)}")
        report.append("")
        report.append("🔍 text 列示例:")
        report.append(f"  类型: {type(text_sample).__name__}")
        report.append(f"  内容: {str(text_sample)[:200]}{'...' if len(str(text_sample)) > 200 else ''}")
        report.append("")
        report.append("🔍 image 列示例:")

        if isinstance(image_sample, dict):
            report.append("  类型: dict")
            report.append("  键值详情:")
            for key, value in image_sample.items():
                preview = str(value)[:100]
                if len(str(value)) > 100:
                    preview += "..."
                report.append(f"    • {key}: {type(value).__name__} = {preview}")
        else:
            report.append(f"  类型: {type(image_sample).__name__}")
            preview = str(image_sample)[:150]
            if len(str(image_sample)) > 150:
                preview += "..."
            report.append(f"  内容: {preview}")

        return "\n".join(report)

    except Exception as e:
        return f"❌ 检查失败: {str(e)}"