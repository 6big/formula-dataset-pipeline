import os
import cv2
import numpy as np

def apply_enhancements(image):
    """
    应用指定的增强操作：
    1. 只做5°旋转
    2. 使用最近邻插值保持原画质
    3. 不添加任何其他处理
    """
    # 只做5°旋转
    angle = np.random.uniform(-5, 5)
    
    # 获取图像尺寸
    if len(image.shape) == 3:
        h, w = image.shape[:2]
    else:
        h, w = image.shape
    
    # 计算旋转中心
    center = (w // 2, h // 2)
    
    # 应用旋转，使用最近邻插值保持原画质
    scale_matrix = cv2.getRotationMatrix2D(center, angle, 0.9)  # 1.0表示不缩放
    
    # 计算新边界尺寸
    cos_angle = abs(scale_matrix[0, 0])
    sin_angle = abs(scale_matrix[0, 1])
    new_w = int((h * sin_angle) + (w * cos_angle))
    new_h = int((h * cos_angle) + (w * sin_angle))
    
    # 调整变换矩阵
    scale_matrix[0, 2] += (new_w / 2) - center[0]
    scale_matrix[1, 2] += (new_h / 2) - center[1]
    
    # 应用变换，使用最近邻插值保持原画质
    if len(image.shape) == 3:
        enhanced = cv2.warpAffine(image, scale_matrix, (new_w, new_h), 
                                flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REFLECT)
    else:
        enhanced = cv2.warpAffine(image, scale_matrix, (new_w, new_h), 
                                flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REFLECT)
    
    return enhanced


def enhance_formula_image(input_path, output_path, target_height=128, apply_augmentation=False):
    """
    处理单张图像
    """
    try:
        # 读取图像
        image = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)  # 保持原图所有通道信息
        if image is None:
            raise ValueError("无法读取图像")

        # 如果需要增强，则应用增强操作
        if apply_augmentation:
            print(f"🔄 应用增强操作: {os.path.basename(input_path)}")
            image = apply_enhancements(image)
        
        # 对于未增强的图像，直接保存
        if not apply_augmentation:
            # 直接复制文件以保持完全相同的画质
            import shutil
            shutil.copy2(input_path, output_path)
            print(f"✅ 已处理: {output_path} (未增强，保持原画质)")
            return

        # ==================== 步骤1: 保持原图不变 ====================
        processed = image

        # ==================== 步骤2: 直接使用整个图像 ====================
        # 对于公式图像，直接使用整个图像
        cropped = processed

        # ==================== 步骤3: 保存结果 ====================
        # 使用适当压缩的PNG保存以减小文件体积
        cv2.imwrite(output_path, cropped, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        print(f"✅ 已增强: {output_path} (尺寸: {cropped.shape[1]} x {cropped.shape[0]})")

    except Exception as e:
        print(f"⚠️ 处理失败: {input_path} -> {e}")
        # 完全失败时，复制原始文件
        try:
            import shutil
            shutil.copy2(input_path, output_path)
            print(f"🔄 失败回退，已复制原始图像: {output_path}")
        except:
            pass


def enhance_images_in_directory(input_dir, output_dir, target_height=128, num_to_augment=40):
    """
    处理目录中的图像，按确定性方式选择指定数量的图像进行增强
    由于所有图片都有标签，需要保持图像和标签的对应关系
    """
    supported_formats = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif')
    os.makedirs(output_dir, exist_ok=True)

    # 获取所有支持的图像文件并排序（确保确定性）
    all_images = []
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(supported_formats):
            all_images.append(filename)
    
    # 按文件名字典序排序，确保每次运行结果一致
    all_images.sort()
    
    print(f"📁 找到 {len(all_images)} 张图像")
    
    # 确定要增强的图片索引（等间隔选择）
    if len(all_images) <= num_to_augment:
        indices_to_augment = set(range(len(all_images)))
        print(f"⚠️ 图像总数({len(all_images)}) <= 要增强的数量({num_to_augment})，将增强所有图像")
    else:
        # 等间隔选择索引
        step = len(all_images) / num_to_augment
        indices_to_augment = set()
        for i in range(num_to_augment):
            idx = int(i * step)
            indices_to_augment.add(min(idx, len(all_images) - 1))
        print(f"🎯 等间隔选择 {num_to_augment} 张图像进行增强")

    # 处理所有图像
    processed_count = 0
    augmented_count = 0
    
    for idx, filename in enumerate(all_images):
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)
        
        # 检查是否需要应用增强
        apply_augmentation = idx in indices_to_augment
        
        enhance_formula_image(input_path, output_path, target_height, apply_augmentation)
        
        if apply_augmentation:
            augmented_count += 1
        processed_count += 1
        
        # 显示进度
        if processed_count % 20 == 0:
            print(f"📊 进度: {processed_count}/{len(all_images)} (已增强: {augmented_count})")
    
    print(f"\n✅ 处理完成!")
    print(f"📊 总处理: {processed_count} 张")
    print(f"📊 增强操作: {augmented_count} 张")


if __name__ == "__main__":
    input_dir = "./transfer_data/generate_images"
    output_dir = "./worked_data/images"
    NUM_TO_AUGMENT = 120  # 增强120张图像

    if not os.path.exists(input_dir):
        print(f"❌ 输入路径不存在: {input_dir}")
    elif os.path.isfile(input_dir):
        os.makedirs(os.path.dirname(output_dir), exist_ok=True)
        print("🔄 处理单个文件（应用增强）")
        enhance_formula_image(input_dir, output_dir, apply_augmentation=True)
    elif os.path.isdir(input_dir):
        enhance_images_in_directory(input_dir, output_dir, num_to_augment=NUM_TO_AUGMENT)