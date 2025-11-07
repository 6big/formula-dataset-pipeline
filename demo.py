"""
数学公式数据集处理流水线 GUI 应用。

该模块提供了一个基于 Gradio 的图形界面，用于处理数学公式数据集，
包括检查、采样预分析、格式转换、图像生成、核验、增强和路径修改等功能。
"""

import sys
import os
import pandas as pd
import gradio as gr

# 添加项目路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 导入后端函数
from origin_data.check import check_columns
from origin_data.analyze_pre_sampling import run_pre_sampling_analysis
from transfer_data.convert import (
    convert_to_latex_jsonl,
    convert_tagged_jsonl_to_latex_jsonl,
)
from transfer_data.generate_formula_images import generate_formula_images
from transfer_data.compare import compare_and_clean
from worked_data.enhance_image import enhance_images_in_place, enhance_images_to_new_dir
from worked_data.analyze_jsonl import analyze_jsonl


def create_app():
    with gr.Blocks(
        title="数学公式数据集处理流水线", theme=gr.themes.Soft()
    ) as demo_app:

        # 紫色标题 + 步骤导航（无滚动条）
        gr.Markdown(
            """
        <h2 style="margin: 0 0 15px 0; color: #6864f4; font-size: 28px; font-weight: bold;text-align: center;margin-bottom: 40px;">
        🧪 数学公式数据集处理流水线
        </h2>
        """
        )

        with gr.Tab("步骤 1：检查原始数据"):
            with gr.Row():
                with gr.Column(scale=1):
                    file_input = gr.File(label="上传原始数据", file_types=[".parquet"])
                    check_btn = gr.Button("🔍 检查数据")

                with gr.Column(scale=2):
                    check_output = gr.Textbox(
                        label="检查结果",
                        lines=11,
                        interactive=False,
                        placeholder="使用提示:\n"
                        "1. 上传原始数据集文件(.parquet格式)。\n"
                        "2. 点击[检查数据]按钮后可以查看检查结果。\n"
                        "3. 如果不需要采样预分析,可以跳过步骤2。\n",
                    )

            # 添加事件绑定
            check_btn.click(fn=check_columns, inputs=file_input, outputs=check_output)

        with gr.Tab("步骤 2：采样预分析"):
            with gr.Row():
                with gr.Column(scale=1):
                    step2_file_input = gr.File(
                        label="上传原始数据集", file_types=[".parquet"]
                    )
                    text_column = gr.Textbox(
                        label="采样文本列名",
                        value="text",
                        placeholder="请输入包含LaTeX公式的列名",
                    )
                    output_path = gr.Textbox(
                        label="规则文件输出路径",
                        value="./origin_data/output/sampling_rules.json",
                        placeholder="请填写规则文件输出路径",
                    )

                    with gr.Group():
                        gr.Markdown("#### 分析参数")
                        rare_count_threshold = gr.Number(
                            label="稀有类别最小样本数阈值",
                            value=10,
                            minimum=0,
                            precision=0,
                        )
                        rare_ratio_threshold = gr.Slider(
                            label="稀有类别最小占比阈值",
                            value=0.05,
                            minimum=0,
                            maximum=1,
                            step=0.01,
                        )
                        target_min_per_class = gr.Number(
                            label="每类目标最小样本数", value=30, minimum=0, precision=0
                        )

                    analyze_btn = gr.Button("🔬 执行预分析")

                with gr.Column(scale=2):
                    analyze_output = gr.Textbox(
                        label="分析结果",
                        lines=33,
                        interactive=False,
                        placeholder="使用提示:\n"
                        "1. 上传原始数据集文件(.parquet格式)。\n"
                        "2. 设置相关参数并点击执行预分析按钮。\n"
                        "3. 查看分析结果和采样建议。",
                    )
                    sampling_rules_output = gr.JSON(
                        label="采样规则(JSON格式)", visible=False
                    )

            # 添加事件绑定
            def wrap_run_pre_sampling_analysis(
                parquet_file,
                text_column,
                output_path,
                rare_count_threshold,
                rare_ratio_threshold,
                target_min_per_class,
            ):
                if parquet_file is None:
                    return "❌请先上传Parquet文件", None

                try:
                    result = run_pre_sampling_analysis(
                        parquet_path=parquet_file.name,
                        text_column=text_column,
                        output_path=output_path,
                        rare_count_threshold=int(rare_count_threshold),
                        rare_ratio_threshold=float(rare_ratio_threshold),
                        target_min_per_class=int(target_min_per_class),
                    )

                    # 格式化输出结果
                    output_text = f"✅ 采样预分析完成！\n\n"
                    output_text += f"📊 总行数: {result['metadata']['total_rows']}\n"
                    output_text += (
                        f"📝 非空行数: {result['metadata']['non_empty_rows']}\n"
                    )
                    output_text += f"EmptyEntries: {result['metadata']['empty_rows']}\n"
                    output_text += (
                        f"🧮 提取公式总数: {result['metadata']['total_formulas']}\n"
                    )
                    output_text += f"📂 输出规则文件: {output_path}\n\n"

                    output_text += "📈 公式结构分布:\n"
                    for structure, count in result["distributions"][
                        "structure"
                    ].items():
                        percentage = result["summary"]["structure_ratio_%"].get(
                            structure, 0
                        )
                        output_text += f"  - {structure}: {count} ({percentage}%)\n"

                    output_text += "\n📊 学术领域分布:\n"
                    for domain, count in result["distributions"]["domain"].items():
                        percentage = result["summary"]["domain_ratio_%"].get(domain, 0)
                        output_text += f"  - {domain}: {count} ({percentage}%)\n"

                    output_text += "\n⚠️ 稀有类别:\n"
                    output_text += f"  结构类别: {', '.join(result['rare_categories']['structure']) or '无'}\n"
                    output_text += f"  领域类别: {', '.join(result['rare_categories']['domain']) or '无'}\n\n"

                    output_text += "🎯 采样建议:\n"
                    output_text += (
                        f"  策略: {result['sampling_recommendations']['strategy']}\n"
                    )
                    output_text += f"  需要过采样的类别: {', '.join(result['sampling_recommendations']['oversample_categories']) or '无'}\n"
                    output_text += f"  需要欠采样的类别: {', '.join(result['sampling_recommendations']['undersample_categories']) or '无'}\n"

                    return output_text, result

                except Exception as exception:
                    import traceback

                    error_info = f"❌ 分析失败: {str(exception)}\n详细错误信息:\n{traceback.format_exc()}"
                    return error_info, None

            analyze_btn.click(
                fn=wrap_run_pre_sampling_analysis,
                inputs=[
                    step2_file_input,
                    text_column,
                    output_path,
                    rare_count_threshold,
                    rare_ratio_threshold,
                    target_min_per_class,
                ],
                outputs=[analyze_output, sampling_rules_output],
            )

        with gr.Tab("步骤 3：转换格式"):
            with gr.Row():
                with gr.Column(scale=1):
                    step2_file_input = gr.File(
                        label="上传原始数据集", file_types=[".parquet"]
                    )

                    with gr.Group():
                        gr.Markdown("#### 转换模式")
                        conversion_mode = gr.Radio(
                            choices=[
                                ("直接从Parquet转换", "parquet"),
                                ("从带标签JSONL转换(需执行步骤2)", "tagged"),
                            ],
                            value="tagged",
                            label="选择转换模式",
                        )

                    # Parquet转换参数
                    with gr.Group(visible=False) as parquet_group:
                        gr.Markdown("#### Parquet采样参数")
                        sample_interval = gr.Number(
                            label="采样间隔", value=20, minimum=0, precision=0
                        )
                        target_samples = gr.Number(
                            label="目标样本数", value=300, minimum=0, precision=0
                        )
                        total_records_limit = gr.Number(
                            label="总记录限制",
                            value=100000,
                            interactive=False,
                        )

                    # 带标签JSONL转换参数
                    with gr.Group(visible=True) as tagged_group:
                        gr.Markdown("#### 带标签数据采样参数")
                        tagged_input_jsonl = gr.Textbox(
                            label="带标签JSONL文件路径",
                            value="./origin_data/output/intermediate_tagged.jsonl",
                            placeholder="请输入带标签JSONL文件路径",
                        )

                        with gr.Group():
                            gr.Markdown("##### 采样策略")
                            tagged_sampling_strategy = gr.Radio(
                                choices=[
                                    ("随机采样", "random"),
                                    ("分层采样", "stratified"),
                                ],
                                value="stratified",
                                label="采样策略",
                            )
                            tagged_target_samples = gr.Number(
                                label="目标样本数", value=300, precision=0
                            )

                        with gr.Group():
                            gr.Markdown("##### 过滤规则")
                            tagged_exclude_other = gr.Checkbox(
                                label="排除 'Other' 类别", value=True
                            )
                            tagged_exclude_rare = gr.Checkbox(
                                label="排除稀有类别", value=True
                            )

                            tagged_sampling_rules_path = gr.Textbox(
                                label="采样规则文件路径",
                                value="./origin_data/output/sampling_rules.json",
                            )

                            tagged_exclude_custom = gr.Textbox(
                                label="自定义排除类别（用逗号分隔）",
                                placeholder="例如: 微分,根式,矩阵/分段",
                            )

                    convert_btn = gr.Button("🔄 转换为JSONL")

                with gr.Column(scale=2):
                    convert_output = gr.Textbox(
                        label="转换结果",
                        lines=35,
                        interactive=False,
                        placeholder="使用提示:\n"
                        "1. 选择转换模式(直接从Parquet转换或从带标签JSONL转换)。\n"
                        "2. 根据所选模式设置相应的参数。\n"
                        "3. 点击转换按钮开始处理。",
                    )

            # 添加模式切换逻辑
            def toggle_conversion_mode(mode):
                if mode == "parquet":
                    return gr.update(visible=True), gr.update(visible=False)
                else:
                    return gr.update(visible=False), gr.update(visible=True)

            conversion_mode.change(
                fn=toggle_conversion_mode,
                inputs=conversion_mode,
                outputs=[parquet_group, tagged_group],
            )

            # 添加事件绑定
            def wrap_convert_function(
                conversion_mode,
                parquet_file,
                sample_interval,
                target_samples,
                total_records_limit,
                tagged_input_jsonl,
                tagged_sampling_strategy,
                tagged_target_samples,
                tagged_exclude_other,
                tagged_exclude_rare,
                tagged_sampling_rules_path,
                tagged_exclude_custom,
            ):
                try:
                    if conversion_mode == "parquet":
                        # 使用原始的Parquet转换函数
                        if parquet_file is None:
                            return "请先上传Parquet文件"

                        return convert_to_latex_jsonl(
                            input_parquet=parquet_file.name,
                            output_dir="",  # 使用默认输出目录
                            sample_interval=int(sample_interval),
                            target_samples=int(target_samples),
                            total_records_limit=int(total_records_limit),
                        )
                    else:
                        # 使用新的带标签数据转换函数
                        exclude_custom_list = None
                        if tagged_exclude_custom and tagged_exclude_custom.strip():
                            exclude_custom_list = [
                                cat.strip() for cat in tagged_exclude_custom.split(",")
                            ]

                        return convert_tagged_jsonl_to_latex_jsonl(
                            input_jsonl=tagged_input_jsonl,
                            output_dir="",  # 使用默认输出目录
                            target_samples=int(tagged_target_samples),
                            sampling_strategy=tagged_sampling_strategy,
                            sampling_rules_path=tagged_sampling_rules_path,
                            exclude_other=tagged_exclude_other,
                            exclude_rare=tagged_exclude_rare,
                            exclude_custom=exclude_custom_list,
                        )

                except Exception as exception:
                    import traceback

                    error_info = f"❌ 转换失败: {str(exception)}\n详细错误信息:\n{traceback.format_exc()}"
                    return error_info

            convert_btn.click(
                fn=wrap_convert_function,
                inputs=[
                    conversion_mode,
                    step2_file_input,
                    sample_interval,
                    target_samples,
                    total_records_limit,
                    tagged_input_jsonl,
                    tagged_sampling_strategy,
                    tagged_target_samples,
                    tagged_exclude_other,
                    tagged_exclude_rare,
                    tagged_sampling_rules_path,
                    tagged_exclude_custom,
                ],
                outputs=convert_output,
            )

        with gr.Tab("步骤 4：生成公式图"):
            with gr.Row():
                with gr.Column(scale=1):
                    step4_output_dir = gr.Textbox(
                        label="输出目录",
                        value="./transfer_data/output",
                        placeholder="请输入输出目录路径",
                    )
                    input_jsonl = gr.Textbox(
                        label="输入JSONL文件路径",
                        value="./transfer_data/input/formulas.jsonl",
                        placeholder="请输入JSONL文件路径",
                    )
                    user_prompt = gr.Textbox(
                        label="用户提示词",
                        value="请根据以下 LaTeX 公式生成相应的数学表达式图片。",
                        lines=3,
                    )

                    with gr.Group():
                        gr.Markdown("#### 渲染参数")
                        image_prefix = gr.Textbox(
                            label="图像文件前缀",
                            value="sample",
                            placeholder="请输入图像文件前缀",
                        )

                        with gr.Row():
                            dpi = gr.Number(
                                label="DPI",
                                value=100,
                                precision=0,
                            )
                            fontsize = gr.Number(
                                label="字体大小", value=20, precision=0
                            )

                        with gr.Row():
                            figsize_width = gr.Number(label="图像宽度", value=5)
                            figsize_height = gr.Number(label="图像高度", value=3)

                    with gr.Group():
                        gr.Markdown("#### 处理策略")
                        failure_strategy = gr.Radio(
                            choices=[
                                ("跳过失败样本", "skip"),
                                ("创建占位符图像", "create_placeholder"),
                            ],
                            value="skip",
                            label="失败处理策略",
                        )

                        # 添加复选框以允许同时记录失败样本ID
                        record_failed_ids = gr.Checkbox(
                            label="记录失败样本ID供后续处理", value=False
                        )

                    generate_btn = gr.Button("🎨 生成公式图像")

                with gr.Column(scale=2):
                    generate_output = gr.Textbox(
                        label="生成结果",
                        lines=42,
                        interactive=False,
                        placeholder="使用提示:\n"
                        "1. 设置输出目录和输入JSONL文件路径。\n"
                        "2. 配置渲染参数(DPI、字体大小、图像尺寸等)。\n"
                        "3. 选择失败处理策略:\n"
                        "   - 跳过：遇到渲染失败的公式直接跳过，不保存图片。\n"
                        "   - 占位符：为失败公式生成占位符图像，确保数据完整性。\n"
                        "     默认使用透明图像(224x224)并添加红色❌水印。\n"
                        "4. 点击生成按钮开始创建公式图像。",
                    )

            # 添加事件绑定
            def wrap_generate_formula_images(
                output_dir,
                input_jsonl,
                user_prompt,
                image_prefix,
                dpi,
                figsize_width,
                figsize_height,
                fontsize,
                failure_strategy,
                record_failed_ids,  # 添加这个参数
            ):
                if not output_dir:
                    return "请指定输出目录"

                try:
                    result = generate_formula_images(
                        output_dir=output_dir,
                        input_jsonl=input_jsonl,
                        user_prompt=user_prompt,
                        image_prefix=image_prefix,
                        dpi=dpi,
                        figsize=(figsize_width, figsize_height),
                        fontsize=fontsize,
                        failure_strategy=failure_strategy,
                        record_failed_ids=record_failed_ids,  # 传递这个参数
                    )
                    return result
                except Exception as exception:
                    import traceback

                    error_info = f"❌ 生成失败: {str(exception)}\n详细错误信息:\n{traceback.format_exc()}"
                    return error_info

            generate_btn.click(
                fn=wrap_generate_formula_images,
                inputs=[
                    step4_output_dir,
                    input_jsonl,
                    user_prompt,
                    image_prefix,
                    dpi,
                    figsize_width,
                    figsize_height,
                    fontsize,
                    failure_strategy,
                    record_failed_ids,  # 添加这个输入
                ],
                outputs=generate_output,
            )

        with gr.Tab("步骤 5：核验图集"):
            with gr.Row():
                with gr.Column(scale=1):
                    jsonl_file_path = gr.Textbox(
                        label="JSONL文件路径",
                        value="./transfer_data/output/dataset.jsonl",
                        placeholder="请输入JSONL文件路径",
                    )
                    images_folder_path = gr.Textbox(
                        label="图片文件夹路径",
                        value="./transfer_data/output/images",
                        placeholder="请输入图片文件夹路径",
                    )
                    bad_images_file = gr.Textbox(
                        label="Bad Images文件路径（可选）",
                        placeholder="请输入bad_images.txt文件路径（可选）",
                    )

                    with gr.Group():
                        gr.Markdown("#### 处理模式")
                        mode = gr.Radio(
                            choices=[
                                ("自动删除不存在的图片条目", "auto"),
                                ("仅返回统计信息，供用户决定", "interactive"),
                                ("跳过处理", "skip"),
                            ],
                            value="auto",
                            label="处理模式",
                        )

                    compare_btn = gr.Button("🔍 核验图集")

                with gr.Column(scale=2):
                    compare_output = gr.Textbox(
                        label="核验结果",
                        lines=23,
                        interactive=False,
                        placeholder="使用提示:\n"
                        "1. 设置JSONL文件路径和图片文件夹路径。\n"
                        "2. 可选择提供bad_images.txt文件路径。\n"
                        "3. 选择处理模式(自动删除、交互式或跳过)。\n"
                        "4. 点击核验按钮开始比对和清理。",
                    )

            # 添加事件绑定
            compare_btn.click(
                fn=compare_and_clean,
                inputs=[jsonl_file_path, images_folder_path, mode, bad_images_file],
                outputs=compare_output,
            )

        with gr.Tab("步骤 6：图像增强"):
            with gr.Row():
                with gr.Column(scale=1):
                    images_dir = gr.Textbox(
                        label="图片输入目录",
                        value="./transfer_data/output/images",
                        placeholder="请输入图片目录路径",
                    )
                    output_dir = gr.Textbox(
                        label="图片输出目录（可选）",
                        value="./worked_data/output/images",
                        placeholder="留空表示原目录增强",
                    )
                    dataset_jsonl = gr.Textbox(
                        label="JSONL文件路径（可选）",
                        value="./transfer_data/output/dataset.jsonl",
                        placeholder="请输入JSONL文件路径（可选）",
                    )

                    with gr.Group():
                        gr.Markdown("#### 增强参数")
                        enhance_strategy = gr.Radio(
                            choices=[
                                ("确定性增强", "deterministic"),
                                ("随机增强", "random"),
                                ("全部增强", "all"),
                            ],
                            value="deterministic",
                            label="增强策略",
                        )

                        with gr.Row():
                            num_to_augment = gr.Number(
                                label="增强数量",
                                value=None,
                                minimum=0,
                                precision=0,
                                interactive=True,
                            )
                            augmentation_ratio = gr.Slider(
                                label="增强比例",
                                value=float(0.1),
                                minimum=0,
                                maximum=1,
                                step=0.01,
                                interactive=True,
                            )

                        random_seed = gr.Number(label="随机种子", value=42, precision=0)

                    with gr.Group():
                        gr.Markdown("#### 备份选项")
                        backup_original = gr.Checkbox(
                            label="备份原图（仅在原目录增强时有效）", value=False
                        )

                    enhance_btn = gr.Button("🔄 开始增强")

                with gr.Column(scale=2):
                    enhance_output = gr.Textbox(
                        label="增强结果",
                        lines=35,
                        interactive=False,
                        placeholder="使用提示:\n"
                        "1. 确定性增强策略通过等间距采样，相同输入参数每次产生相同结果。\n"
                        "2. 随机增强策略基于随机种子进行采样，相同种子每次产生相同结果。\n"
                        "3. 增强数量：指定具体要增强的图像数量，默认留空则使用增强比例计算。\n"
                        "4. 增强比例：当增强数量默认时生效, 0表示不进行增强。\n"
                        "5. 全部增强：对所有图像进行增强，忽略数量和比例设置。\n",
                    )

            # 策略变化的交互逻辑
            def update_params(strategy):
                if strategy == "all":
                    return gr.update(interactive=False, value=0), gr.update(
                        interactive=False, value=0.1
                    )
                else:
                    return gr.update(interactive=True), gr.update(interactive=True)

            enhance_strategy.change(
                fn=update_params,
                inputs=enhance_strategy,
                outputs=[num_to_augment, augmentation_ratio],
            )

            # 添加事件绑定
            def wrap_enhance_images_with_backup(
                images_dir,
                output_dir,
                dataset_jsonl,
                num_to_augment,
                augmentation_ratio,
                enhance_strategy,
                random_seed,
                backup_original,
            ):
                # 将Gradio的Number转换为Python的int/float
                # 修改：保留用户输入的0值，而不是转换为None
                if num_to_augment is not None and num_to_augment >= 0:
                    num_to_augment = int(num_to_augment)
                else:
                    num_to_augment = None

                # 修改：保留用户输入的0值，而不是转换为默认值0.1
                if augmentation_ratio is not None and augmentation_ratio >= 0:
                    augmentation_ratio = float(augmentation_ratio)
                else:
                    augmentation_ratio = 0.1

                if not output_dir.strip():  # 原地增强
                    return enhance_images_in_place(
                        images_dir,
                        dataset_jsonl,
                        num_to_augment,
                        augmentation_ratio,
                        enhance_strategy,
                        backup_original=backup_original,
                        random_seed=int(random_seed),
                    )
                else:
                    return enhance_images_to_new_dir(
                        images_dir,
                        output_dir,
                        dataset_jsonl,
                        num_to_augment,
                        augmentation_ratio,
                        enhance_strategy,
                        random_seed=int(random_seed),
                    )

            enhance_btn.click(
                fn=wrap_enhance_images_with_backup,
                inputs=[
                    images_dir,
                    output_dir,
                    dataset_jsonl,
                    num_to_augment,
                    augmentation_ratio,
                    enhance_strategy,
                    random_seed,
                    backup_original,
                ],
                outputs=enhance_output,
            )

        with gr.Tab("步骤 7：修改路径"):
            with gr.Row():
                with gr.Column(scale=1):
                    input_jsonl = gr.Textbox(
                        label="输入JSONL文件路径",
                        value="./transfer_data/output/dataset.jsonl",
                        placeholder="请输入输入JSONL文件路径",
                    )
                    output_jsonl = gr.Textbox(
                        label="输出JSONL文件路径",
                        value="./worked_data/output/modified_dataset.jsonl",
                        placeholder="请输入输出JSONL文件路径",
                    )
                    old_prefix = gr.Textbox(
                        label="旧路径前缀",
                        value="images/",
                        placeholder="请输入需要替换的旧路径前缀",
                    )
                    new_prefix = gr.Textbox(
                        label="新路径前缀",
                        value="./worked_data/output/images/",
                        placeholder="请输入新的路径前缀",
                    )

                    with gr.Group():
                        gr.Markdown("#### 验证选项")
                        validate_paths = gr.Checkbox(
                            label="验证新路径是否存在",
                            value=False,
                        )

                    modify_btn = gr.Button("✏️ 修改路径")

                with gr.Column(scale=2):
                    modify_output = gr.Textbox(
                        label="修改结果",
                        lines=23,
                        interactive=False,
                        placeholder="使用提示:\n"
                        "1.默认新路径前缀与图片目录一致，新路径存在，无需验证。\n"
                        "2.若部分图片路径不存在，请检查图片增强环节是否选择了[原始增强]?\n"
                        "3.若选择了[原始增强],图片路径在transfer_data/output/images下。\n"
                        "回到步骤5,增强后图片默认输出到worked_data/output/images下。",
                    )

            # 添加事件绑定
            def wrap_modify_image_paths(
                input_jsonl, output_jsonl, old_prefix, new_prefix, validate_paths
            ):
                # 导入所需的函数
                from worked_data.modify_image_paths import (
                    modify_image_paths_with_validation,
                )

                return modify_image_paths_with_validation(
                    input_jsonl=input_jsonl,
                    output_jsonl=output_jsonl,
                    old_prefix=old_prefix,
                    new_prefix=new_prefix,
                    validate_paths=validate_paths,
                )

            modify_btn.click(
                fn=wrap_modify_image_paths,
                inputs=[
                    input_jsonl,
                    output_jsonl,
                    old_prefix,
                    new_prefix,
                    validate_paths,
                ],
                outputs=modify_output,
            )

        with gr.Tab("步骤 8：数据集分析"):
            with gr.Row():
                with gr.Column(scale=1, min_width=100):
                    with gr.Group():
                        input_jsonl_path = gr.Textbox(
                            label="输入JSONL文件路径",
                            value="./worked_data/output/modified_dataset.jsonl",
                            placeholder="请输入要分析的JSONL文件路径",
                            scale=1,
                        )
                        upload_btn = gr.UploadButton(
                            label="📁 上传其他数据集", file_types=[".jsonl"], scale=1
                        )
                    output_html_path = gr.Textbox(
                        label="输出HTML报告路径",
                        value="analysis_report.html",  # 默认报告名
                        placeholder="请输入HTML报告文件名(如 analysis_report.html)",
                    )

                    with gr.Group():
                        gr.Markdown("#### 分析选项")
                        use_ai_analysis = gr.Checkbox(label="启用 AI 分析", value=False)

                    with gr.Group(visible=False) as ai_group:  # 默认隐藏 AI 配置
                        gr.Markdown("#### 书生 API 配置")
                        ai_api_key = gr.Textbox(
                            label="API Key",
                            type="password",  # 密码框，不显示内容
                            placeholder="请输入书生 API Key",
                        )
                        ai_model = gr.Dropdown(
                            label="模型选择",
                            choices=[
                                "intern-latest",
                                "intern-s1",
                                "intern-s1-mini",
                                "internvl3.5-241b-a28b",
                                "internvl3-latest",
                                "internvl3-78b",
                            ],
                            value="intern-latest",
                        )

                    analyze_btn = gr.Button("📊 开始分析")

                with gr.Column(scale=2, min_width=600):
                    #  两个图表并排
                    with gr.Row():
                        latex_length_chart = gr.Image(
                            label="LaTeX 长度分布图",
                            show_label=True,
                            width=300,
                            height=250,
                            interactive=False,
                        )
                        formula_type_chart = gr.Image(
                            label="公式类型分布图",
                            show_label=True,
                            width=300,
                            height=250,
                            interactive=False,
                        )

                    # 文本结果摘要
                    analysis_result_summary = gr.Textbox(
                        label="分析结果摘要", lines=5, interactive=False,
                        placeholder="💡图片生成说明:\n"
                                    "分析图表会保存在项目目录下的 ./worked_data/output 文件夹中。\n"
                                    "如果图片未显示，您可以在文件系统中直接访问这些 PNG 文件。"
                    )

                    # HTML报告展示组件
                    report_html_display = gr.HTML(label="详细分析报告", show_label=True)

            # 添加事件绑定：当上传按钮被点击时，更新文本框的值
            def update_input_path(file):
                if file is not None:
                    return file.name
                return ""

            upload_btn.upload(
                fn=update_input_path, inputs=upload_btn, outputs=input_jsonl_path
            )

            #  AI 选项切换逻辑
            def toggle_ai_options(use_ai):
                return gr.update(visible=use_ai)

            use_ai_analysis.change(
                fn=toggle_ai_options, inputs=use_ai_analysis, outputs=ai_group
            )

            #  添加事件绑定
            def wrap_analyze_jsonl(
                input_jsonl_path,
                output_html_path,
                use_ai_analysis,
                ai_api_key,
                ai_model,
            ):
                #  增加校验：如果启用了 AI 但 Key 为空，直接提示用户
                if use_ai_analysis and (not ai_api_key or not ai_api_key.strip()):
                    return (
                        None,
                        None,
                        "<p>❌ 请先输入有效的书生 API Key。</p>",
                        "❌ 请先输入有效的书生 API Key。",
                    )

                # 导入 OUTPUT_DIR 以便找到生成的图表
                from worked_data.analyze_jsonl import OUTPUT_DIR as ANALYSIS_OUTPUT_DIR

                try:
                    # 读取数据文件
                    data_frame = pd.read_json(input_jsonl_path, lines=True)

                    # 统计信息
                    # 根据数据格式计算统计信息
                    if "latex" in data_frame.columns:
                        # 原始公式数据格式
                        stats_dict = {
                            "total_formulas": len(data_frame),
                            "avg_latex_length": data_frame["latex"].str.len().mean(),
                            "min_latex_length": data_frame["latex"].str.len().min(),
                            "max_latex_length": data_frame["latex"].str.len().max(),
                        }
                    elif "messages" in data_frame.columns:
                        # 生成的数据集格式，从messages中提取LaTeX
                        def extract_latex_length(row):
                            try:
                                if (
                                    len(row["messages"]) > 1
                                    and "content" in row["messages"][1]
                                ):
                                    return len(row["messages"][1]["content"])
                                else:
                                    return 0
                            except (IndexError, KeyError, TypeError):
                                return 0

                        latex_lengths = data_frame.apply(extract_latex_length, axis=1)
                        stats_dict = {
                            "total_formulas": len(data_frame),
                            "avg_latex_length": latex_lengths.mean(),
                            "min_latex_length": latex_lengths.min(),
                            "max_latex_length": latex_lengths.max(),
                        }
                    else:
                        # 其他格式，提供基础统计信息
                        stats_dict = {
                            "total_formulas": len(data_frame),
                            "avg_latex_length": 0,
                            "min_latex_length": 0,
                            "max_latex_length": 0,
                        }

                    # 公式类型分布
                    if "tags" in data_frame.columns:
                        formula_types = (
                            data_frame["tags"]
                            .apply(
                                lambda x: (
                                    x.get("formula_type", "unknown")
                                    if isinstance(x, dict)
                                    else "unknown"
                                )
                            )
                            .value_counts()
                        )
                    else:
                        formula_types = pd.Series(dtype=int)  # 空的Series

                    # 调用后端分析函数（现在返回 df 和 report_html）
                    df, report_html = analyze_jsonl(
                        input_path=input_jsonl_path,
                        output_html=(
                            output_html_path if output_html_path.strip() else None
                        ),
                        use_ai=use_ai_analysis,
                        ai_key=ai_api_key if use_ai_analysis else None,
                        ai_model=ai_model if use_ai_analysis else None,
                    )

                    # 构造简要文本结果（可选）
                    result_msg = f"✅ 分析完成！\n\n"
                    result_msg += f"📊 读取样本数: {len(df)}\n"
                    result_msg += f"📁 生成的图表保存在: {ANALYSIS_OUTPUT_DIR}\n"
                    if output_html_path.strip():
                        result_msg += f"📄 HTML 报告: {output_html_path}\n"

                    #  加载生成的图表
                    length_chart_path = os.path.join(
                        ANALYSIS_OUTPUT_DIR, "latex_length_dist.png"
                    )
                    type_chart_path = os.path.join(
                        ANALYSIS_OUTPUT_DIR, "formula_type_dist.png"
                    )

                    # 返回结果：图表 + 完整 HTML 报告 + 简要文本（可选保留）
                    return (
                        length_chart_path,
                        type_chart_path,
                        report_html,  # 直接返回 HTML 字符串
                        result_msg,
                    )

                except FileNotFoundError as file_not_found_error:
                    error_msg = f"❌ 文件未找到: {file_not_found_error}"
                    return None, None, "<p>❌ 分析失败</p>", error_msg
                except Exception as general_exception:
                    import traceback

                    error_info = f"❌ 分析失败: {str(general_exception)}\n详细错误信息:\n{traceback.format_exc()}"
                    return None, None, "<p>❌ 分析失败</p>", error_info

            analyze_btn.click(
                fn=wrap_analyze_jsonl,
                inputs=[
                    input_jsonl_path,
                    output_html_path,
                    use_ai_analysis,
                    ai_api_key,
                    ai_model,
                ],
                outputs=[
                    latex_length_chart,  # 输出1：长度分布图
                    formula_type_chart,  # 输出2：类型分布图
                    report_html_display,  # 输出3：完整 HTML 报告
                    analysis_result_summary,  # 输出4：简要文本结果
                ],
            )

    return demo_app


if __name__ == "__main__":
    APP = create_app()
    APP.launch(inbrowser=True, share=False)
