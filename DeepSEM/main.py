import os
import pandas as pd
import numpy as np
import argparse
from typing import Optional, Dict
from enum import Enum
import tempfile
import shutil
import traceback
# --- FastAPI 和相关库导入 ---
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Form
from fastapi.concurrency import run_in_threadpool
import io

# --- 您的模型导入 ---
# 假设您的 src 目录与此文件在同一级别，或者已正确安装
from src.DeepSEM_cell_type_non_specific_GRN_model import non_celltype_GRN_model
from src.DeepSEM_cell_type_specific_GRN_model import celltype_GRN_model
from src.DeepSEM_cell_type_test_non_specific_GRN_model import test_non_celltype_GRN_model
from src.DeepSEM_cell_type_test_specific_GRN_model import celltype_GRN_model as test_celltype_GRN_model
from src.DeepSEM_embed_model import deepsem_embed
from src.DeepSEM_generation_model import deepsem_generation

# --- FastAPI 应用实例 ---
# 由于没有需要在启动时加载的全局数据，我们暂时不需要 lifespan 事件
app = FastAPI(
    title="DeepSEM GRN Inference API",
    description="上传基因表达矩阵和可选的先验网络，推断基因调控网络。",
)

# --- 定义任务类型的枚举，用于API文档和验证 ---
class TaskType(str, Enum):
    non_celltype_GRN = "non_celltype_GRN"
    celltype_GRN = "celltype_GRN"
    simulation = "simulation"
    embedding = "embedding"

# --- 核心处理函数 ---
def perform_deepsem_inference(
    expression_content: bytes,
    network_content: Optional[bytes],
    task: str,
    params: Dict
) -> pd.DataFrame:
    """
    这个函数包含了原始脚本中的所有核心计算逻辑。
    它被设计为可以在后台线程中运行，以避免阻塞服务器。
    它通过创建临时文件来与需要文件路径的旧模型代码兼容。
    """
    # 使用临时目录来安全地处理输入和输出文件
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 1. 准备输入文件路径
            data_file_path = os.path.join(temp_dir, 'data.csv')
            net_file_path = os.path.join(temp_dir, 'label.csv') if network_content else None
            result_dir_path = os.path.join(temp_dir, 'results')
            os.makedirs(result_dir_path, exist_ok=True)

            # 2. 将上传的文件内容写入临时文件
            with open(data_file_path, 'wb') as f:
                f.write(expression_content)
            
            if net_file_path:
                with open(net_file_path, 'wb') as f:
                    f.write(network_content)

            # 3. 构建类似于 argparse 的 opt 对象
            # 使用 argparse.Namespace 来模拟命令行解析的结果
            opt = argparse.Namespace(
                data_file=data_file_path,
                net_file=net_file_path,
                save_name=result_dir_path, # 将结果保存到临时目录中
                task=task,
                **params # 传入所有其他超参数
            )
            
            # 4. 运行原始脚本的核心逻辑
            # 这部分代码直接从您的原始脚本中迁移而来
            model = None
            if opt.task == 'non_celltype_GRN':
                if opt.setting == 'default':
                    opt.beta, opt.alpha, opt.K1, opt.K2, opt.n_hidden, opt.gamma, opt.lr, opt.lr_step_size, opt.batch_size = 1, 100, 1, 2, 128, 0.95, 1e-4, 0.99, 64
                model = non_celltype_GRN_model(opt) if opt.setting == 'default' else test_non_celltype_GRN_model(opt)
                model.train_model()

            elif opt.task == 'celltype_GRN':
                if opt.setting == 'default':
                    opt.beta, opt.alpha, opt.K1, opt.K2, opt.n_hidden, opt.gamma, opt.lr, opt.lr_step_size, opt.batch_size = 0.01, 1, 1, 2, 128, 0.95, 1e-4, 0.99, 64
                model = celltype_GRN_model(opt) if opt.setting == 'default' else test_celltype_GRN_model(opt)
                model.train_model()

            elif opt.task == 'simulation':
                if opt.setting == 'default':
                    opt.n_epochs, opt.beta, opt.alpha, opt.K1, opt.K2, opt.n_hidden, opt.gamma, opt.lr, opt.lr_step_size, opt.batch_size = 120, 1, 10, 1, 2, 128, 0.95, 1e-4, 0.99, 64
                model = deepsem_generation(opt)
                model.train_model()

            elif opt.task == 'embedding':
                if opt.setting == 'default':
                    opt.n_epochs, opt.beta, opt.alpha, opt.K1, opt.K2, opt.n_hidden, opt.gamma, opt.lr, opt.lr_step_size, opt.batch_size, opt.K = 120, 1, 10, 1, 2, 128, 0.95, 1e-4, 0.99, 64, 1
                model = deepsem_embed(opt)
                model.train_model()
            
            # 5. 读取模型生成的输出文件
            # 根据任务类型，模型会生成不同格式的输出文件
            if opt.task in ['non_celltype_GRN', 'celltype_GRN']:
                # GRN 推断任务生成的是边列表格式的 TSV 文件
                output_file_path = os.path.join(result_dir_path, 'GRN_inference_result.tsv')
                if not os.path.exists(output_file_path):
                    # 列出目录中的文件以便调试
                    existing_files = os.listdir(result_dir_path) if os.path.exists(result_dir_path) else []
                    print(f"错误：期望的文件不存在: {output_file_path}")
                    print(f"结果目录中的文件: {existing_files}")
                    raise FileNotFoundError(f"模型未在指定位置生成输出文件: {output_file_path}。目录中的文件: {existing_files}")
                
                # 读取 TSV 格式的边列表（列：TF, Target, EdgeWeight）
                result_df = pd.read_csv(output_file_path, sep='\t')
                
                # 重命名列以匹配 API 返回格式
                result_df = result_df.rename(columns={
                    'TF': 'source',
                    'Target': 'target',
                    'EdgeWeight': 'weight'
                })
                
                # 移除权重为0的边以减小输出大小
                result_df = result_df[result_df['weight'] != 0].copy()
                
                return result_df
            elif opt.task == 'simulation':
                # 模拟任务生成的是 h5ad 文件，需要特殊处理
                output_file_path = os.path.join(result_dir_path, 'simulation_reusult.h5ad')
                if not os.path.exists(output_file_path):
                    raise FileNotFoundError(f"模型未在指定位置生成输出文件: {output_file_path}")
                # TODO: 处理 h5ad 文件格式（如果需要返回模拟数据）
                raise NotImplementedError("simulation 任务的输出格式暂未实现")
            elif opt.task == 'embedding':
                # 嵌入任务生成的是 h5ad 文件，需要特殊处理
                output_file_path = os.path.join(result_dir_path, 'embedding.h5ad')
                if not os.path.exists(output_file_path):
                    raise FileNotFoundError(f"模型未在指定位置生成输出文件: {output_file_path}")
                # TODO: 处理 h5ad 文件格式（如果需要返回嵌入向量）
                raise NotImplementedError("embedding 任务的输出格式暂未实现")
            else:
                raise ValueError(f"未知的任务类型: {opt.task}")

        except Exception as e:
            # --- 修改后的部分 ---
            print(f"!!! DeepSEM 推断过程中发生严重错误: {e}")
            print("--- TRACEBACK START ---")
            traceback.print_exc() # 打印完整的错误堆栈跟踪信息到控制台
            print("--- TRACEBACK END ---")
            raise e # 重新抛出异常，以便 FastAPI 框架能捕获它并返回 500 错误
        # `with` 语句结束时，temp_dir 会被自动清理

