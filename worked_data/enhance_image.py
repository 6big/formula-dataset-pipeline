import os
import cv2
import numpy as np
import json
from pathlib import Path

def apply_enhancements(image, random_seed: int = None):
    """
    应用 ±5° 旋转增强
    
    Args:
        image: OpenCV 图像数组
        random_seed: 随机种子，用于复现结果
    """
    if random_seed is not None:
        np.random.seed(random_seed)
    
    angle = np.random.uniform(-5, 5)
    
    if len(image.shape) == 3:
        h, w = image.shape[:2]
    else:
        h, w = image.shape
    
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # 计算新边界尺寸
    cos_angle = abs(rotation_matrix[0, 0])
    sin_angle = abs(rotation_matrix[0, 1])
    new_w = int((h * sin_angle) + (w * cos_angle))
    new_h = int((h * cos_angle) + (w * sin_angle))
    
    # 调整变换矩阵以保持中心
    rotation_matrix[0, 2] += (new_w / 2) - center[0]
    rotation_matrix[1, 2] += (new_h / 2) - center[1]
    
    enhanced = cv2.warpAffine(
        image, 
        rotation_matrix, 
        (new_w, new_h), 
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_REFLECT
    )
    
    return enhanced

def _get_images_from_jsonl(dataset_jsonl):
    """从 JSONL 文件获取图片列表的辅助函数"""
    jsonl_images = set()
    try:
        with open(dataset_jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line.strip())
                        for img_path in data.get('images', []):
                            filename = os.path.basename(img_path)
                            jsonl_images.add(filename)
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        print(f"⚠️ 读取 JSONL 文件时出错: {e}")
    return jsonl_images

