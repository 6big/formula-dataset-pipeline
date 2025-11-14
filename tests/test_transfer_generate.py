import unittest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from transfer_data.generate_formula_images import (
    fix_latex_for_mathtext,
    validate_latex_syntax,
    render_latex_to_png,
    create_placeholder_image,
    generate_formula_images
)


class TestFixLatexForMathtext(unittest.TestCase):
    """测试 fix_latex_for_mathtext 函数"""

    def test_fix_cal_to_mathcal(self):
        """测试 \cal 替换为 \mathcal"""
        input_latex = r"\cal{A}"
        result = fix_latex_for_mathtext(input_latex)
        self.assertIn(r"\mathcal{A}", result)

    def test_stackrel_to_overset(self):
        """测试 \stackrel 替换为 \overset"""
        input_latex = r"\stackrel{a}{b}"
        result = fix_latex_for_mathtext(input_latex)
        self.assertIn(r"\overset{a}{b}", result)

    def test_sp_to_superscript(self):
        """测试 \sp 替换为 ^"""
        input_latex = r"\sp{a}"
        result = fix_latex_for_mathtext(input_latex)
        self.assertIn(r"^{a}", result)

    def test_invalid_input(self):
        """测试无效输入"""
        self.assertEqual(fix_latex_for_mathtext(None), "")
        self.assertEqual(fix_latex_for_mathtext(123), "")


class TestValidateLatexSyntax(unittest.TestCase):
    """测试 validate_latex_syntax 函数"""

    def test_valid_syntax(self):
        """测试有效的LaTeX语法"""
        self.assertTrue(validate_latex_syntax(r"a+b"))
        self.assertFalse(validate_latex_syntax(""))
        self.assertFalse(validate_latex_syntax(None))  # 注意：函数对None和空字符串返回False

    def test_invalid_syntax_simple(self):
        """测试简单的无效LaTeX语法"""
        # 这个测试可能需要根据实际函数实现进行调整
        pass


class TestRenderLatexToPng(unittest.TestCase):
    """测试 render_latex_to_png 函数"""

    @patch('transfer_data.generate_formula_images.plt')
    def test_render_success(self, mock_plt):
        """测试成功渲染"""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_plt.subplots.return_value = (mock_fig, mock_ax)

        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = os.path.join(temp_dir, "test.png")
            result = render_latex_to_png(r"a+b", test_path)
            self.assertTrue(result)
            mock_plt.savefig.assert_called_once()

    @patch('transfer_data.generate_formula_images.plt')
    def test_render_failure(self, mock_plt):
        """测试渲染失败"""
        mock_plt.subplots.side_effect = Exception("Test error")
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = os.path.join(temp_dir, "test.png")
            result = render_latex_to_png(r"a+b", test_path)
            self.assertFalse(result)


class TestCreatePlaceholderImage(unittest.TestCase):
    """测试 create_placeholder_image 函数"""

    @patch('transfer_data.generate_formula_images.plt')
    def test_create_placeholder_success(self, mock_plt):
        """测试成功创建占位符图像"""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_plt.subplots.return_value = (mock_fig, mock_ax)

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "placeholder.png"
            result = create_placeholder_image(image_path)
            self.assertTrue(result)
            mock_plt.savefig.assert_called_once()

    @patch('transfer_data.generate_formula_images.plt')
    def test_create_placeholder_failure(self, mock_plt):
        """测试创建占位符图像失败"""
        mock_plt.subplots.side_effect = Exception("Test error")

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "placeholder.png"
            result = create_placeholder_image(image_path)
            self.assertFalse(result)


class TestGenerateFormulaImages(unittest.TestCase):
    """测试 generate_formula_images 函数"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # 创建测试用的JSONL文件
        self.test_jsonl_path = self.temp_path / "formulas.jsonl"
        self.create_test_data()

        # 输出目录
        self.output_dir = self.temp_path / "output"

    def tearDown(self):
        """测试后清理"""
        self.temp_dir.cleanup()

    def create_test_data(self):
        """创建测试用的数据"""
        test_data = [
            {"id": "formula_000001", "latex": "\\int_0^1 x^2 dx"},
            {"id": "formula_000002", "latex": "\\frac{d}{dx} \\sin(x)"},
            {"id": "formula_000003", "latex": "\\sum_{i=1}^n i"}
        ]

        with open(self.test_jsonl_path, 'w', encoding='utf-8') as f:
            for item in test_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

    @patch('transfer_data.generate_formula_images.render_latex_to_png')
    def test_generate_images_serial_success(self, mock_render):
        """测试串行模式下成功生成图像"""
        mock_render.return_value = True

        result = generate_formula_images(
            output_dir=str(self.output_dir),
            input_jsonl=str(self.test_jsonl_path),
            serial_threshold=100  # 确保使用串行模式
        )

        self.assertIn("✅", result)
        self.assertIn("总记录: 3", result)
        self.assertTrue((self.output_dir / "dataset.jsonl").exists())

    @patch('transfer_data.generate_formula_images.render_latex_to_png')
    def test_generate_images_serial_with_placeholder(self, mock_render):
        """测试串行模式下使用占位符策略"""
        mock_render.return_value = False  # 模拟渲染失败

        result = generate_formula_images(
            output_dir=str(self.output_dir),
            input_jsonl=str(self.test_jsonl_path),
            failure_strategy="create_placeholder",
            serial_threshold=100  # 确保使用串行模式
        )

        # 由于我们mock了render_latex_to_png使其返回False，但使用了create_placeholder策略
        # 所以仍然应该成功生成dataset.jsonl
        self.assertIn("✅", result)
        self.assertTrue((self.output_dir / "dataset.jsonl").exists())

    @patch('transfer_data.generate_formula_images.render_latex_to_png')
    def test_generate_images_empty_input(self, mock_render):
        """测试空输入文件"""
        # 创建空的JSONL文件
        empty_jsonl_path = self.temp_path / "empty.jsonl"
        empty_jsonl_path.touch()

        result = generate_formula_images(
            output_dir=str(self.output_dir),
            input_jsonl=str(empty_jsonl_path)
        )

        self.assertIn("⚠️", result)
        self.assertIn("输入 JSONL 文件为空或格式错误", result)

    @patch('transfer_data.generate_formula_images.render_latex_to_png')
    def test_generate_images_nonexistent_input(self, mock_render):
        """测试不存在的输入文件"""
        result = generate_formula_images(
            output_dir=str(self.output_dir),
            input_jsonl="nonexistent.jsonl"
        )

        self.assertIn("❌", result)
        self.assertIn("渲染失败", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)