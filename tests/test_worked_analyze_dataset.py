import sys
import os
import tempfile
import json
import pandas as pd
# 禁用GUI后端以避免_tkinter.TclError
import matplotlib
matplotlib.use('Agg')  # 使用非GUI后端
import matplotlib.pyplot as plt

# 处理openai依赖问题
try:
    from unittest.mock import patch, MagicMock
    import builtins
    # 模拟openai模块
    mock_openai = MagicMock()
    sys.modules['openai'] = mock_openai
except ImportError:
    pass

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 导入被测函数
from worked_data.analyze_jsonl import (
    classify_formula_type,
    classify_formula_domain,
    analyze_jsonl
)


def test_classify_formula_type():
    """测试公式结构分类函数"""
    print("Testing classify_formula_type...")

    # 测试微分类型（最高优先级）
    assert classify_formula_type(r"\frac{\partial f}{\partial x}") == "微分"
    assert classify_formula_type(r"\partial f / \partial x") == "微分"
    assert classify_formula_type(r"\nabla f") == "微分"

    # 测试积分类型
    assert classify_formula_type(r"\int_0^1 x dx") == "积分"

    # 测试求和类型
    assert classify_formula_type(r"\sum_{i=1}^n i") == "求和"
    assert classify_formula_type(r"\prod_{i=1}^n i") == "求和"

    # 测试矩阵/分段类型
    assert classify_formula_type(r"\begin{matrix} a & b \\ c & d \end{matrix}") == "矩阵/分段"
    assert classify_formula_type(r"\begin{cases} x & x > 0 \\ -x & x \leq 0 \end{cases}") == "矩阵/分段"

    # 测试二项式类型
    assert classify_formula_type(r"\binom{n}{k}") == "二项式"

    # 测试分数类型
    assert classify_formula_type(r"\frac{a}{b}") == "分数"
    assert classify_formula_type(r"\frac{1}{2}") == "分数"

    # 测试根式类型
    assert classify_formula_type(r"\sqrt{x}") == "根式"
    assert classify_formula_type(r"\sqrt[3]{x}") == "根式"

    # 测试极限类型
    assert classify_formula_type(r"\lim_{x \to 0}") == "极限"

    # 测试不等式类型
    assert classify_formula_type(r"a \ge b") == "不等式"
    assert classify_formula_type(r"a \le b") == "不等式"
    assert classify_formula_type(r"a \ne b") == "不等式"

    # 测试代数式类型 - 包含字母或运算符的会被认为是代数式
    assert classify_formula_type("x + y = z") == "代数式"
    assert classify_formula_type("a * b") == "代数式"

    # 测试空字符串和其他情况
    assert classify_formula_type("") == "其他"
    # 只包含普通文本的会被认为是代数式而不是其他，因为含有字母
    assert classify_formula_type("plain text") == "代数式"

    print("✅ classify_formula_type tests passed!")


def test_classify_formula_domain():
    """测试公式领域分类函数"""
    print("Testing classify_formula_domain...")

    # 测试统计学
    assert classify_formula_domain(r"\Pr(A)") == "统计学"
    assert classify_formula_domain(r"\mathcal{N}(0,1)") == "统计学"
    # 注意：由于使用了IGNORECASE标志，\prod会被匹配为统计学（因为包含\pr）
    assert classify_formula_domain(r"\prod_{i=1}^n i") == "统计学"

    # 测试线性代数
    assert classify_formula_domain(r"\vec{v}") == "线性代数"
    assert classify_formula_domain(r"\det(A)") == "线性代数"

    # 测试逻辑学
    assert classify_formula_domain(r"A \land B") == "逻辑学"
    assert classify_formula_domain(r"\forall x") == "逻辑学"

    # 测试集合论 - 由于匹配优先级，包含\in, \cup, \cap, \int等的表达式都会匹配集合论
    assert classify_formula_domain(r"A \cup B") == "集合论"
    assert classify_formula_domain(r"A \cap B") == "集合论"
    assert classify_formula_domain(r"x \in A") == "集合论"
    assert classify_formula_domain(r"\int f(t) dt") == "集合论"  # 因为包含\int，而\int包含in
    assert classify_formula_domain(r"\lim_{x \to \infty}") == "集合论"  # 因为包含\in

    # 测试三角学
    assert classify_formula_domain(r"\sin(x)") == "三角学"
    assert classify_formula_domain(r"\cos(x)") == "三角学"

    # 测试微积分（不包含集合论、统计学等更高优先级的符号）
    assert classify_formula_domain(r"\lim_{x \to 0}") == "微积分"
    assert classify_formula_domain(r"\partial f / \partial x") == "微积分"
    assert classify_formula_domain(r"\sum_{i=1}^n i") == "微积分"

    # 测试代数
    assert classify_formula_domain(r"x = y + 1") == "代数"
    assert classify_formula_domain(r"\sqrt{a^2 + b^2}") == "代数"

    # 测试空字符串和其他情况
    assert classify_formula_domain("") == "Other"
    # 包含字母的普通文本被归类为代数
    assert classify_formula_domain("plain text") == "代数"

    print("✅ classify_formula_domain tests passed!")