# --- API 端点 ---

@app.post("/infer-grn/")
async def infer_gene_regulatory_network(
    # --- 文件上传 ---
    expression_file: UploadFile = File(..., description="输入的scRNA-seq基因表达矩阵 (CSV)"),
    network_file: Optional[UploadFile] = File(None, description="GRN的真实网络结构 (CSV), 如果可用 (可选)"),
    # --- 核心参数 ---
    task: TaskType = Form(TaskType.celltype_GRN, description="要执行的任务类型。"),
    setting: str = Form("default", description="是否使用默认超参数 ('default' 或 'test')"),
    # --- 超参数 (使用 Form 而不是 Query, 因为请求是 multipart/form-data) ---
    n_epochs: int = Form(120, description="训练的 Epoch 数量"),
    batch_size: int = Form(64, description="训练过程中的批次大小"),
    alpha: float = Form(100.0, description="W 的 L1 范数损失系数 (alpha)"),
    beta: float = Form(1.0, description="KL 项的损失系数 (beta)"),
    lr: float = Form(1e-4, description="RMSprop 的学习率"),
    # ... 在这里可以添加所有其他的 argparse 参数作为 Form 字段 ...
    n_hidden: int = Form(128, description="MLP 中隐藏神经元的数量"),
    K: int = Form(1, description="GMM 中的高斯核数量"),
    K1: int = Form(1, description="优化 MLP 的 Epoch 数"),
    K2: int = Form(2, description="优化 W 的 Epoch 数"),
    gamma: float = Form(0.95, description="学习率的衰减因子"),
    lr_step_size: float = Form(0.99, description="学习率衰减的步长")

):
    """
    接收 CSV 文件和参数，运行 DeepSEM 推断 GRN，并返回网络边列表。
    """
    # 验证文件类型
    if not expression_file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="无效的表达文件类型，请上传 CSV 文件。")
    if network_file and not network_file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="无效的网络文件类型，请上传 CSV 文件。")

    try:
        expression_content = await expression_file.read()
        network_content = await network_file.read() if network_file else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取上传文件失败: {e}")

    # 将所有超参数打包到一个字典中
    params = {
        "n_epochs": n_epochs,
        "setting": setting,
        "batch_size": batch_size,
        "alpha": alpha,
        "beta": beta,
        "lr": lr,
        "lr_step_size": lr_step_size,
        "gamma": gamma,
        "n_hidden": n_hidden,
        "K": K,
        "K1": K1,
        "K2": K2,
    }

    # --- 运行耗时任务 ---
    try:
        print("开始在后台线程中执行 DeepSEM GRN 推断...")
        result_df = await run_in_threadpool(
            perform_deepsem_inference,
            expression_content=expression_content,
            network_content=network_content,
            task=task.value,
            params=params
        )
        print("DeepSEM GRN 推断完成。")

        # 将 DataFrame 转换为 JSON 格式返回
        result_df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
        return result_df.to_dict(orient='records')

    except Exception as e:
        # 捕获后台任务抛出的异常
        raise HTTPException(status_code=500, detail=f"执行 GRN 推断时发生内部错误: {e}")


@app.get("/")
async def root():
    return {"message": "欢迎使用 DeepSEM GRN 推断 API。请访问 /docs 查看使用文档。"}

# --- 如何运行 ---
# 1. 确保安装了所有必要的库: pip install fastapi "uvicorn[standard]" pandas numpy
# 2. 确保您的 src 目录和这个文件在同一个目录下。
# 3. 在终端中运行: uvicorn main_deepsem:app --reload
# 4. 在浏览器中打开 http://127.0.0.1:8000/docs 查看交互式 API 文档。