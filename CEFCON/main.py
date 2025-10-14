# main.py
import pandas as pd
import numpy as np
import scanpy as sc
from anndata import AnnData
import cefcon as cf
import warnings
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool
from contextlib import asynccontextmanager
import io
import networkx as nx
warnings.filterwarnings("ignore")

# --- 全局变量和启动事件 ---

# 创建一个字典来缓存应用启动时加载的数据
# 这样可以避免在每次API请求时都重复加载这个网络
cached_data = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时执行
    print("应用启动... 正在加载先验网络...")
    prior_network_human = cf.datasets.load_human_prior_interaction_network(dataset='nichenet')
    # 将基因符号从人类转换为小鼠
    prior_network_mouse = cf.datasets.convert_human_to_mouse_network(prior_network_human)
    cached_data["prior_network"] = prior_network_mouse
    print("先验网络加载完成。")
    yield
    # 应用关闭时执行 (可选)
    cached_data.clear()
    print("应用关闭。")


# --- FastAPI 应用实例 ---
app = FastAPI(
    title="Cefcon GRN Inference API",
    description="上传一个基因表达矩阵 (CSV)，推断谱系特异性基因调控网络。",
    lifespan=lifespan
)


# --- 核心处理函数 ---
def perform_grn_inference(df: pd.DataFrame):
    """
    这个函数包含了原始脚本中的所有核心计算逻辑。
    它被设计为可以在后台线程中运行，以避免阻塞服务器。
    """
    try:
        # 1. 数据预处理
        df.index = df.index.str.upper()
        
        # 2. 创建 AnnData 对象
        adata = AnnData(df.values.T, dtype=np.float32)
        adata.obs_names = df.columns
        adata.var_names = df.index
        
        # 3. 标准化和对数转换
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
        adata.X = adata.X.astype(np.float32)
        adata.layers['log_transformed'] = adata.X.copy()
        
        # 4. 准备 Cefcon 数据
        # 从缓存中获取预加载的先验网络
        prior_network = cached_data.get("prior_network")
        if prior_network is None:
            raise RuntimeError("先验网络未加载，请检查应用启动流程。")
            
        data = cf.data_preparation(adata, prior_network)
        
        # 5. 运行 Cefcon 模型
        # 注意：如果你的机器有兼容的GPU，可以设置 cuda 参数，例如 cuda=0
        cefcon_GRN_model = cf.NetModel(epochs=250, repeats=1, seed=-1)
        cefcon_GRN_model.run(data['all'])
        
        # 6. 获取预测的网络
        # 这里我们直接在内存中获取结果，而不是保存到文件
        G_predicted = cefcon_GRN_model.get_network(
            edge_threshold_avgDegree=None,
            edge_threshold_zscore=None,
            output_file=None # 设置为 None 以避免写入文件
        )
        
        # 7. 转换为 Pandas DataFrame
        result_df = nx.to_pandas_edgelist(G_predicted)
        return result_df

    except Exception as e:
        # 在计算过程中捕获任何异常
        print(f"GRN 推断过程中发生错误: {e}")
        # 在实际应用中，你可能想要更详细的日志记录
        raise e


# --- API 端点 ---
@app.post("/infer-grn/")
async def infer_gene_regulatory_network(expression_file: UploadFile = File(..., description="基因表达矩阵 CSV 文件 (基因为行, 细胞/样本为列)")):
    """
    接收一个 CSV 文件，运行 Cefcon 推断 GRN，并返回网络边列表。
    """
    # 检查上传的是否是 CSV 文件
    if not expression_file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="无效的文件类型，请上传 CSV 文件。")

    try:
        # 从上传的文件中读取内容到 Pandas DataFrame
        # 使用 io.StringIO 将字节流转换为文本流
        contents = await expression_file.read()
        buffer = io.StringIO(contents.decode('utf-8'))
        df = pd.read_csv(buffer, index_col=0)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析 CSV 文件失败: {e}")

    # --- 运行耗时任务 ---
    # 使用 run_in_threadpool 将同步的、CPU密集型的函数
    # 放入独立的线程中执行，从而不会阻塞 FastAPI 的主事件循环。
    # 这对于保持服务器的响应性至关重要。
    try:
        print("开始在后台线程中执行 GRN 推断...")
        result_df = await run_in_threadpool(perform_grn_inference, df)
        print("GRN 推断完成。")

        # 将 DataFrame 转换为 JSON 格式返回
        # orient='records' 会生成一个列表，每个元素是一个代表一行的字典
        # 例如: [{"source": "A", "target": "B", "weight": 0.5}, ...]
        result_df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
        return result_df.to_dict(orient='records')

    except Exception as e:
        # 如果后台任务抛出异常，在这里捕获并返回一个服务器错误
        raise HTTPException(status_code=500, detail=f"执行 GRN 推断时发生内部错误: {e}")

@app.get("/")
async def root():
    return {"message": "欢迎使用 Cefcon GRN 推断 API。请访问 /docs 查看使用文档。"}