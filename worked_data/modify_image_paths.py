import json

# 定义路径前缀
old_prefix = "images/"
new_prefix = "/root/VLM-formula-recognition-dataset/data/train_data/mini_train/images/"

# 读取并处理文件
input_file = "./transfer_data/best_output.jsonl"
output_file = "./worked_data/add_train.jsonl"

with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
    for line in infile:
        # 解析JSON行
        data = json.loads(line.strip())
        
        # 修改images字段中的路径
        if 'images' in data:
            for i, image_path in enumerate(data['images']):
                if image_path.startswith(old_prefix):
                    # 替换前缀
                    new_path = image_path.replace(old_prefix, new_prefix)
                    data['images'][i] = new_path
        
        # 写入修改后的JSON行
        outfile.write(json.dumps(data, ensure_ascii=False) + '\n')

print(f"处理完成，已保存到 {output_file}")