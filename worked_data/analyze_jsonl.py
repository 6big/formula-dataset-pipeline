import json
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import re
import os
from openai import OpenAI
import textwrap  # 添加textwrap模块用于文本换行
from concurrent.futures import ThreadPoolExecutor
import platform
from typing import Tuple, List, Dict, Any

# 设置绘图风格
sns.set_style(style="whitegrid")
plt.rcParams["figure.figsize"] = (10, 6)
pd.set_option("display.max_colwidth", 100)

#  书生 API 配置
SUPPORTED_MODELS = [
    "intern-latest",
    "intern-s1",
    "intern-s1-mini",
    "internvl3.5-241b-a28b",
    "internvl3-latest",
    "internvl3-78b",
]
BASE_URL = "https://chat.intern-ai.org.cn/api/v1/"

#  输出目录配置（使用相对路径）
OUTPUT_DIR = "./worked_data/output"


# 公式结构分类的正则常量（提升可读性与可维护性）
FORMULA_TYPE_PATTERNS = [
    ("微分", r"\\partial|\\nabla"),
    ("积分", r"\\int"),
    ("求和", r"\\sum|\\prod"),
    ("矩阵/分段", r"\\begin\{(?:matrix|pmatrix|bmatrix|vmatrix|cases)\}"),
    ("二项式", r"\\binom|\\choose"),
    ("分数", r"\\frac"),
    ("根式", r"\\sqrt"),
    ("极限", r"\\lim"),
    ("不等式", r"\\ge|\\le|\\ne|\\approx|\\ll|\\gg|\\equiv"),
]


def classify_formula_type(latex_str: str) -> str:
    """根据 LaTeX 字符串内容判断公式的主要结构类型。

    分类优先级从高到低：
        微分 > 积分 > 求和 > 矩阵/分段 > 二项式 > 分数 > 根式 > 极限 > 不等式 > 上下标。
    若不匹配任何已知模式，则返回"其他"。

    Args:
        latex_str: 输入的 LaTeX 公式字符串。

    Returns:
        公式类型字符串，如 "微分", "矩阵/分段", "不等式" 等。
    """
    if not latex_str:
        return "其他"

    # 按优先级顺序检测，返回首个匹配的类别
    for type_name, pattern in FORMULA_TYPE_PATTERNS:
        if re.search(pattern, latex_str):
            return type_name

    # 如果没有匹配任何模式，尝试更宽松的匹配
    # 检查是否包含数学表达式的基本特征
    if re.search(r"[a-zA-Z]", latex_str) or re.search(r"[+\-*/=<>]", latex_str):
        return "代数式"

    return "其他"


# 学术领域分类的正则常量
FORMULA_DOMAIN_PATTERNS = [
    ("统计学", r"\\Pr|\\prob|\\mathbb\{P\}|\\binom|\\mathcal\{N\}"),
    ("线性代数", r"\\vec|\\det|\\begin\{(?:matrix|pmatrix)\}"),
    ("逻辑学", r"\\land|\\lor|\\lnot|\\forall|\\exists|\\Rightarrow"),
    ("集合论", r"\\cup|\\cap|\\in|\\subset|\\emptyset"),
    ("三角学", r"\\sin|\\cos|\\tan|\\arcsin|\\arccos|\\arctan"),
    ("微积分", r"\\int|\\partial|\\lim|\\infty|\\sum|\\prod"),
    ("代数", r"=|\\sqrt|\\pm|\\cdot|\\frac|\\ge|\\le|\\ne"),
]


def classify_formula_domain(latex_str: str) -> str:
    """根据 LaTeX 字符串判断公式所属学术领域。

    优先匹配高特异性领域，无匹配时默认归入 "代数"。

    Args:
        latex_str: 输入的 LaTeX 公式字符串。

    Returns:
        领域字符串，如 "微积分", "线性代数", "代数" 等。
    """
    if not latex_str:
        return "Other"

    # 按特异性降序匹配（高特异性优先）
    for domain_name, pattern in FORMULA_DOMAIN_PATTERNS:
        if re.search(pattern, latex_str, re.IGNORECASE):
            return domain_name

    # 如果没有匹配任何模式，尝试更宽松的匹配
    # 检查是否包含数学表达式的基本特征
    if re.search(r"[a-zA-Z]", latex_str) or re.search(r"[+\-*/=<>]", latex_str):
        return "代数"

    return "Other"


