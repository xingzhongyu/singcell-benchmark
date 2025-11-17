#!/usr/bin/env python3
"""
空间转录组数据预处理工具 - FastAPI 版本
提供数据预处理、空间聚类和 SpatialDE 分析功能
"""

import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import tempfile
import uuid
from typing import Dict, List, Optional, Any, Literal
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# 尝试导入生物信息学相关包
try:
    import anndata as ad
    import scanpy as sc
    import pandas as pd
    import numpy as np
    from scipy import sparse
    BIO_AVAILABLE = True
except ImportError as e:
    logging.warning(f"生物信息学包导入失败: {e}")
    BIO_AVAILABLE = False

# 配置日志
def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    default_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.getenv("LOG_DIR", default_dir)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "log")
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(level)
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)
    fh.setLevel(level)
    root.addHandler(sh)
    root.addHandler(fh)

_setup_logging()
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="空间转录组数据预处理服务",
    description="提供空间转录组数据的预处理、空间聚类和 SpatialDE 分析功能",
    version="1.0.0"
)

# 输出目录配置
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
try:
    import time
    from starlette.middleware.base import BaseHTTPMiddleware
    class RequestLogMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            start = time.time()
            response = None
            try:
                response = await call_next(request)
                return response
            finally:
                duration = (time.time() - start) * 1000.0
                status = getattr(response, "status_code", -1)
                logger.info("request %s %s -> %s (%.1f ms)",
                            request.method, request.url.path, status, duration)
    app.add_middleware(RequestLogMiddleware)
except Exception as _e:
    logger.debug("中间件初始化失败: %s", _e)

# 文件类型映射（用于下载接口）
FILE_TYPE_MAP = {
    "preprocessed": "preprocessed_{file_id}.h5ad",
    "spatial": "spatial_{file_id}.h5ad",
    "spatialde": "spatialde_{file_id}.h5ad"
}


def handle_error(step: str, error: Exception, include_traceback: bool = True) -> Dict[str, Any]:
    """统一错误处理函数"""
    error_info = {
        "error": True,
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error)
    }
    
    if include_traceback:
        error_info["traceback"] = traceback.format_exc()
    
    logger.error(f"步骤 {step} 执行失败: {error}")
    if include_traceback:
        logger.error(traceback.format_exc())
    
    return error_info


def _read_adata(
    file_path: str,
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = "auto",
) -> "ad.AnnData":
    """Centralized AnnData reader.
    Supports a few common spatial/single-cell formats and keeps logic in one place.
    """
    if file_type == "auto":
        if file_path.endswith(".h5ad"):
            return ad.read_h5ad(file_path)
        if file_path.endswith(".h5"):
            return sc.read_10x_h5(file_path)
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path, index_col=0)
            return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
        if file_path.endswith(".tsv"):
            df = pd.read_csv(file_path, sep="\t", index_col=0)
            return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
        # Fallback to scanpy's autodetect
        return sc.read(file_path)

    if file_type == "h5ad":
        return ad.read_h5ad(file_path)
    if file_type == "10x_h5":
        return sc.read_10x_h5(file_path)
    if file_type == "csv":
        df = pd.read_csv(file_path, index_col=0)
        return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
    if file_type == "tsv":
        df = pd.read_csv(file_path, sep="\t", index_col=0)
        return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))

    # If we get here the file_type is not supported
    raise ValueError(f"Unsupported file_type: {file_type}")


def perform_quality_control(
    adata: ad.AnnData,
    min_genes: int = 200,
    min_cells: int = 3,
    max_mito_percent: float = 5.0,
    mito_prefix: str = "MT-"
) -> Dict[str, Any]:
    """执行质量控制的内部函数"""
    initial_cells = adata.n_obs
    initial_genes = adata.n_vars
    
    # 计算质量控制指标
    logger.info("计算质量控制指标")
    # mark mitochondrial genes by prefix then compute QC metrics
    mt_key = "mt"
    adata.var[mt_key] = adata.var_names.str.startswith(mito_prefix)
    sc.pp.calculate_qc_metrics(adata, qc_vars=[mt_key], percent_top=None, log1p=False, inplace=True)
    
    # 过滤低质量细胞和基因
    logger.info(f"过滤细胞 (min_genes={min_genes})")
    sc.pp.filter_cells(adata, min_genes=min_genes)
    
    logger.info(f"过滤基因 (min_cells={min_cells})")
    sc.pp.filter_genes(adata, min_cells=min_cells)
    
    # 线粒体基因过滤
    pct_col = "pct_counts_mt"
    if max_mito_percent > 0 and pct_col in adata.obs.columns:
        logger.info(f"过滤线粒体基因 (max_mito_percent={max_mito_percent})")
        before_mito = int(adata.n_obs)
        adata = adata[adata.obs[pct_col] < max_mito_percent, :].copy()
        mito_removed = before_mito - int(adata.n_obs)
        logger.info(f"基于线粒体基因过滤移除 {mito_removed} 个细胞")
    else:
        mito_removed = 0
        logger.info("跳过线粒体基因过滤")
    
    return {
        "adata": adata,
        "initial_cells": initial_cells,
        "final_cells": adata.n_obs,
        "cells_removed": initial_cells - adata.n_obs,
        "initial_genes": initial_genes,
        "final_genes": adata.n_vars,
        "genes_removed": initial_genes - adata.n_vars,
        "mito_cells_removed": mito_removed
    }


