import gradio as gr
import sys
import os

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入后端函数
from origin_data.check import check_columns
from transfer_data.convert import convert_to_latex_jsonl 
from transfer_data.generate_formula_images import generate_formula_images
from transfer_data.compare import compare_and_clean
from worked_data.enhance_image import enhance_images_in_place, enhance_images_to_new_dir
from worked_data.analyze_jsonl import analyze_jsonl

def create_app():
    with gr.Blocks(
        title="数学公式数据集处理流水线",
        theme=gr.themes.Soft()
    ) as demo:
        
        # 紫色标题 + 步骤导航（无滚动条）
        gr.Markdown("""
        <h2 style="margin: 0 0 15px 0; color: #6864f4; font-size: 28px; font-weight: bold;text-align: center;margin-bottom: 40px;">
        🧪 数学公式数据集处理流水线
        </h2>
        """)
        
        with gr.Tab("步骤 1：检查原始数据"):
            with gr.Row():
                with gr.Column(scale=1):
                    file_input = gr.File(
                        label="上传原始数据",
                        file_types=[".parquet"]
                    )
                    check_btn = gr.Button("🔍 检查数据")
                
                with gr.Column(scale=2):
                    check_output = gr.Textbox(
                        label="检查结果",
                        lines=11,
                        interactive=False
                    )

            # 添加事件绑定
            check_btn.click(
                fn=check_columns,
                inputs=file_input,
                outputs=check_output
            )
        
        with gr.Tab("步骤 2：转换格式"):
            with gr.Row():
                with gr.Column(scale=1):
                    step2_file_input = gr.File(
                        label="上传原始数据集",
                        file_types=[".parquet"]
                    )
                    with gr.Group():
                        gr.Markdown("#### 采样参数")
                        sample_interval = gr.Number(
                            label="采样间隔",
                            value=20,minimum=0,
                            precision=0
                        )
                        target_samples = gr.Number(
                            label="目标样本数",
                            value=300,minimum=0,
                            precision=0
                        )
                        total_records_limit = gr.Number(
                            label="总记录限制",
                            value=100000,
                            interactive=False,
                        )
                    
                    convert_btn = gr.Button("🔄 转换为JSONL")
                
                with gr.Column(scale=2):
                    convert_output = gr.Textbox(
                        label="转换结果",
                        lines=25,
                        interactive=False
                    )
            
            # 添加事件绑定
            convert_btn.click(
                fn=convert_to_latex_jsonl,
                inputs=[
                    step2_file_input, 
                    gr.State(""), 
                    sample_interval,
                    target_samples,
                    total_records_limit
                ],
                outputs=convert_output
            )
        
        with gr.Tab("步骤 3：生成公式图"):
            with gr.Row():
                with gr.Column(scale=1):
                    output_dir = gr.Textbox(
                        label="输出目录",
                        value="transfer_data/output",
                        placeholder="请输入输出目录路径"
                    )
                    input_jsonl = gr.Textbox(
                        label="输入JSONL文件路径",
                        value="transfer_data/input/formulas.jsonl",
                        placeholder="请输入JSONL文件路径"
                    )
                    user_prompt = gr.Textbox(
                        label="用户提示词",
                        value="请根据以下 LaTeX 公式生成相应的数学表达式图片。",
                        lines=3
                    )
                    
                    with gr.Group():
                        gr.Markdown("#### 渲染参数")
                        dpi = gr.Number(label="DPI", value=100, precision=0,)
                        fontsize = gr.Number(label="字体大小", value=20, precision=0)
                        
                        with gr.Row():
                            figsize_width = gr.Number(label="图像宽度", value=5)
                            figsize_height = gr.Number(label="图像高度", value=3)
                    
                    with gr.Group():
                        gr.Markdown("#### 处理策略")
                        failure_strategy = gr.Radio(
                            choices=[
                                ("跳过失败样本", "skip"),
                                ("包含占位符", "include_failed"),
                                ("记录失败ID供后续处理", "interactive")
                            ],
                            value="skip",
                            label="失败处理策略"
                        )
                    
                    generate_btn = gr.Button("🎨 生成公式图像")
                
                with gr.Column(scale=2):
                    generate_output = gr.Textbox(
                        label="生成结果",
                        lines=45,
                        interactive=False
                    )
            
            # 添加事件绑定
            def wrap_generate_formula_images(output_dir, input_jsonl, user_prompt, image_prefix, dpi, figsize_width, figsize_height, fontsize, failure_strategy):
                figsize = (figsize_width, figsize_height)
                return generate_formula_images(
                    output_dir=output_dir,
                    input_jsonl=input_jsonl,
                    user_prompt=user_prompt,
                    image_prefix=image_prefix,
                    dpi=dpi,
                    figsize=figsize,
                    fontsize=fontsize,
                    failure_strategy=failure_strategy
                )
            
            generate_btn.click(
                fn=wrap_generate_formula_images,
                inputs=[
                    output_dir,
                    input_jsonl,
                    user_prompt,
                    gr.State("formula"),  # image_prefix 参数固定为 "formula"
                    dpi,
                    figsize_width,
                    figsize_height,
                    fontsize,
                    failure_strategy
                ],
                outputs=generate_output
            )
        
        with gr.Tab("步骤 4：核验图集"):
            with gr.Row():
                with gr.Column(scale=1):
                    jsonl_file_path = gr.Textbox(
                        label="JSONL文件路径",
                        value="./transfer_data/output/dataset.jsonl",
                        placeholder="请输入JSONL文件路径"
                    )
                    images_folder_path = gr.Textbox(
                        label="图片文件夹路径",
                        value="./transfer_data/output/images",
                        placeholder="请输入图片文件夹路径"
                    )
                    bad_images_file = gr.Textbox(
                        label="Bad Images文件路径（可选）",
                        placeholder="请输入bad_images.txt文件路径（可选）"
                    )
                    
                    with gr.Group():
                        gr.Markdown("#### 处理模式")
                        mode = gr.Radio(
                            choices=[
                                ("自动删除不存在的图片条目", "auto"),
                                ("仅返回统计信息，供用户决定", "interactive"),
                                ("跳过处理", "skip")
                            ],
                            value="auto",
                            label="处理模式"
                        )
                    
                    compare_btn = gr.Button("🔍 核验图集")
                
                with gr.Column(scale=2):
                    compare_output = gr.Textbox(
                        label="核验结果",
                        lines=26,
                        interactive=False,
                        placeholder="请在图片文件夹中进行人工核验，删除不合格的图片后再点击核验按钮。"
                    )
            
            # 添加事件绑定
            compare_btn.click(
                fn=compare_and_clean,
                inputs=[
                    jsonl_file_path,
                    images_folder_path,
                    mode,
                    bad_images_file
                ],
                outputs=compare_output
            )
        
        with gr.Tab("步骤 5：图像增强"):
            with gr.Row():
                with gr.Column(scale=1):
                    images_dir = gr.Textbox(
                        label="图片输入目录",
                        value="./transfer_data/output/images",
                        placeholder="请输入图片目录路径"
                    )
                    output_dir = gr.Textbox(
                        label="图片输出目录（可选）",
                        value="./worked_data/output/images",
                        placeholder="留空表示原目录增强"
                    )
                    dataset_jsonl = gr.Textbox(
                        label="JSONL文件路径（可选）",
                        value="./transfer_data/output/dataset.jsonl",
                        placeholder="请输入JSONL文件路径（可选）"
                    )
                    
                    with gr.Group():
                        gr.Markdown("#### 增强参数")
                        enhance_strategy = gr.Radio(
                            choices=[
                                ("确定性增强", "deterministic"),
                                ("随机增强", "random"),
                                ("全部增强", "all")
                            ],
                            value="deterministic",
                            label="增强策略"
                        )
                        
                        with gr.Row():
                            num_to_augment = gr.Number(
                                label="增强数量",
                                value=0,
                                precision=0,
                                interactive=True
                            )
                            augmentation_ratio = gr.Slider(
                                label="增强比例",
                                value=float(0.1),
                                minimum=0, 
                                maximum=1, 
                                step=0.01,
                                interactive=True
                            )
                        
                        random_seed = gr.Number(
                            label="随机种子",
                            value=42,
                            precision=0
                        )
                    
                    with gr.Group():
                        gr.Markdown("#### 备份选项")
                        backup_original = gr.Checkbox(
                            label="备份原图（仅在原目录增强时有效）",
                            value=False
                        )
                    
                    enhance_btn = gr.Button("🔄 开始增强")
                
                with gr.Column(scale=2):
                    enhance_output = gr.Textbox(
                        label="增强结果",
                        lines=37,
                        interactive=False,
                        placeholder="tip:\n "
                        "1.确定性增强策略通过等间距采样,相同输入参数每次产生相同增强结果。\n"
                    )
            
            # 策略变化的交互逻辑
            def update_params(strategy):
                if strategy == "all":
                    return gr.update(interactive=False, value=0), gr.update(interactive=False, value=0.1)
                else:
                    return gr.update(interactive=True), gr.update(interactive=True)
            
            enhance_strategy.change(
                fn=update_params,
                inputs=enhance_strategy,
                outputs=[num_to_augment, augmentation_ratio]
            )
            
            # 添加事件绑定
            def wrap_enhance_images_with_backup(
                images_dir, output_dir, dataset_jsonl, 
                num_to_augment, augmentation_ratio, 
                enhance_strategy, random_seed, backup_original
            ):
                # 将Gradio的Number转换为Python的int/float
                if num_to_augment is not None and num_to_augment > 0:
                    num_to_augment = int(num_to_augment)
                else:
                    num_to_augment = None
                
                if augmentation_ratio is not None and augmentation_ratio > 0:
                    augmentation_ratio = float(augmentation_ratio)
                else:
                    augmentation_ratio = 0.1
                
                if not output_dir.strip():  # 原地增强
                    return enhance_images_in_place(
                        images_dir, dataset_jsonl,
                        num_to_augment, augmentation_ratio, enhance_strategy,
                        backup_original=backup_original,
                        random_seed=int(random_seed)
                    )
                else:
                    return enhance_images_to_new_dir(
                        images_dir, output_dir, dataset_jsonl,
                        num_to_augment, augmentation_ratio, enhance_strategy,
                        random_seed=int(random_seed)
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
                    backup_original
                ],
                outputs=enhance_output
            )

        with gr.Tab("步骤 6：修改路径"):
            with gr.Row():
                with gr.Column(scale=1):
                    input_jsonl = gr.Textbox(
                        label="输入JSONL文件路径",
                        value="./transfer_data/output/dataset.jsonl",
                        placeholder="请输入输入JSONL文件路径"
                    )
                    output_jsonl = gr.Textbox(
                        label="输出JSONL文件路径",
                        value="./worked_data/output/modified_dataset.jsonl",
                        placeholder="请输入输出JSONL文件路径"
                    )
                    old_prefix = gr.Textbox(
                        label="旧路径前缀",
                        value="images/",
                        placeholder="请输入需要替换的旧路径前缀"
                    )
                    new_prefix = gr.Textbox(
                        label="新路径前缀",
                        value="./worked_data/output/images/",
                        placeholder="请输入新的路径前缀"
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
                        placeholder="tip:\n "
                                "1.默认新路径前缀与图片目录一致，新路径存在，无需验证。\n"
                                "2.若部分图片路径不存在，请检查图片增强环节是否选择了[原始增强]? \n"
                                "3.若选择了[原始增强],图片路径在transfer_data/output/images下。\n" 
                                "回到步骤5,增强后图片默认输出到worked_data/output/images下。" 
                    )

            
            # 添加事件绑定
            def wrap_modify_image_paths(input_jsonl, output_jsonl, old_prefix, new_prefix, validate_paths):
                # 导入所需的函数
                from worked_data.modify_image_paths import modify_image_paths_with_validation
                
                return modify_image_paths_with_validation(
                    input_jsonl=input_jsonl,
                    output_jsonl=output_jsonl,
                    old_prefix=old_prefix,
                    new_prefix=new_prefix,
                    validate_paths=validate_paths
                )
            
            modify_btn.click(
                fn=wrap_modify_image_paths,
                inputs=[
                    input_jsonl,
                    output_jsonl,
                    old_prefix,
                    new_prefix,
                    validate_paths
                ],
                outputs=modify_output
            )
        
        with gr.Tab("步骤 7：数据集分析"):
            with gr.Row():
                with gr.Column(scale=1, min_width=100):
                    with gr.Group():
                        input_jsonl_path = gr.Textbox(
                            label="输入JSONL文件路径",
                            value="./worked_data/output/modified_dataset.jsonl",
                            placeholder="请输入要分析的JSONL文件路径",
                            scale=1  
                        )
                        upload_btn = gr.UploadButton(
                            label="📁 上传其他数据集",
                            file_types=[".jsonl"],
                            scale=1  
                        )
                    output_html_path = gr.Textbox(
                        label="输出HTML报告路径",
                        value="analysis_report.html",  # 默认报告名
                        placeholder="请输入HTML报告文件名（如 analysis_report.html）"
                    )
                    
                    with gr.Group():
                        gr.Markdown("#### 分析选项")
                        use_ai_analysis = gr.Checkbox(
                            label="启用 AI 分析（需要书生 API Key）",
                            value=False
                        )
                        
                    with gr.Group(visible=False) as ai_group:  # 默认隐藏 AI 配置
                        gr.Markdown("#### 书生 API 配置")
                        ai_api_key = gr.Textbox(
                            label="API Key",
                            type="password",  # 密码框，不显示内容
                            placeholder="请输入书生 API Key"
                        )
                        ai_model = gr.Dropdown(
                            label="模型选择",
                            choices=[
                                "intern-latest",
                                "intern-s1", 
                                "intern-s1-mini",
                                "internvl3.5-241b-a28b",
                                "internvl3-latest",
                                "internvl3-78b"
                            ],
                            value="intern-latest"
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
                            interactive=False
                        )
                        formula_type_chart = gr.Image(
                            label="公式类型分布图",
                            show_label=True,
                            width=300,
                            height=250,
                            interactive=False
                        )
                    
                    # 文本结果摘要
                    analysis_result_summary = gr.Textbox(
                        label="分析结果摘要",
                        lines=5,
                        interactive=False
                    )
                    # HTML报告展示组件
                    report_html_display = gr.HTML(
                        label="详细分析报告",
                        show_label=True
                    )
                    
                    

            # 添加事件绑定：当上传按钮被点击时，更新文本框的值
            def update_input_path(file):
                if file is not None:
                    return file.name
                return ""
            
            upload_btn.upload(
                fn=update_input_path,
                inputs=upload_btn,
                outputs=input_jsonl_path
            )
            
            #  AI 选项切换逻辑
            def toggle_ai_options(use_ai):
                return gr.update(visible=use_ai)
            
            use_ai_analysis.change(
                fn=toggle_ai_options,
                inputs=use_ai_analysis,
                outputs=ai_group
            )
            
            #  添加事件绑定
            def wrap_analyze_jsonl(input_jsonl_path, output_html_path, use_ai_analysis, ai_api_key, ai_model):
                #  增加校验：如果启用了 AI 但 Key 为空，直接提示用户
                if use_ai_analysis and (not ai_api_key or not ai_api_key.strip()):
                    return None, None, "<p>❌ 请先输入有效的书生 API Key。</p>", "❌ 请先输入有效的书生 API Key。"
                
                # 导入 OUTPUT_DIR 以便找到生成的图表
                from worked_data.analyze_jsonl import OUTPUT_DIR as ANALYSIS_OUTPUT_DIR
                
                try:
                    # 调用后端分析函数（现在返回 df 和 report_html）
                    df, report_html = analyze_jsonl(
                        input_path=input_jsonl_path,
                        output_html=output_html_path if output_html_path.strip() else None,
                        use_ai=use_ai_analysis,
                        ai_key=ai_api_key if use_ai_analysis else None,
                        ai_model=ai_model if use_ai_analysis else None
                    )
                    
                    # 构造简要文本结果（可选）
                    result_msg = f"✅ 分析完成！\n\n"
                    result_msg += f"📊 读取样本数: {len(df)}\n"
                    result_msg += f"📁 生成的图表保存在: {ANALYSIS_OUTPUT_DIR}\n"
                    if output_html_path.strip():
                        result_msg += f"📄 HTML 报告: {output_html_path}\n"
                    
                    #  加载生成的图表
                    length_chart_path = os.path.join(ANALYSIS_OUTPUT_DIR, "latex_length_dist.png")
                    type_chart_path = os.path.join(ANALYSIS_OUTPUT_DIR, "formula_type_dist.png")
                    
                    # 返回结果：图表 + 完整 HTML 报告 + 简要文本（可选保留）
                    return (
                        length_chart_path,
                        type_chart_path,
                        report_html,  # 直接返回 HTML 字符串
                        result_msg
                    )
                
                except FileNotFoundError as e:
                    error_msg = f"❌ 文件未找到: {e}"
                    return None, None, "<p>❌ 分析失败</p>", error_msg
                except Exception as e:
                    error_msg = f"❌ 分析失败: {str(e)}"
                    return None, None, "<p>❌ 分析失败</p>", error_msg
        
            analyze_btn.click(
                fn=wrap_analyze_jsonl,
                inputs=[
                    input_jsonl_path,
                    output_html_path,
                    use_ai_analysis,
                    ai_api_key,
                    ai_model
                ],
                outputs=[
                    latex_length_chart,     # 输出1：长度分布图
                    formula_type_chart,     # 输出2：类型分布图
                    report_html_display,    # 输出3：完整 HTML 报告
                    analysis_result_summary  # 输出4：简要文本结果
                ]
            )

        with gr.Tab("使用说明"):
            gr.Markdown("待开发...")
    return demo

if __name__ == "__main__":
    app = create_app()
    app.launch(inbrowser=False, share=False)