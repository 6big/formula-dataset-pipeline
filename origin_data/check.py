import pandas as pd
import os


def check_columns(file_path: str) -> str:
    """
    检查 Parquet 文件的基本结构信息。

    Args:
        file_path (str): 上传的 .parquet 文件路径

    Returns:
        str: 格式化的检查报告
    """
    try:
        # 检查文件扩展名
        if not file_path.endswith(".parquet"):
            return "❌ 仅支持 .parquet 文件！请上传 Parquet 格式数据。"

        # 读取 Parquet
        df = pd.read_parquet(file_path)

        # 检查是否为空
        if df.empty:
            return "⚠️ 文件为空，无数据行。"

        # 获取列信息
        columns = list(df.columns)

        # 获取第一行示例（如果有的话）
        first_row = df.iloc[0] if len(df) > 0 else None

        # 构建报告
        report = []
        report.append("✅ Parquet 文件读取成功！")
        report.append(f"📊 总行数: {len(df)}")
        report.append(f"📋 列数量: {len(columns)}")
        report.append(f"📋 列名列表: {columns}")
        
        if first_row is not None:
            report.append("")
            report.append("🔍 各列数据示例:")
            for col in columns:
                sample_value = first_row[col]
                report.append(f"  列 '{col}':")
                report.append(f"    类型: {type(sample_value).__name__}")
                if isinstance(sample_value, dict):
                    report.append("    值详情:")
                    for key, value in sample_value.items():
                        preview = str(value)[:100]
                        if len(str(value)) > 100:
                            preview += "..."
                        report.append(f"      • {key}: {type(value).__name__} = {preview}")
                else:
                    preview = str(sample_value)[:200]
                    if len(str(sample_value)) > 200:
                        preview += "..."
                    report.append(f"    值预览: {preview}")

        return "\n".join(report)

    except Exception as e:
        return f"❌ 检查失败: {str(e)}"