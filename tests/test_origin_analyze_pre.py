import unittest
import tempfile
import pandas as pd
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from origin_data.analyze_pre_sampling import (
    extract_latex_formulas,
    analyze_formula_distribution,
    run_pre_sampling_analysis
)


class TestAnalyzePreSampling(unittest.TestCase):

    def setUp(self):
        """创建测试用的Parquet文件"""
        # 创建临时目录
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # 创建测试数据
        self.test_data = pd.DataFrame({
            'text': [
                'This is a formula: $E = mc^2$ and another one $$F = ma$$',
                'Another example with \\(a^2 + b^2 = c^2\\) and \\[x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\\]',
                'No formulas in this text',
                None,  # 测试空值处理
                'More formulas: $\\int_0^1 x^2 dx$ and $$\\sum_{i=1}^n i = \\frac{n(n+1)}{2}$$',
                '$\\partial f/\\partial x$',  # 微分公式
            ]
        })

        # 保存为Parquet文件
        self.test_parquet = self.temp_path / "test_data.parquet"
        self.test_data.to_parquet(self.test_parquet)

        # 创建空的Parquet文件
        self.empty_parquet = self.temp_path / "empty_data.parquet"
        empty_data = pd.DataFrame({'text': []})
        empty_data.to_parquet(self.empty_parquet)

        # 创建没有公式列的Parquet文件
        self.no_text_column_parquet = self.temp_path / "no_text_column.parquet"
        other_data = pd.DataFrame({'other_column': ['some text']})
        other_data.to_parquet(self.no_text_column_parquet)

    def tearDown(self):
        """清理临时文件"""
        self.temp_dir.cleanup()

    def test_extract_latex_formulas(self):
        """测试LaTeX公式提取功能"""
        # 测试正常情况
        text = 'This is a formula: $E = mc^2$ and another one $$F = ma$$'
        formulas = extract_latex_formulas(text)
        self.assertIn('$E = mc^2$', formulas)
        self.assertIn('F = ma', formulas)

        # 测试不同格式的公式
        text = 'Another example with \\(a^2 + b^2 = c^2\\) and \\[x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\\]'
        formulas = extract_latex_formulas(text)
        self.assertIn('a^2 + b^2 = c^2', formulas)
        self.assertIn('x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}', formulas)

        # 测试空文本
        formulas = extract_latex_formulas('')
        self.assertEqual(formulas, [])

        # 测试None输入
        formulas = extract_latex_formulas(None)
        self.assertEqual(formulas, [])

    def test_analyze_formula_distribution_normal(self):
        """测试正常情况下的公式分布分析"""
        result = analyze_formula_distribution(str(self.test_parquet))

        # 检查返回结果的结构
        self.assertIn('metadata', result)
        self.assertIn('distributions', result)
        self.assertIn('structure', result['distributions'])
        self.assertIn('domain', result['distributions'])
        self.assertIn('rare_categories', result)
        self.assertIn('sampling_recommendations', result)
        self.assertIn('summary', result)

        # 检查元数据
        self.assertEqual(result['metadata']['total_rows'], 6)
        self.assertGreaterEqual(result['metadata']['total_formulas'], 0)
        self.assertEqual(result['metadata']['text_column'], 'text')

        # 检查分布信息
        self.assertIsInstance(result['distributions']['structure'], dict)
        self.assertIsInstance(result['distributions']['domain'], dict)

    def test_analyze_formula_distribution_empty_file(self):
        """测试空Parquet文件的处理"""
        with self.assertRaises(ValueError) as context:
            analyze_formula_distribution(str(self.empty_parquet))

        self.assertIn("No formulas found", str(context.exception))

    def test_analyze_formula_distribution_missing_column(self):
        """测试缺少指定列的情况"""
        with self.assertRaises(ValueError) as context:
            analyze_formula_distribution(str(self.no_text_column_parquet), text_column='text')

        self.assertIn("Column 'text' not found", str(context.exception))

    def test_analyze_formula_distribution_nonexistent_file(self):
        """测试不存在的文件"""
        with self.assertRaises(FileNotFoundError):
            analyze_formula_distribution('nonexistent_file.parquet')

    def test_run_pre_sampling_analysis(self):
        """测试完整的采样分析运行函数"""
        output_file = self.temp_path / "sampling_rules.json"

        result = run_pre_sampling_analysis(
            parquet_path=str(self.test_parquet),
            output_path=str(output_file)
        )

        # 检查返回结果
        self.assertIn('metadata', result)
        self.assertIn('distributions', result)

        # 检查文件是否已创建
        self.assertTrue(output_file.exists())

        # 检查文件内容
        with open(output_file, 'r', encoding='utf-8') as f:
            saved_result = json.load(f)

        self.assertIn('metadata', saved_result)
        self.assertIn('distributions', saved_result)


if __name__ == '__main__':
    unittest.main()