def perform_normalization(
    adata: ad.AnnData,
    method: Literal["log1p", "sqrt", "none"] = "log1p",
    target_sum: float = 1e4,
    highly_variable_genes: bool = True,
    n_top_genes: int = 2000,
) -> Dict[str, Any]:
    """执行数据标准化的内部函数"""
    # 标准化
    logger.info(f"标准化数据 (target_sum={target_sum})")
    sc.pp.normalize_total(adata, target_sum=target_sum)
    
    logger.info(f"应用转换方法: {method}")
    if method == "log1p":
        sc.pp.log1p(adata)
    elif method == "sqrt":
        # handle sparse matrices
        if sparse.issparse(adata.X):
            adata.X = np.sqrt(adata.X.A)
        else:
            adata.X = np.sqrt(adata.X)
    elif method == "none":
        logger.info("跳过数据转换")
    
    # 高变基因选择
    n_hvg = 0
    if highly_variable_genes:
        logger.info(f"选择高变基因 (n_top_genes={n_top_genes})")
        try:
            sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes)
            n_hvg = adata.var.highly_variable.sum()
            adata = adata[:, adata.var.highly_variable]
            logger.info(f"选择了 {n_hvg} 个高变基因")
        except Exception as e:
            logger.warning(f"高变基因选择失败: {e}")
            n_hvg = 0
    
    return {
        "adata": adata,
        "method": method,
        "target_sum": target_sum,
        "n_hvg": n_hvg,
        "final_shape": list(adata.shape)
    }


@app.post("/api/preprocess")
async def integrated_preprocessing(
    file: UploadFile = File(..., description="空间转录组数据文件"),
    # 文件类型
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form("auto", description="文件类型"),
    # 质量控制参数
    min_genes: int = Form(200, description="每个细胞最少表达的基因数"),
    min_cells: int = Form(3, description="每个基因最少在多少个细胞中表达"),
    max_mito_percent: float = Form(5.0, description="线粒体基因最大百分比"),
    mito_prefix: str = Form("MT-", description="线粒体基因前缀"),
    # 标准化参数
    normalization_method: Literal["log1p", "sqrt", "none"] = Form("log1p", description="标准化方法"),
    target_sum: float = Form(1e4, description="标准化目标总和"),
    highly_variable_genes: bool = Form(True, description="是否选择高变基因"),
    n_top_genes: int = Form(2000, description="高变基因数量"),
):
    """
    整合的数据预处理流程：加载 → 质控 → 归一化
    
    接收上传的文件，执行质量控制和数据标准化，返回文件ID用于下载。
    
    **参数说明**:
    - `file`: 上传的空间转录组数据文件（支持 h5ad, 10x_h5, csv, tsv 格式）
    - `file_type`: 文件类型，可选: auto, h5ad, 10x_h5, csv, tsv（默认: "auto"）
    - `min_genes`: 每个细胞最少表达的基因数（默认: 200）
    - `min_cells`: 每个基因最少在多少个细胞中表达（默认: 3）
    - `max_mito_percent`: 线粒体基因最大百分比（默认: 5.0）
    - `mito_prefix`: 线粒体基因前缀（默认: "MT-"）
    - `normalization_method`: 标准化方法，可选: log1p, sqrt, none（默认: "log1p"）
    - `target_sum`: 标准化目标总和（默认: 1e4）
    - `highly_variable_genes`: 是否选择高变基因（默认: True）
    - `n_top_genes`: 高变基因数量（默认: 2000）
    
    **返回** (JSON格式):
    - `data`: 包含文件ID和统计信息的字典
        - `preprocessed_data.h5ad`: 文件ID（用于下载接口）
        - `处理统计信息`: 文本格式的统计信息
    """
    if not BIO_AVAILABLE:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "生物信息学包未安装",
                "error": "请安装 anndata, scanpy, pandas, numpy, scipy"
            }
        )
    
    temp_input_path = None
    
    try:
        # 生成唯一的文件ID
        file_id = str(uuid.uuid4())
        
        # 保存上传的文件到临时目录
        temp_input_path = os.path.join(tempfile.gettempdir(), f"input_{file_id}_{file.filename}")
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"文件已保存: {temp_input_path}, 大小: {len(content)} bytes")
        
        # 步骤1: 加载数据
        logger.info("步骤1: 加载数据")
        adata = _read_adata(temp_input_path, file_type)
        initial_shape = adata.shape
        
        # 步骤2: 质量控制
        logger.info("步骤2: 质量控制")
        qc_result = perform_quality_control(
            adata, min_genes, min_cells, max_mito_percent, mito_prefix
        )
        adata = qc_result["adata"]
        
        # 步骤3: 数据标准化
        logger.info("步骤3: 数据标准化")
        norm_result = perform_normalization(
            adata, normalization_method, target_sum, 
            highly_variable_genes, n_top_genes
        )
        adata = norm_result["adata"]
        
        # 保存处理后的数据到输出目录
        output_filename = f"preprocessed_{file_id}.h5ad"
        output_file_path = os.path.join(OUTPUT_DIR, output_filename)
        adata.write_h5ad(output_file_path)
        logger.info(f"预处理后的数据已保存: {output_file_path}")
        
        # 格式化处理统计信息为文本
        stats_text_parts = []
        stats_text_parts.append("数据预处理统计：")
        stats_text_parts.append(f"\n初始数据维度：")
        stats_text_parts.append(f"  细胞数: {initial_shape[0]}")
        stats_text_parts.append(f"  基因数: {initial_shape[1]}")
        
        stats_text_parts.append(f"\n质量控制统计：")
        stats_text_parts.append(f"  初始细胞数: {qc_result['initial_cells']}")
        stats_text_parts.append(f"  最终细胞数: {qc_result['final_cells']}")
        stats_text_parts.append(f"  移除细胞数: {qc_result['cells_removed']}")
        stats_text_parts.append(f"  初始基因数: {qc_result['initial_genes']}")
        stats_text_parts.append(f"  最终基因数: {qc_result['final_genes']}")
        stats_text_parts.append(f"  移除基因数: {qc_result['genes_removed']}")
        stats_text_parts.append(f"  线粒体过滤移除细胞数: {qc_result['mito_cells_removed']}")
        
        stats_text_parts.append(f"\n数据标准化统计：")
        stats_text_parts.append(f"  标准化方法: {norm_result['method']}")
        stats_text_parts.append(f"  目标总和: {norm_result['target_sum']}")
        stats_text_parts.append(f"  高变基因数量: {norm_result['n_hvg']}")
        stats_text_parts.append(f"  最终数据维度: {norm_result['final_shape']}")
        
        stats_text = "\n".join(stats_text_parts)
        
        # 返回 JSON 响应，数据放在 data 下
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "数据预处理完成",
                "data": {
                    "preprocessed_data.h5ad": file_id,
                    "处理统计信息": stats_text
                }
            }
        )
    
    except Exception as e:
        logger.error(f"数据预处理失败: {str(e)}", exc_info=True)
        error_info = handle_error("integrated_preprocessing", e)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "数据预处理失败",
                "error": error_info
            }
        )
    
    finally:
        # 清理临时输入文件
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")


