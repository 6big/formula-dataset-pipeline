import json
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import re  
import os
from pylatexenc.latexwalker import LatexWalker, LatexWalkerError
from openai import OpenAI
import textwrap  # 添加textwrap模块用于文本换行
from concurrent.futures import ThreadPoolExecutor
import platform

#  强力设置中文字体（解决中文显示问题）
import platform
system = platform.system()
if system == 'Windows':
    # Windows 系统优先使用中文字体，并检查字体文件是否存在
    simhei_path = "C:/Windows/Fonts/simhei.ttf"
    if os.path.exists(simhei_path):
        matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'DejaVu Sans']
    else:
        # 如果黑体不存在，使用微软雅黑作为备选
        matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimSun', 'DejaVu Sans']
elif system == 'Darwin':  # macOS
    matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Heiti TC', 'DejaVu Sans']
else:  # Linux
    matplotlib.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 设置绘图风格
sns.set_style(style="whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)
pd.set_option('display.max_colwidth', 100)

#  书生 API 配置
SUPPORTED_MODELS = [
    "intern-latest",
    "intern-s1", 
    "intern-s1-mini",
    "internvl3.5-241b-a28b",
    "internvl3-latest",
    "internvl3-78b"
]
BASE_URL = "https://chat.intern-ai.org.cn/api/v1/"

#  输出目录配置（使用相对路径）
OUTPUT_DIR = "./worked_data/output"


def classify_formula_type(latex_str):
    """使用 match-case 重构公式类型分类(Python 3.10+)"""
    if not latex_str:
        return "其他"
    
    match True:
        #  修复：优先匹配更具体的模式（微分符号优先于分数）
        case _ if re.search(r"\\partial|\\nabla", latex_str):  # 微分符号优先
            return "微分"
        case _ if re.search(r"\\int", latex_str):
            return "积分"
        case _ if re.search(r"\\sum", latex_str):
            return "求和"
        case _ if re.search(r"\\frac", latex_str):  # 分数放后面
            return "分数"
        case _ if re.search(r"\\sqrt", latex_str):
            return "根式"
        case _ if re.search(r"\\lim", latex_str):
            return "极限"
        case _:
            return "其他"


def classify_formula_domain(latex_str):
    """按学术领域分类公式"""
    if not latex_str:
        return "Other"
    
    # 定义各学术领域的关键词
    domain_patterns = {
        "Calculus": r"\\int|\\partial|\\nabla|\\lim|\\infty|\\oint",
        "Algebra": r"\\sum|\\prod|\\sqrt|\\pm|\\mp|\\cdot|\\times",
        "Trigonometry": r"\\sin|\\cos|\\tan|\\cot|\\sec|\\csc|\\arcsin|\\arccos|\\arctan",
        "Statistics": r"\\sigma|\\mu|\\log|\\ln|\\exp|\\Pr|\\prob",
        "Linear Algebra": r"\\matrix|\\vmatrix|\\det|\\vec|\\cdot|\\times",
        "Set Theory": r"\\cup|\\cap|\\in|\\notin|\\subset|\\subseteq|\\forall|\\exists",
        "Logic": r"\\land|\\lor|\\lnot|\\Rightarrow|\\Leftrightarrow|\\forall|\\exists"
    }
    
    # 计算每个领域的匹配次数
    matches = {}
    for domain, pattern in domain_patterns.items():
        matches[domain] = len(re.findall(pattern, latex_str))
    
    # 返回匹配次数最多的领域，如果没有匹配则返回Other
    if any(matches.values()):
        return max(matches, key=matches.get)
    else:
        return "Other"


def generate_visualizations(df, output_dir):
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
    
    # 左图：公式结构分布（中文标签）
    type_counts = Counter(df["formula_type"])
    type_counts_clean = {k: v for k, v in type_counts.items() if v > 0}  # 过滤 0 值
    # 在饼图中明确指定字体属性，这是解决中文显示的最可靠方法
    if system == 'Windows':
        simhei_path = "C:/Windows/Fonts/simhei.ttf"
        if os.path.exists(simhei_path):
            import matplotlib.font_manager as fm
            font_prop = fm.FontProperties(fname=simhei_path)  # 使用黑体
        else:
            font_prop = None  # 回退到默认字体
    else:
        font_prop = None  # 非Windows系统使用默认字体设置
    
    if type_counts_clean:  # 确保有数据再绘制
        ax1.pie(
            type_counts_clean.values(), 
            labels=type_counts_clean.keys(), 
            autopct='%1.1f%%',
            # 明确指定字体属性
            textprops={'fontproperties': font_prop} if font_prop else {}
        )
        # 为标题也设置字体
        ax1.set_title("公式结构分布", fontproperties=font_prop if font_prop else None)
    else:
        ax1.text(0.5, 0.5, "无数据", ha='center', va='center')
        ax1.set_title("公式结构分布")
    
    # 右图：学术领域分布（英文标签）
    domain_counts = Counter(df["formula_domain"])
    domain_counts_clean = {k: v for k, v in domain_counts.items() if v > 0}  # 过滤 0 值
    if domain_counts_clean:  # 确保有数据再绘制
        ax2.pie(
            domain_counts_clean.values(), 
            labels=domain_counts_clean.keys(), 
            autopct='%1.1f%%'
        )
        ax2.set_title("学术领域分布", fontproperties=font_prop if font_prop else None)
    else:
        ax2.text(0.5, 0.5, "无数据", ha='center', va='center')
        ax2.set_title("学术领域分布")
    
    plt.tight_layout()
    type_dist_path = os.path.join(output_dir, "formula_type_dist.png")
    plt.savefig(type_dist_path, bbox_inches='tight', dpi=100)  # 确保完整保存
    plt.close()  # 关键：关闭画布，释放资源

    return ["latex_length_dist.png", "formula_type_dist.png"]


def call_ai_analysis(stats_dict, api_key, model):
    """调用 AI API（独立函数）"""
    # 验证模型是否支持
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"不支持的模型: {model}。支持的模型: {', '.join(SUPPORTED_MODELS)}")

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
            max_tokens=1500  # 限制输出长度
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"❌ 书生 API 调用失败: {e}")
        raise


