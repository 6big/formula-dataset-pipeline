import unittest
import tempfile
import os
import shutil
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Formula Dataset Pipeline'))

from worked_data.modify_image_paths import (
    modify_image_paths,
    modify_image_paths_with_validation,
    batch_modify_paths
)


class TestModifyImagePaths(unittest.TestCase):
    """测试 modify_image_paths 函数"""

    def setUp(self):
        """创建临时目录和测试文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = os.path.join(self.temp_dir, "input.jsonl")
        self.output_file = os.path.join(self.temp_dir, "output.jsonl")
        
        # 创建测试数据
        test_data = [
            {"text": "formula 1", "images": ["images/formula1.png", "images/formula2.jpg"]},
            {"text": "formula 2", "images": ["images/eq1.png"]},
            {"text": "formula 3", "images": ["other/path/image.png"]},  # 不匹配前缀
            {"text": "formula 4"},  # 没有 images 字段
        ]
        
        with open(self.input_file, 'w', encoding='utf-8') as f:
            for item in test_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.temp_dir)

    def test_modify_image_paths_normal_case(self):
        """测试正常修改图像路径的情况"""
        result = modify_image_paths(
            input_jsonl=self.input_file,
            output_jsonl=self.output_file,
            old_prefix="images/",
            new_prefix="enhanced/"
        )
        
        # 验证返回结果
        self.assertIsInstance(result, str)
        self.assertIn("✅ 路径修改完成", result)
        self.assertIn("总记录: 4", result)
        self.assertIn("已修改: 2", result)  # 前两条记录被修改
        self.assertIn("已更新: 3", result)  # 3个路径被更新
        
        # 验证输出文件存在
        self.assertTrue(os.path.exists(self.output_file))
        
        # 验证输出文件内容
        with open(self.output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        self.assertEqual(len(lines), 4)
        
        # 验证第一行数据
        data1 = json.loads(lines[0].strip())
        self.assertEqual(data1["images"], ["enhanced/formula1.png", "enhanced/formula2.jpg"])
        
        # 验证第二行数据
        data2 = json.loads(lines[1].strip())
        self.assertEqual(data2["images"], ["enhanced/eq1.png"])
        
        # 验证第三行数据（未修改）
        data3 = json.loads(lines[2].strip())
        self.assertEqual(data3["images"], ["other/path/image.png"])
        
        # 验证第四行数据（没有images字段）
        data4 = json.loads(lines[3].strip())
        self.assertNotIn("images", data4)

    def test_modify_image_paths_nonexistent_input(self):
        """测试输入文件不存在的情况"""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.jsonl")
        result = modify_image_paths(
            input_jsonl=nonexistent_file,
            output_jsonl=self.output_file
        )
        
        # 验证返回错误信息
        self.assertIsInstance(result, str)
        self.assertIn("❌ 输入文件不存在", result)

    def test_modify_image_paths_empty_file(self):
        """测试空文件的情况"""
        empty_file = os.path.join(self.temp_dir, "empty.jsonl")
        with open(empty_file, 'w', encoding='utf-8') as f:
            pass  # 创建空文件
            
        result = modify_image_paths(
            input_jsonl=empty_file,
            output_jsonl=self.output_file
        )
        
        # 验证返回结果
        self.assertIsInstance(result, str)
        self.assertIn("✅ 路径修改完成", result)
        self.assertIn("总记录: 0", result)
        
        # 验证输出文件存在且为空
        self.assertTrue(os.path.exists(self.output_file))
        with open(self.output_file, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read(), "")


class TestModifyImagePathsWithValidation(unittest.TestCase):
    """测试 modify_image_paths_with_validation 函数"""

    def setUp(self):
        """创建临时目录和测试文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = os.path.join(self.temp_dir, "input.jsonl")
        self.output_file = os.path.join(self.temp_dir, "output.jsonl")
        
        # 创建测试数据
        test_data = [
            {"text": "formula 1", "images": ["images/formula1.png", "images/formula2.jpg"]},
            {"text": "formula 2", "images": ["other/path/image.png"]},
        ]
        
        with open(self.input_file, 'w', encoding='utf-8') as f:
            for item in test_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.temp_dir)

    def test_modify_image_paths_with_validation_no_validation(self):
        """测试带验证功能的路径修改（不实际验证路径）"""
        result = modify_image_paths_with_validation(
            input_jsonl=self.input_file,
            output_jsonl=self.output_file,
            old_prefix="images/",
            new_prefix="enhanced/",
            validate_paths=False
        )
        
        # 验证返回结果
        self.assertIsInstance(result, str)
        self.assertIn("✅ 路径修改完成", result)
        self.assertIn("总记录: 2", result)
        self.assertIn("已修改: 1", result)  # 第一条记录被修改
        self.assertIn("已更新: 2", result)  # 2个路径被更新
        
        # 验证输出文件内容
        with open(self.output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        data1 = json.loads(lines[0].strip())
        self.assertEqual(data1["images"], ["enhanced/formula1.png", "enhanced/formula2.jpg"])

    def test_modify_image_paths_with_validation_with_invalid_paths(self):
        """测试带验证功能的路径修改（包含无效路径）"""
        result = modify_image_paths_with_validation(
            input_jsonl=self.input_file,
            output_jsonl=self.output_file,
            old_prefix="images/",
            new_prefix="enhanced/",
            validate_paths=True  # 启用路径验证
        )
        
        # 验证返回结果
        self.assertIsInstance(result, str)
        self.assertIn("✅ 路径修改完成", result)
        # 由于路径不存在，应该报告找不到的路径
        self.assertIn("找不到的路径:", result)


class TestBatchModifyPaths(unittest.TestCase):
    """测试 batch_modify_paths 函数"""

    def setUp(self):
        """创建临时目录和测试文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        
        # 创建多个测试文件
        self.file1 = os.path.join(self.temp_dir, "file1.jsonl")
        self.file2 = os.path.join(self.temp_dir, "file2.jsonl")
        
        test_data1 = [
            {"text": "formula 1", "images": ["images/formula1.png"]},
        ]
        
        test_data2 = [
            {"text": "formula 2", "images": ["images/formula2.png"]},
        ]
        
        with open(self.file1, 'w', encoding='utf-8') as f:
            for item in test_data1:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                
        with open(self.file2, 'w', encoding='utf-8') as f:
            for item in test_data2:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.temp_dir)
        shutil.rmtree(self.output_dir)

    def test_batch_modify_paths_with_output_dir(self):
        """测试批量修改路径并指定输出目录"""
        jsonl_files = [self.file1, self.file2]
        result = batch_modify_paths(
            jsonl_files=jsonl_files,
            old_prefix="images/",
            new_prefix="enhanced/",
            output_dir=self.output_dir
        )
        
        # 验证返回结果
        self.assertIsInstance(result, str)
        self.assertIn("file1.jsonl", result)
        self.assertIn("file2.jsonl", result)
        
        # 验证输出文件存在
        output_file1 = os.path.join(self.output_dir, "file1.jsonl")
        output_file2 = os.path.join(self.output_dir, "file2.jsonl")
        self.assertTrue(os.path.exists(output_file1))
        self.assertTrue(os.path.exists(output_file2))
        
        # 验证输出文件内容
        with open(output_file1, 'r', encoding='utf-8') as f:
            data1 = json.loads(f.readline().strip())
        self.assertEqual(data1["images"], ["enhanced/formula1.png"])
        
        with open(output_file2, 'r', encoding='utf-8') as f:
            data2 = json.loads(f.readline().strip())
        self.assertEqual(data2["images"], ["enhanced/formula2.png"])

    def test_batch_modify_paths_without_output_dir(self):
        """测试批量修改路径但不指定输出目录"""
        jsonl_files = [self.file1]
        result = batch_modify_paths(
            jsonl_files=jsonl_files,
            old_prefix="images/",
            new_prefix="enhanced/",
            output_dir=None  # 不指定输出目录
        )
        
        # 验证返回结果
        self.assertIsInstance(result, str)
        self.assertIn("file1.jsonl", result)
        
        # 验证在输入目录中创建了修改后的文件
        modified_file = os.path.join(self.temp_dir, "modified_file1.jsonl")
        self.assertTrue(os.path.exists(modified_file))


if __name__ == "__main__":
    unittest.main()