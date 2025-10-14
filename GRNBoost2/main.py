# --- 必要的库导入 ---
import pandas as pd
import numpy as np
import io
import warnings
from typing import List

# FastAPI 相关导入
from fastapi import FastAPI, File, UploadFile, HTTPException, Path
from fastapi.concurrency import run_in_threadpool
from contextlib import asynccontextmanager

# Arboreto 和 Dask 相关导入
from arboreto.algo import grnboost2, genie3
from distributed import Client, LocalCluster

warnings.filterwarnings("ignore")

# --- 全局变量和应用生命周期管理 ---
cached_data = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用的生命周期管理器。
    """
    # 应用启动时执行
    print("应用启动... 正在创建 Dask 客户端...")
    try:
        cluster = LocalCluster()
        client = Client(cluster)
        cached_data["dask_client"] = client
        print(f"Dask 客户端创建完成。Dashboard 链接: {client.dashboard_link}")
    except Exception as e:
        print(f"创建 Dask 客户端失败: {e}")
        
    yield # 应用在此处运行
    
    # 应用关闭时执行
    print("应用关闭... 正在关闭 Dask 客户端...")
    client = cached_data.get("dask_client")
    if client:
        try:
            client.close()
            print("Dask 客户端已成功关闭。")
        except Exception as e:
            print(f"关闭 Dask 客户端时出错: {e}")
            
    cached_data.clear()
    print("应用关闭。")

# --- FastAPI 应用实例 ---
app = FastAPI(
    title="Arboreto GRN Inference API",
    description="上传一个基因表达矩阵和一个转录因子列表，使用 GENIE3 或 GRNBoost2 推断基因调控网络。",
    version="1.0.0",
    lifespan=lifespan
)


# --- 核心处理函数 ---
def perform_grn_inference(expression_df: pd.DataFrame, tf_names: List[str], algorithm: str):
    """
    这个函数包含了 Arboreto 的核心计算逻辑。
    
    参数:
    - expression_df: 基因表达矩阵 (Pandas DataFrame)，样本为行，基因为列。
    - tf_names: 转录因子名称列表。
    - algorithm: 使用的算法，'genie3' 或 'grnboost2'。
    """
    try:
        print(f"开始 GRN 推断，使用算法: {algorithm}")
        
        expression_genes = set(expression_df.columns)
        valid_tf_names = [tf for tf in tf_names if tf in expression_genes]
        if not valid_tf_names:
            raise ValueError("转录因子列表中的基因均未在表达矩阵的列名中找到。")
        print(f"在表达矩阵中找到 {len(valid_tf_names)}/{len(tf_names)} 个转录因子。")

        if algorithm == 'genie3':
            network = genie3(expression_data=expression_df, tf_names=valid_tf_names)
        elif algorithm == 'grnboost2':
            dask_client = cached_data.get("dask_client")
            if not dask_client:
                raise RuntimeError("Dask 客户端未初始化，无法运行 GRNBoost2。")
            network = grnboost2(expression_data=expression_df,
                                tf_names=valid_tf_names,
                                client_or_address=dask_client)
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        if not network.empty:
            max_value = network['importance'].max()
            if max_value > 0:
                network['importance'] = network['importance'] / max_value
        
        print("GRN 推断计算完成。")
        return network

    except Exception as e:
        print(f"GRN 推断过程中发生严重错误: {e}")
        raise e


# --- API 端点 ---
@app.post("/infer-grn/{algorithm_name}")
async def infer_gene_regulatory_network(
    algorithm_name: str = Path(..., description="要使用的算法: 'genie3' 或 'grnboost2'", enum=['genie3', 'grnboost2']),
    expression_file: UploadFile = File(..., description="基因表达矩阵 CSV 文件 (基因为行, 样本/细胞为列)"),
    tf_file: UploadFile = File(..., description="转录因子列表 CSV 文件 (单列，无表头)")
):
    """
    接收表达矩阵和转录因子列表，运行 Arboreto 推断 GRN，并返回网络边列表。
    """
    # 1. 读取并解析表达矩阵文件
    try:
        contents = await expression_file.read()
        buffer = io.StringIO(contents.decode('utf-8'))
        # 原始文件格式为：基因为行，样本为列。Arboreto 需要转置后的格式。
        expression_df = pd.read_csv(buffer, index_col=0)
        
        # --- 关键修正：转置 DataFrame ---
        # 将格式从 (基因 x 样本) 转换为 (样本 x 基因) 以满足 Arboreto 的要求
        expression_df = expression_df.T
        
        # 确保列名（基因名）是字符串类型
        expression_df.columns = expression_df.columns.astype(str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析表达矩阵 CSV 文件失败: {e}")

    # 2. 读取并解析转录因子文件
    try:
        tf_contents = await tf_file.read()
        tf_buffer = io.StringIO(tf_contents.decode('utf-8'))
        tf_df = pd.read_csv(tf_buffer, header=None)
        tf_names = tf_df[0].astype(str).tolist()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析转录因子 CSV 文件失败: {e}")

    # 3. 在后台线程中运行耗时的推断任务
    try:
        result_df = await run_in_threadpool(
            perform_grn_inference, 
            expression_df, 
            tf_names,
            algorithm_name
        )
        
        # 4. 格式化并返回结果
        result_df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
        return result_df.to_dict(orient='records')

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行 GRN 推断时发生内部错误: {str(e)}")


@app.get("/")
async def root():
    return {"message": "欢迎使用 Arboreto GRN 推断 API。请访问 /docs 查看使用文档。"}