def get_ai_analysis_report(stats_dict, api_key, model="intern-latest"):
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
        with open(html_path, 'r', encoding='utf-8') as f:
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
    to_parquet: bool = False, 
    use_ai: bool = True,
    ai_key: str = None,
    ai_model: str = None
):
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
    with open(input_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                
                #  修复：正确提取 messages 中 assistant 的 content
                assistant_content = ""
                for msg in item.get("messages", []):
                    if msg["role"] == "assistant":
                        assistant_content = msg["content"]
                        break  # 只取第一个 assistant 消息
                
                #  使用提取到的 LaTeX 内容
                latex_content = assistant_content
                
                # 提取特征
                latex_len = len(latex_content.split())
                formula_type = classify_formula_type(latex_content) 
                formula_domain = classify_formula_domain(latex_content)
                records.append({
                    "idx": idx,
                    "latex": latex_content,
                    "latex_len": latex_len,
                    "formula_type": formula_type,
                    "formula_domain": formula_domain
                })
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
        percentage = count/total if total > 0 else 0
        print(f"  - {type_name}: {count} ({percentage:.1%})")
    
    print(f"\n📈 学术领域分布:")
    for domain_name, count in domain_counts.most_common():
        # 避免除以0错误
        percentage = count/total if total > 0 else 0
        print(f"  - {domain_name}: {count} ({percentage:.1%})")
    
    # 可视化部分（输出到统一目录）
    print("\n🖼️ 生成可视化图表...")
    
    # 准备AI分析的数据
    stats_dict = {
        'total_samples': total,
        'avg_length': avg_len,
        'formula_type_counts': type_counts,
        'formula_domain_counts': domain_counts
    }
    
    # 先在主线程生成图表
    viz_files = generate_visualizations(df, OUTPUT_DIR)
    
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
                future_ai = executor.submit(call_ai_analysis, stats_dict, final_api_key, final_model)
                
                # 等待结果
                try:
                    ai_report = future_ai.result()       # 阻塞直到 AI 返回
                    print(f"\n📋 AI 分析报告:\n{ai_report}")
                except Exception as e:
                    print(f"❌ AI分析任务执行失败: {e}")
    
    # 移除 AI 报告中的 Markdown 格式符号并按每行56个字符换行
    if ai_report:
        # 移除 ### 和 ** 符号
        ai_report = ai_report.replace("#", "").replace("*", "")
        
        # 按每行56个字符进行换行处理
        wrapped_lines = []
        for line in ai_report.split('\n'):
            # 如果行非空且长度超过56个字符，则按56个字符分割
            if line and len(line) > 56:
                # 使用textwrap.fill进行自动换行
                wrapped_line = textwrap.fill(line, width=56)
                wrapped_lines.append(wrapped_line)
            else:
                wrapped_lines.append(line)
        ai_report = '\n'.join(wrapped_lines)
    
    # 可选：生成 HTML 报告（输出到统一目录）
    report_html = ""  # 初始化报告字符串
    if output_html and use_ai and final_api_key:
        # 如果输出路径不是绝对路径，放在 OUTPUT_DIR 下
        if not os.path.isabs(output_html):
            output_html = os.path.join(OUTPUT_DIR, output_html)
        
        with open(output_html, 'w', encoding='utf-8') as f:
            f.write(f"""
            <h3>数据集AI分析报告</h3>
            <pre style="white-space: pre-wrap; word-wrap: break-word;">{ai_report}</pre>
            <h3> AI生成的内容可能有误 , 请结合实际情况进行判断。</h3>
            """)
        print(f"📄 已生成 HTML 报告: {output_html}")
        
        # 新增：读取并修正刚生成的 HTML 报告
        report_html = _read_and_fix_html_report(output_html)
    
    return df, report_html  # 返回 DataFrame 和 HTML 字符串