# 添加英文标签映射字典，解决Linux系统中文显示问题
FORMULA_TYPE_ENGLISH = {
    "微分": "Differential",
    "积分": "Integral",
    "求和": "Summation",
    "矩阵/分段": "Matrix/Piecewise",
    "二项式": "Binomial",
    "分数": "Fraction",
    "根式": "Radical",
    "极限": "Limit",
    "不等式": "Inequality",
    "代数式": "Algebraic",
    "其他": "Other"
}

FORMULA_DOMAIN_ENGLISH = {
    "统计学": "Statistics",
    "线性代数": "Linear Algebra",
    "逻辑学": "Logic",
    "集合论": "Set Theory",
    "三角学": "Trigonometry",
    "微积分": "Calculus",
    "代数": "Algebra",
    "其他": "Other"
}


def generate_visualizations(df: pd.DataFrame, output_dir: str) -> List[str]:
    """生成所有图表（独立函数）"""
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 如果数据框为空，直接返回
    if df.empty:
        print("⚠️ 数据为空，跳过图表生成")
        return []

    # 1. 响应长度分布直方图
    plt.figure(figsize=(10, 5))
    sns.histplot(df["latex_len"], bins=50, alpha=0.6, color="steelblue")
    plt.xlabel("LaTeX Length (tokens)")
    plt.ylabel("Frequency")
    plt.title("LaTeX Length Distribution")
    plt.tight_layout()
    length_dist_path = os.path.join(output_dir, "latex_length_dist.png")
    plt.savefig(length_dist_path)
    plt.close()  # 关键：关闭画布，释放资源

    # 2. 组合饼图（结构分类 + 领域分类）
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

    # 左图：公式结构分布（英文标签）
    type_counts = Counter(df["formula_type"])
    type_counts_clean = {k: v for k, v in type_counts.items() if v > 0}  # 过滤 0 值

    if type_counts_clean:  # 确保有数据再绘制
        # 使用英文标签替代中文标签
        english_labels = [FORMULA_TYPE_ENGLISH.get(label, label) for label in type_counts_clean.keys()]
        ax1.pie(
            type_counts_clean.values(),
            labels=english_labels,
            autopct="%1.1f%%",
        )
        ax1.set_title("Formula Structure Distribution")
    else:
        ax1.text(0.5, 0.5, "No Data", ha="center", va="center")
        ax1.set_title("Formula Structure Distribution")

    # 右图：学术领域分布（英文标签）
    domain_counts = Counter(df["formula_domain"])
    domain_counts_clean = {k: v for k, v in domain_counts.items() if v > 0}  # 过滤 0 值
    if domain_counts_clean:  # 确保有数据再绘制
        # 使用英文标签替代中文标签
        english_labels = [FORMULA_DOMAIN_ENGLISH.get(label, label) for label in domain_counts_clean.keys()]
        ax2.pie(
            domain_counts_clean.values(),
            labels=english_labels,
            autopct="%1.1f%%",
        )
        ax2.set_title("Academic Domain Distribution")
    else:
        ax2.text(0.5, 0.5, "No Data", ha="center", va="center")
        ax2.set_title("Academic Domain Distribution")

    plt.tight_layout()
    type_dist_path = os.path.join(output_dir, "formula_type_dist.png")
    plt.savefig(type_dist_path, bbox_inches="tight", dpi=100)  # 确保完整保存
    plt.close()  # 关键：关闭画布，释放资源

    return ["latex_length_dist.png", "formula_type_dist.png"]


def call_ai_analysis(stats_dict: Dict[str, Any], api_key: str, model: str) -> str:
    """调用 AI API（独立函数）"""
    # 验证模型是否支持
    if model not in SUPPORTED_MODELS:
        raise ValueError(
            f"不支持的模型: {model}。支持的模型: {', '.join(SUPPORTED_MODELS)}"
        )

    # 构建 AI 提示词
    prompt = f"""
    你是一个专业的数据集分析专家。请根据以下数据集统计信息，生成一份简短凝练的结构化分析报告。

    数据集统计信息：
    - 总样本数: {stats_dict['total_samples']}
    - 平均长度: {stats_dict['avg_length']:.1f} tokens
    - 公式结构分布: {dict(stats_dict['formula_type_counts'])}
    - 学术领域分布: {dict(stats_dict['formula_domain_counts'])}

    请按以下结构输出分析报告：
    1. 数据质量评估：评价数据集的整体质量
    2. 主要发现：指出数据集的关键特征，包括公式结构和学术领域的分布情况
    3. 潜在问题：识别可能存在的问题
    4. 改进建议：提供具体的优化建议
    5. 适用场景：推荐适合的应用场景

    要求语言专业、简洁、有建设性。
    """

    try:
        # 初始化书生客户端
        client = OpenAI(
            api_key=api_key,
            base_url=BASE_URL,
        )

        # 调用书生 API
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=1500,  # 限制输出长度
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"❌ 书生 API 调用失败: {e}")
        raise