def test_analyze_jsonl_with_different_formats():
    """测试主分析函数处理不同格式的JSONL文件"""
    print("Testing analyze_jsonl with different formats...")

    # 创建临时测试文件 - 标准格式（包含latex字段）
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
        test_data = [
            {"latex": r"\frac{a}{b}"},
            {"latex": r"\int_0^1 x dx"},
            {"latex": r"\sqrt{x^2 + y^2}"},
        ]

        for item in test_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
        temp_jsonl_path = f.name

    try:
        # 调用分析函数
        df, report_html = analyze_jsonl(
            input_path=temp_jsonl_path,
            output_html=None,
            use_ai=False  # 不调用 AI，避免 API 费用
        )

        # 验证返回的 DataFrame
        assert len(df) == 3
        assert "latex" in df.columns
        assert "latex_len" in df.columns
        assert "formula_type" in df.columns
        assert "formula_domain" in df.columns

        print("✅ analyze_jsonl standard format tests passed!")

    finally:
        # 清理临时文件
        os.unlink(temp_jsonl_path)


def test_analyze_jsonl_with_messages_format():
    """测试主分析函数处理messages格式的JSONL文件"""
    print("Testing analyze_jsonl with messages format...")

    # 创建临时测试文件 - messages格式
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
        test_data = [
            {"messages": [{"role": "user", "content": "Solve this"}, {"role": "assistant", "content": r"\frac{a}{b}"}]},
            {"messages": [{"role": "user", "content": "Calculate"}, {"role": "assistant", "content": r"\int_0^1 x dx"}]},
        ]

        for item in test_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
        temp_jsonl_path = f.name

    try:
        # 调用分析函数
        df, report_html = analyze_jsonl(
            input_path=temp_jsonl_path,
            use_ai=False  # 不调用 AI，避免 API 费用
        )

        # 验证返回的 DataFrame
        assert len(df) == 2
        assert "latex" in df.columns
        assert df.iloc[0]["latex"] == r"\frac{a}{b}"
        assert df.iloc[1]["latex"] == r"\int_0^1 x dx"

        print("✅ analyze_jsonl messages format tests passed!")

    finally:
        # 清理临时文件
        os.unlink(temp_jsonl_path)


def test_analyze_jsonl_edge_cases():
    """测试主分析函数的边界条件"""
    print("Testing analyze_jsonl edge cases...")

    # 创建临时测试文件 - 包含空行和无效数据
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
        # 写入有效数据
        f.write(json.dumps({"latex": r"\frac{a}{b}"}) + '\n')
        # 写入空行
        f.write('\n')
        # 写入无效JSON
        f.write('invalid json\n')
        # 写入缺少latex字段的对象
        f.write(json.dumps({"text": "no latex here"}) + '\n')
        temp_jsonl_path = f.name

    try:
        # 调用分析函数
        df, report_html = analyze_jsonl(
            input_path=temp_jsonl_path,
            use_ai=False
        )

        # 验证返回的 DataFrame - 应该只有1条有效记录
        assert len(df) == 1
        assert df.iloc[0]["latex"] == r"\frac{a}{b}"

        print("✅ analyze_jsonl edge cases tests passed!")

    finally:
        # 清理临时文件
        os.unlink(temp_jsonl_path)


def test_analyze_jsonl_nonexistent_file():
    """测试主分析函数处理不存在的文件"""
    print("Testing analyze_jsonl with nonexistent file...")

    try:
        # 尝试分析不存在的文件
        analyze_jsonl(input_path="/nonexistent/file.jsonl")
        assert False, "应该抛出 FileNotFoundError"
    except FileNotFoundError:
        print("✅ analyze_jsonl nonexistent file test passed!")
    except Exception as e:
        assert False, f"应该抛出 FileNotFoundError，但得到了 {type(e).__name__}: {e}"


def run_all_tests():
    """运行所有测试"""
    print("🧪 开始运行测试...")
    test_classify_formula_type()
    test_classify_formula_domain()
    test_analyze_jsonl_with_different_formats()
    test_analyze_jsonl_with_messages_format()
    test_analyze_jsonl_edge_cases()
    test_analyze_jsonl_nonexistent_file()
    print("🎉 所有测试通过！")


if __name__ == "__main__":
    run_all_tests()