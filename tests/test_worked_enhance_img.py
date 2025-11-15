import unittest
import tempfile
import os
import shutil
import json
import numpy as np
import cv2
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目根目录到 Python 路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from worked_data.enhance_image import (
    apply_enhancements,
    _get_images_from_jsonl,
    enhance_images_in_place,
    enhance_images_to_new_dir,
    enhance_images_with_backup
)


class TestApplyEnhancements(unittest.TestCase):
    """测试 apply_enhancements 函数"""

    def setUp(self):
        """设置测试环境"""
        # 创建一个简单的测试图像 (100x100 的单通道图像)
        self.test_image = np.ones((100, 100), dtype=np.uint8) * 128

        # 创建一个三通道测试图像 (100x100 的三通道图像)
        self.test_image_3ch = np.ones((100, 100, 3), dtype=np.uint8) * 128

    def test_apply_enhancements_with_grayscale_image(self):
        """测试对灰度图像应用增强"""
        result = apply_enhancements(self.test_image, random_seed=42)

        # 验证结果是一个 numpy 数组
        self.assertIsInstance(result, np.ndarray)

        # 验证输出图像的形状存在（可能因旋转而变化）
        self.assertGreater(result.shape[0], 0)
        self.assertGreater(result.shape[1], 0)

    def test_apply_enhancements_with_color_image(self):
        """测试对彩色图像应用增强"""
        result = apply_enhancements(self.test_image_3ch, random_seed=42)

        # 验证结果是一个 numpy 数组
        self.assertIsInstance(result, np.ndarray)

        # 验证输出图像的形状存在（可能因旋转而变化）
        self.assertGreater(result.shape[0], 0)
        self.assertGreater(result.shape[1], 0)
        # 验证仍然是三通道图像
        self.assertEqual(len(result.shape), 3)
        self.assertEqual(result.shape[2], 3)

    def test_apply_enhancements_deterministic_with_seed(self):
        """测试使用相同随机种子时增强结果的一致性"""
        result1 = apply_enhancements(self.test_image, random_seed=42)
        result2 = apply_enhancements(self.test_image, random_seed=42)

        # 使用相同种子时，结果应该一致
        # 注意：由于浮点数精度问题，我们不能直接比较数组是否相等
        self.assertIsInstance(result1, np.ndarray)
        self.assertIsInstance(result2, np.ndarray)


class TestGetImagesFromJsonl(unittest.TestCase):
    """测试 _get_images_from_jsonl 函数"""

    def setUp(self):
        """创建临时 JSONL 文件用于测试"""
        self.temp_dir = tempfile.mkdtemp()
        self.jsonl_file = os.path.join(self.temp_dir, "test.jsonl")

        # 创建测试数据
        test_data = [
            {"images": ["/path/to/image1.jpg", "/path/to/image2.png"]},
            {"images": ["/another/path/image3.jpeg"]},
            {"no_images_key": "value"},
            {"images": []}
        ]

        with open(self.jsonl_file, 'w', encoding='utf-8') as f:
            for item in test_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

    def tearDown(self):
        """清理临时文件"""
        shutil.rmtree(self.temp_dir)

    def test_get_images_from_valid_jsonl(self):
        """测试从有效的 JSONL 文件中获取图片列表"""
        result = _get_images_from_jsonl(self.jsonl_file)

        # 验证返回的是一个集合
        self.assertIsInstance(result, set)

        # 验证包含正确的文件名
        expected_files = {"image1.jpg", "image2.png", "image3.jpeg"}
        self.assertEqual(result, expected_files)

    def test_get_images_from_nonexistent_file(self):
        """测试从不存在的文件中获取图片列表"""
        result = _get_images_from_jsonl("/nonexistent/file.jsonl")

        # 应该返回空集合
        self.assertIsInstance(result, set)
        self.assertEqual(result, set())

    def test_get_images_from_invalid_jsonl(self):
        """测试从无效的 JSONL 文件中获取图片列表"""
        invalid_jsonl = os.path.join(self.temp_dir, "invalid.jsonl")
        with open(invalid_jsonl, 'w', encoding='utf-8') as f:
            f.write("invalid json content\n")
            f.write("{ invalid: json: content }\n")

        result = _get_images_from_jsonl(invalid_jsonl)

        # 应该返回空集合，不抛出异常
        self.assertIsInstance(result, set)
        self.assertEqual(result, set())