def enhance_images_in_place(
    images_dir: str,
    dataset_jsonl: str = None,
    num_to_augment: int = None,
    augmentation_ratio: float = 0.1,
    enhance_strategy: str = "deterministic",
    backup_original: bool = False,
    random_seed: int = 42  # 新增：随机种子
) -> str:
    """
    原地增强图片（直接替换原图）
    
    Args:
        images_dir: 图片目录
        dataset_jsonl: 可选，JSONL 文件路径
        num_to_augment: 要增强的数量
        augmentation_ratio: 增强比例
        enhance_strategy: 增强策略
        backup_original: 是否备份原图
        random_seed: 随机种子，用于确定性增强
    """
    try:
        images_path = Path(images_dir)
        if not images_path.exists():
            return f"❌ 图片目录不存在: {images_dir}"
        
        # 支持的图像格式
        supported_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}
        
        # 获取要处理的图片列表
        if dataset_jsonl and Path(dataset_jsonl).exists():
            jsonl_images = _get_images_from_jsonl(dataset_jsonl)
            all_images = []
            for file in images_path.iterdir():
                if file.suffix.lower() in supported_formats and file.name in jsonl_images:
                    all_images.append(file.name)
            print(f"🔍 从 JSONL 读取到 {len(jsonl_images)} 个图片引用，目录中找到 {len(all_images)} 个匹配的图片")
        else:
            all_images = []
            for file in images_path.iterdir():
                if file.suffix.lower() in supported_formats:
                    all_images.append(file.name)
            print(f"📁 目录中找到 {len(all_images)} 个图片文件")
        
        if not all_images:
            return f"❌ 目录中没有找到要处理的图片文件"
        
        all_images.sort()
        
        # 确定要增强的图片索引（设置随机种子确保确定性）
        np.random.seed(random_seed)
        total_images = len(all_images)
        
        if enhance_strategy == "all":
            indices_to_augment = set(range(total_images))
        elif enhance_strategy == "random":
            if num_to_augment is None:
                num_to_augment = int(total_images * augmentation_ratio)
            indices_to_augment = set(np.random.choice(
                total_images, 
                min(num_to_augment, total_images), 
                replace=False
            ))
        else:  # "deterministic"
            if num_to_augment is None:
                num_to_augment = int(total_images * augmentation_ratio)
            
            if total_images <= num_to_augment:
                indices_to_augment = set(range(total_images))
            else:
                step = total_images / num_to_augment
                indices_to_augment = set()
                for i in range(num_to_augment):
                    idx = int(i * step)
                    indices_to_augment.add(min(idx, total_images - 1))
        
        # 处理图像
        processed_count = 0
        augmented_count = 0
        failed_count = 0
        skipped_count = 0
        
        for idx, filename in enumerate(all_images):
            image_path = images_path / filename
            apply_augmentation = idx in indices_to_augment
            
            try:
                if not image_path.exists():
                    skipped_count += 1
                    continue
                
                # 读取图像
                image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
                if image is None:
                    failed_count += 1
                    print(f"⚠️ 无法读取图像: {filename}")
                    continue
                
                # 备份原图
                if backup_original:
                    backup_path = image_path.with_suffix(image_path.suffix + '.bak')
                    if not backup_path.exists():
                        import shutil
                        shutil.copy2(image_path, backup_path)
                
                # 应用增强
                if apply_augmentation:
                    enhanced_image = apply_enhancements(image, random_seed=idx)  # 每张图用不同种子避免完全相同
                    cv2.imwrite(str(image_path), enhanced_image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                    augmented_count += 1
                
                processed_count += 1
                    
            except Exception as e:
                print(f"❌ 处理失败 {filename}: {e}")
                failed_count += 1
            
            # 进度显示
            if processed_count % 50 == 0:
                print(f"📊 进度: {processed_count}/{total_images} (已增强: {augmented_count})")
        
        result = (
            f"✅ 图像增强完成！（原地替换）\n"
            f"📊 总图片: {total_images}\n"
            f"🔄 已增强: {augmented_count}\n"
            f"❌ 处理失败: {failed_count}\n"
            f"🎯 策略: {enhance_strategy}\n"
            f"🔧 随机种子: {random_seed}\n"
            f"📁 目录: {images_dir}\n"
        )
        
        if skipped_count > 0:
            result += f"⚠️ 跳过: {skipped_count} 张（可能不在 JSONL 中）\n"
        
        if dataset_jsonl:
            result += f"📋 参考 JSONL: {dataset_jsonl}\n"
        
        return result
        
    except Exception as e:
        return f"❌ 增强失败: {str(e)}"

# 其他函数保持不变...
def enhance_images_to_new_dir(
    input_dir: str,
    output_dir: str,
    dataset_jsonl: str = None,
    num_to_augment: int = None,
    augmentation_ratio: float = 0.1,
    enhance_strategy: str = "deterministic",
    random_seed: int = 42
) -> str:
    """增强图片到新目录"""
    try:
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 获取图片列表
        supported_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}
        
        if dataset_jsonl and Path(dataset_jsonl).exists():
            jsonl_images = _get_images_from_jsonl(dataset_jsonl)
            all_images = []
            for file in input_path.iterdir():
                if file.suffix.lower() in supported_formats and file.name in jsonl_images:
                    all_images.append(file.name)
        else:
            all_images = []
            for file in input_path.iterdir():
                if file.suffix.lower() in supported_formats:
                    all_images.append(file.name)
        
        if not all_images:
            return f"❌ 输入目录中没有找到图片文件"
        
        all_images.sort()
        
        # 确定要增强的图片索引
        np.random.seed(random_seed)
        total_images = len(all_images)
        
        if enhance_strategy == "all":
            indices_to_augment = set(range(total_images))
        elif enhance_strategy == "random":
            if num_to_augment is None:
                num_to_augment = int(total_images * augmentation_ratio)
            indices_to_augment = set(np.random.choice(
                total_images, 
                min(num_to_augment, total_images), 
                replace=False
            ))
        else:
            if num_to_augment is None:
                num_to_augment = int(total_images * augmentation_ratio)
            
            if total_images <= num_to_augment:
                indices_to_augment = set(range(total_images))
            else:
                step = total_images / num_to_augment
                indices_to_augment = set()
                for i in range(num_to_augment):
                    idx = int(i * step)
                    indices_to_augment.add(min(idx, total_images - 1))
        
        # 处理图像
        processed_count = 0
        augmented_count = 0
        failed_count = 0
        
        for idx, filename in enumerate(all_images):
            input_path_file = input_path / filename
            output_path_file = output_path / filename
            apply_augmentation = idx in indices_to_augment
            
            try:
                image = cv2.imread(str(input_path_file), cv2.IMREAD_UNCHANGED)
                if image is None:
                    failed_count += 1
                    continue
                
                if apply_augmentation:
                    enhanced_image = apply_enhancements(image, random_seed=idx)
                    cv2.imwrite(str(output_path_file), enhanced_image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                    augmented_count += 1
                else:
                    import shutil
                    shutil.copy2(input_path_file, output_path_file)
                
                processed_count += 1
                    
            except Exception as e:
                print(f"❌ 处理失败 {filename}: {e}")
                failed_count += 1
        
        return (
            f"✅ 图像增强完成！（复制到新目录）\n"
            f"📊 总图片: {total_images}\n"
            f"🔄 已增强: {augmented_count}\n"
            f"❌ 处理失败: {failed_count}\n"
            f"🔧 随机种子: {random_seed}\n"
            f"📁 输入目录: {input_dir}\n"
            f"📁 输出目录: {output_dir}\n"
        )
        
    except Exception as e:
        return f"❌ 增强失败: {str(e)}"

def enhance_images_with_backup(
    images_dir: str,
    output_dir: str = None,
    dataset_jsonl: str = None,
    num_to_augment: int = None,
    augmentation_ratio: float = 0.1,
    enhance_strategy: str = "deterministic",
    random_seed: int = 42
) -> str:
    """增强图片（支持备份模式）"""
    if output_dir:
        return enhance_images_to_new_dir(
            images_dir, output_dir, dataset_jsonl, 
            num_to_augment, augmentation_ratio, enhance_strategy, random_seed
        )
    else:
        return enhance_images_in_place(
            images_dir, dataset_jsonl,
            num_to_augment, augmentation_ratio, enhance_strategy, 
            random_seed=random_seed  # 新增随机种子参数
        )