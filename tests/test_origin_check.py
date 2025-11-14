# test_check.py
import sys
import os
import unittest
from unittest.mock import patch, mock_open

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from origin_data.check import check_columns


class TestCheckColumns(unittest.TestCase):

    def test_invalid_file_extension(self):
        """测试无效文件扩展名"""
        result = check_columns("./origin_data/新建 文本文档.txt")
        self.assertIn("❌ 仅支持 .parquet 文件！", result)

    @patch("pandas.read_parquet")
    def test_empty_parquet_file(self, mock_read_parquet):
        """测试空的Parquet文件"""
        # 模拟空的DataFrame
        mock_df = unittest.mock.Mock()
        mock_df.empty = True
        mock_read_parquet.return_value = mock_df

        result = check_columns("./origin_data/empty_file.parquet")
        self.assertIn("⚠️ 文件为空，无数据行。", result)

    @patch("pandas.read_parquet")
    def test_missing_required_columns(self, mock_read_parquet):
        """测试缺少必需列的情况"""
        # 模拟缺少列的DataFrame
        mock_df = unittest.mock.Mock()
        mock_df.empty = False
        mock_df.columns = ["text"]  # 缺少'image'列
        mock_read_parquet.return_value = mock_df

        result = check_columns("./origin_data/test_file.parquet")
        self.assertIn("❌ 缺少必要列", result)
        self.assertIn("image", result)

    @patch("pandas.read_parquet")
    def test_valid_parquet_with_dict_image(self, mock_read_parquet):
        """测试有效的Parquet文件，其中image列为字典类型"""
        # 模拟有效的DataFrame
        mock_df = unittest.mock.Mock()
        mock_df.empty = False
        mock_df.columns = ["text", "image"]
        mock_df.__len__ = lambda self: 5
        mock_df.iloc = unittest.mock.Mock()

        # 模拟第一行数据
        mock_row = unittest.mock.Mock()
        mock_row.__getitem__ = lambda self, key: (
            "E=mc^2" if key == "text" else {"bytes": b"fake_image_data"}
        )
        mock_df.iloc.__getitem__ = lambda self, key: mock_row

        mock_read_parquet.return_value = mock_df

        result = check_columns("./origin_data/test_file.parquet")
        self.assertIn("✅ 列名检查通过！", result)
        self.assertIn("📊 总行数: 5", result)
        self.assertIn("📋 所有列: ['text', 'image']", result)

    @patch("pandas.read_parquet")
    def test_exception_handling(self, mock_read_parquet):
        """测试异常处理"""
        # 模拟抛出异常
        mock_read_parquet.side_effect = Exception("测试异常")

        result = check_columns("./origin_data/broken_file.parquet")
        self.assertIn("❌ 检查失败: 测试异常", result)


if __name__ == '__main__':
    unittest.main()