def get_ai_analysis_report(
    stats_dict: Dict[str, Any], api_key: str, model: str = "intern-latest"
) -> str:
    """
    使用书生 API 生成分析报告
    stats_dict: 包含统计信息的字典
    api_key: 书生 API Token
    model: 书生模型名称
    """
    return call_ai_analysis(stats_dict, api_key, model)


def _read_and_fix_html_report(html_path: str) -> str:
    """
    读取 HTML 报告文件，并修正其中的图片路径，使其能在 Gradio 中正确显示。

    Args:
        html_path: HTML 报告的文件路径。

    Returns:
        修正后的 HTML 字符串。
    """
    if not os.path.exists(html_path):
        return "<p>❌ 未找到 HTML 报告文件。</p>"

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        #  修正图片路径：将 src="xxx.png" 替换为 src="./worked_data/output/xxx.png"
        # 使用正则表达式匹配所有 img 标签的 src 属性
        def replace_img_src(match):
            filename = match.group(1)
            return f'src="./worked_data/output/{filename}"'

        fixed_html = re.sub(r'src="([^"]+\.png)"', replace_img_src, html_content)
        return fixed_html

    except Exception as e:
        return f"<p>❌ 读取或修正 HTML 报告时出错: {str(e)}</p>"


def analyze_jsonl(
    input_path: str,
    output_html: str = None,
    use_ai: bool = True,
    ai_key: str = None,
    ai_model: str = None,
) -> Tuple[pd.DataFrame, str]:
    """
    分析 JSONL 数据集，可选导出为 Parquet 和 AI 分析
     安全保证：只读原始文件，不修改任何数据
     输出路径：统一在 ./worked_data/output/ 目录下
     支持书生 API：兼容 OpenAI SDK

    Returns:
        tuple: (df, report_html)
            - df: 分析结果的 DataFrame。
            - report_html: 修正后的 HTML 报告字符串，可直接用于前端渲染。
    """
    print(f"🔍 开始分析 JSONL 文件: {input_path}")

    #  安全检查：确保输入文件存在且为只读
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    #  确保输出目录存在（使用相对路径）
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 加载数据（只读模式）
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            try:
                item = json.loads(line)

                # 尝试多种方式提取 LaTeX 内容
                latex_content = ""

                # 方式1: 从 messages 数组中提取 assistant 的 content
                if "messages" in item and isinstance(item["messages"], list):
                    for msg in item["messages"]:
                        if msg.get("role") == "assistant":
                            latex_content = msg.get("content", "")
                            break

                # 方式2: 直接从 latex 或 formula 字段提取
                if not latex_content:
                    latex_content = item.get("latex", item.get("formula", ""))

                # 方式3: 从 content 字段提取
                if not latex_content:
                    latex_content = item.get("content", "")

                # 方式4: 如果item本身就是字符串，直接使用
                if not latex_content and isinstance(item, str):
                    latex_content = item

                # 如果还是没有内容，则跳过
                if not latex_content:
                    print(f"⚠️ 警告 (行 {idx+1}): 无法提取 LaTeX 内容，跳过该行")
                    continue

                # 提取特征
                latex_len = len(latex_content.split()) if latex_content else 0
                formula_type = classify_formula_type(latex_content)
                formula_domain = classify_formula_domain(latex_content)

                # 如果公式被分类为"其他"，打印一些调试信息
                if formula_type == "其他":
                    print(
                        f"⚠️ 警告 (行 {idx+1}): 公式被分类为'其他'，内容预览: {latex_content[:50]}..."
                    )

                records.append(
                    {
                        "idx": idx,
                        "latex": latex_content,
                        "latex_len": latex_len,
                        "formula_type": formula_type,
                        "formula_domain": formula_domain,
                    }
                )
            except json.JSONDecodeError as e:
                print(f"❌ JSON 解析错误 (行 {idx+1}): {e}")
                continue
            except Exception as e:
                print(f"❌ 解析错误 (行 {idx+1}): {e}")
                continue

    df = pd.DataFrame(records)
    print(f"✅ 加载完成: {len(df)} 条样本")

    # 统计摘要
    total = len(df)
    avg_len = df["latex_len"].mean() if total > 0 else 0

    print(f"\n📊 统计摘要:")
    print(f"  - 总样本数: {total}")
    print(f"  - 平均长度: {avg_len:.1f} tokens")

    # 公式类型分布
    type_counts = Counter(df["formula_type"])
    domain_counts = Counter(df["formula_domain"])
    print(f"\n📈 公式结构分布:")
    for type_name, count in type_counts.most_common():
        # 避免除以0错误
        percentage = count / total if total > 0 else 0
        print(f"  - {type_name}: {count} ({percentage:.1%})")

    print(f"\n📈 学术领域分布:")
    for domain_name, count in domain_counts.most_common():
        # 避免除以0错误
        percentage = count / total if total > 0 else 0
        print(f"  - {domain_name}: {count} ({percentage:.1%})")

    # 可视化部分（输出到统一目录）
    print("\n 🖼️ 生成可视化图表...")

    # 准备AI分析的数据
    stats_dict = {
        "total_samples": total,
        "avg_length": avg_len,
        "formula_type_counts": type_counts,
        "formula_domain_counts": domain_counts,
    }

    # 先在主线程生成图表
    generated_files = generate_visualizations(df, OUTPUT_DIR)
    print("✅ 可视化图表生成完成!")
    if generated_files:
        print(f"📊 生成的图表文件: {', '.join(generated_files)}")

    # AI 分析部分
    ai_report = ""
    final_api_key = ""
    final_model = ""

    # 在子线程中执行AI分析（避免阻塞主线程）
    if use_ai and ai_key:
        # 配置优先级：参数 > 环境变量 > 默认值
        final_api_key = ai_key or os.getenv("INTERN_API_KEY", "")
        final_model = ai_model or os.getenv("INTERN_MODEL", "intern-latest")

        if not final_api_key:
            print("❌ 未提供书生 API Key，跳过 AI 分析")
        else:
            print(f"\n🤖 正在使用书生模型 {final_model} 生成分析报告...")
            # 在子线程中执行AI分析
            with ThreadPoolExecutor(max_workers=1) as executor:
                future_ai = executor.submit(
                    call_ai_analysis, stats_dict, final_api_key, final_model
                )

                # 等待结果
                try:
                    ai_report = future_ai.result()  # 阻塞直到 AI 返回
                    print(f"\n📋 AI 分析报告:\n{ai_report}")
                except Exception as e:
                    print(f"❌ AI分析任务执行失败: {e}")

    # 移除 AI 报告中的 Markdown 格式符号并按每行56个字符换行
    if ai_report:
        # 移除 ### 和 ** 符号
        ai_report = ai_report.replace("#", "").replace("*", "")

        # 按每行56个字符进行换行处理
        wrapped_lines = []
        for line in ai_report.split("\n"):
            # 如果行非空且长度超过56个字符，则按56个字符分割
            if line and len(line) > 56:
                # 使用textwrap.fill进行自动换行
                wrapped_line = textwrap.fill(line, width=56)
                wrapped_lines.append(wrapped_line)
            else:
                wrapped_lines.append(line)
        ai_report = "\n".join(wrapped_lines)

    # 可选：生成 HTML 报告（输出到统一目录）
    report_html = ""  # 初始化报告字符串
    if output_html and use_ai and final_api_key:
        # 如果输出路径不是绝对路径，放在 OUTPUT_DIR 下
        if not os.path.isabs(output_html):
            output_html = os.path.join(OUTPUT_DIR, output_html)

        with open(output_html, "w", encoding="utf-8") as f:
            f.write(
                f"""
            <h3>数据集AI分析报告</h3>
            <pre style="white-space: pre-wrap; word-wrap: break-word;">{ai_report}</pre>
            <h3> AI生成的内容可能有误 , 请结合实际情况进行判断。</h3>
            """
            )
        print(f"📄 已生成 HTML 报告: {output_html}")

        # 新增：读取并修正刚生成的 HTML 报告
        report_html = _read_and_fix_html_report(output_html)

    return df, report_html  # 返回 DataFrame 和 HTML 字符串