@app.get("/api/download/{file_id}")
async def download_file(file_id: str, file_type: Optional[str] = None):
    """
    根据文件ID下载处理后的文件
    
    **参数说明**:
    - `file_id`: 文件ID（由预处理/分析接口返回）
    - `file_type`: 文件类型（可选），可选值: h5ad, csv。如果不指定，将尝试所有可能的文件类型
    
    **返回**:
    - 文件内容（二进制流）
    - 如果文件不存在，返回 404 错误
    
    **支持的文件类型**:
    - `preprocessed_{file_id}.h5ad`: 预处理后的数据
    - `spatial_{file_id}.h5ad`: 空间分析后的数据
    - `spatialde_{file_id}.h5ad`: SpatialDE 分析后的数据
    - `spatialde_{file_id}.csv`: SpatialDE CSV 结果
    """
    # 根据 file_type 确定要查找的文件
    if file_type == "h5ad":
        possible_files = [
            f"preprocessed_{file_id}.h5ad",
            f"spatial_{file_id}.h5ad",
            f"spatialde_{file_id}.h5ad"
        ]
    elif file_type == "csv":
        possible_files = [
            f"spatialde_{file_id}.csv"
        ]
    else:
        # 尝试所有可能的文件类型
        possible_files = [
            f"preprocessed_{file_id}.h5ad",
            f"spatial_{file_id}.h5ad",
            f"spatialde_{file_id}.h5ad",
            f"spatialde_{file_id}.csv"
        ]
    
    file_path = None
    for filename in possible_files:
        candidate_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(candidate_path):
            file_path = candidate_path
            break
    
    # 检查文件是否存在
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"文件不存在: file_id={file_id}, file_type={file_type}")
        raise HTTPException(
            status_code=404,
            detail=f"文件不存在或已过期: file_id={file_id}, file_type={file_type}"
        )
    
    # 确定媒体类型
    if file_path.endswith(".csv"):
        media_type = "text/csv"
    else:
        media_type = "application/octet-stream"
    
    # 返回文件
    filename = os.path.basename(file_path)
    logger.info(f"下载文件: {file_path}, file_id: {file_id}")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "bio_available": BIO_AVAILABLE,
        "output_dir": OUTPUT_DIR,
        "services": [
            "preprocess",
            "spatial-analysis",
            "spatialde"
        ]
    }


if __name__ == "__main__":
    import uvicorn, os as _os
    _port = int(_os.getenv("PORT", 8086))
    uvicorn.run(app, host="0.0.0.0", port=_port)
