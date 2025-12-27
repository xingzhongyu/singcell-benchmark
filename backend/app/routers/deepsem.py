from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import httpx

from ..core.config import DEEPSEM_BASE_URL

router = APIRouter()


@router.post("/infer-grn/", summary="Proxy DeepSEM GRN inference")
async def proxy_deepsem_infer_grn(
    expression_file: UploadFile = File(..., description="输入的scRNA-seq基因表达矩阵 (CSV)"),
    network_file: Optional[UploadFile] = File(None, description="GRN真实网络结构 (CSV), 可选"),
    task: str = Form("celltype_GRN", description="任务类型: celltype_GRN / non_celltype_GRN / simulation / embedding"),
    setting: str = Form("default", description="超参配置: default 或 test"),
    n_epochs: int = Form(120, description="训练的 Epoch 数"),
    batch_size: int = Form(64, description="批次大小"),
    alpha: float = Form(100.0, description="W 的 L1 范数损失系数"),
    beta: float = Form(1.0, description="KL 项损失系数"),
    lr: float = Form(1e-4, description="学习率"),
    n_hidden: int = Form(128, description="隐藏层神经元数"),
    K: int = Form(1, description="GMM 高斯核数量"),
    K1: int = Form(1, description="优化 MLP 的 Epoch 数"),
    K2: int = Form(2, description="优化 W 的 Epoch 数"),
    gamma: float = Form(0.95, description="学习率衰减因子"),
    lr_step_size: float = Form(0.99, description="学习率衰减步长"),
):
    """
    将上传的文件和表单参数转发到独立的 DeepSEM 服务。
    """
    try:
        expr_bytes = await expression_file.read()
        net_bytes = await network_file.read() if network_file else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取上传文件失败: {e}")
    finally:
        await expression_file.close()
        if network_file:
            await network_file.close()

    data = {
        "task": task,
        "setting": setting,
        "n_epochs": str(n_epochs),
        "batch_size": str(batch_size),
        "alpha": str(alpha),
        "beta": str(beta),
        "lr": str(lr),
        "n_hidden": str(n_hidden),
        "K": str(K),
        "K1": str(K1),
        "K2": str(K2),
        "gamma": str(gamma),
        "lr_step_size": str(lr_step_size),
    }

    files = {
        "expression_file": (
            expression_file.filename,
            expr_bytes,
            expression_file.content_type or "text/csv",
        )
    }
    if net_bytes is not None:
        files["network_file"] = (
            network_file.filename,
            net_bytes,
            network_file.content_type or "text/csv",
        )

    try:
        print(f"正在连接 DeepSEM 服务: {DEEPSEM_BASE_URL}/infer-grn/")
        # 增加超时时间到 50 分钟（3000秒），因为 GRN 推断可能需要较长时间
        timeout = httpx.Timeout(3000.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{DEEPSEM_BASE_URL}/infer-grn/", data=data, files=files)
            print(f"DeepSEM 服务响应状态码: {resp.status_code}")
    except httpx.ConnectError as e:
        error_msg = f"无法连接到 DeepSEM 服务 ({DEEPSEM_BASE_URL}): {str(e)}"
        print(f"连接错误: {error_msg}")
        raise HTTPException(status_code=502, detail=error_msg)
    except httpx.TimeoutException as e:
        error_msg = f"连接 DeepSEM 服务超时: {str(e)}"
        print(f"超时错误: {error_msg}")
        raise HTTPException(status_code=504, detail=error_msg)
    except httpx.RequestError as e:
        error_msg = f"请求 DeepSEM 服务时发生错误: {str(e)}"
        print(f"请求错误: {error_msg}")
        raise HTTPException(status_code=502, detail=error_msg)
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        print(f"未知错误: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    if resp.status_code >= 400:
        error_detail = resp.text if hasattr(resp, 'text') else str(resp.content)
        print(f"DeepSEM 服务返回错误 (状态码 {resp.status_code}): {error_detail}")
        raise HTTPException(status_code=resp.status_code, detail=f"DeepSEM 服务错误: {error_detail}")

    return resp.json()