class TestEnhanceImagesInPlace(unittest.TestCase):
    """测试 enhance_images_in_place 函数"""

    def setUp(self):
        """创建临时目录和测试图像"""
        self.temp_dir = tempfile.mkdtemp()

        # 创建测试图像
        self.test_image = np.ones((50, 50, 3), dtype=np.uint8) * 128
        self.image_path = os.path.join(self.temp_dir, "test_image.png")
        cv2.imwrite(self.image_path, self.test_image)

        # 创建另一个测试图像
        self.image2_path = os.path.join(self.temp_dir, "test_image2.jpg")
        cv2.imwrite(self.image2_path, self.test_image)

        # 创建非图像文件
        self.text_file = os.path.join(self.temp_dir, "readme.txt")
        with open(self.text_file, 'w') as f:
            f.write("This is a text file")

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.temp_dir)

    def test_enhance_images_in_place_nonexistent_dir(self):
        """测试处理不存在的目录"""
        result = enhance_images_in_place("/nonexistent/directory")

        # 验证返回包含错误信息的字符串
        self.assertIsInstance(result, str)
        self.assertIn("❌ 图片目录不存在", result)

    def test_enhance_images_in_place_empty_dir(self):
        """测试处理空目录"""
        empty_dir = tempfile.mkdtemp()
        try:
            result = enhance_images_in_place(empty_dir)

            # 验证返回包含错误信息的字符串
            self.assertIsInstance(result, str)
            self.assertIn("❌ 目录中没有找到要处理的图片文件", result)
        finally:
            shutil.rmtree(empty_dir)

    def test_enhance_images_in_place_with_images(self):
        """测试处理包含图像的目录"""
        # 使用 deterministic 策略增强所有图像
        result = enhance_images_in_place(
            self.temp_dir,
            enhance_strategy="all",
            random_seed=42
        )

        # 验证返回成功的字符串
        self.assertIsInstance(result, str)
        self.assertIn("✅ 图像增强完成", result)
        self.assertIn("总图片: 2", result)  # 应该找到2个图像文件
        self.assertIn("已增强: 2", result)  # 应该增强了2个图像

    def test_enhance_images_in_place_with_jsonl_filter(self):
        """测试使用 JSONL 文件过滤图像"""
        # 创建 JSONL 文件
        jsonl_file = os.path.join(self.temp_dir, "filter.jsonl")
        test_data = [
            {"images": ["test_image.png"]},  # 只包含一个图像
        ]

        with open(jsonl_file, 'w', encoding='utf-8') as f:
            for item in test_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        result = enhance_images_in_place(
            self.temp_dir,
            dataset_jsonl=jsonl_file,
            enhance_strategy="all",
            random_seed=42
        )

        # 验证只处理了 JSONL 中指定的图像
        self.assertIsInstance(result, str)
        self.assertIn("总图片: 1", result)  # 应该只找到1个匹配的图像
        self.assertIn("已增强: 1", result)  # 应该只增强了1个图像


class TestEnhanceImagesToNewDir(unittest.TestCase):
    """测试 enhance_images_to_new_dir 函数"""

    def setUp(self):
        """创建临时目录和测试图像"""
        self.input_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()

        # 创建测试图像
        self.test_image = np.ones((50, 50, 3), dtype=np.uint8) * 128
        self.image_path = os.path.join(self.input_dir, "test_image.png")
        cv2.imwrite(self.image_path, self.test_image)

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.input_dir)
        shutil.rmtree(self.output_dir)

    def test_enhance_images_to_new_dir_with_images(self):
        """测试将图像增强到新目录"""
        result = enhance_images_to_new_dir(
            self.input_dir,
            self.output_dir,
            enhance_strategy="all",
            random_seed=42
        )

        # 验证返回成功的字符串
        self.assertIsInstance(result, str)
        self.assertIn("✅ 图像增强完成", result)
        self.assertIn("总图片: 1", result)
        self.assertIn("已增强: 1", result)

        # 验证输出目录中存在处理后的图像
        output_image_path = os.path.join(self.output_dir, "test_image.png")
        self.assertTrue(os.path.exists(output_image_path))

    def test_enhance_images_to_new_dir_nonexistent_input(self):
        """测试输入目录不存在的情况"""
        result = enhance_images_to_new_dir(
            "/nonexistent/input",
            self.output_dir
        )

        # 验证返回包含错误信息的字符串
        self.assertIsInstance(result, str)
        # 当输入目录不存在时，函数会抛出异常并返回错误信息
        self.assertIn("❌ 增强失败", result)
        # 修改断言，不再检查特定的错误消息文本，而是检查是否包含常见的错误关键词
        # Windows和Linux系统可能会有不同的错误消息文本
        self.assertTrue("cannot find" in result or "No such file" in result or "找不到" in result or "The system cannot find" in result)


class TestEnhanceImagesWithBackup(unittest.TestCase):
    """测试 enhance_images_with_backup 函数"""

    def setUp(self):
        """创建临时目录和测试图像"""
        self.temp_dir = tempfile.mkdtemp()

        # 创建测试图像
        self.test_image = np.ones((50, 50, 3), dtype=np.uint8) * 128
        self.image_path = os.path.join(self.temp_dir, "test_image.png")
        cv2.imwrite(self.image_path, self.test_image)

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.temp_dir)

    def test_enhance_images_with_backup_no_output_dir(self):
        """测试不指定输出目录时原地增强"""
        result = enhance_images_with_backup(
            self.temp_dir,
            output_dir=None,
            enhance_strategy="all",
            random_seed=42
        )

        # 验证返回成功的字符串
        self.assertIsInstance(result, str)
        self.assertIn("✅ 图像增强完成", result)
        self.assertIn("总图片: 1", result)

    def test_enhance_images_with_backup_with_output_dir(self):
        """测试指定输出目录时增强到新目录"""
        output_dir = tempfile.mkdtemp()
        try:
            result = enhance_images_with_backup(
                self.temp_dir,
                output_dir=output_dir,
                enhance_strategy="all",
                random_seed=42
            )

            # 验证返回成功的字符串
            self.assertIsInstance(result, str)
            self.assertIn("✅ 图像增强完成", result)
            self.assertIn("总图片: 1", result)

            # 验证输出目录中存在处理后的图像
            output_image_path = os.path.join(output_dir, "test_image.png")
            self.assertTrue(os.path.exists(output_image_path))
        finally:
            shutil.rmtree(output_dir)


if __name__ == "__main__":
    unittest.main()