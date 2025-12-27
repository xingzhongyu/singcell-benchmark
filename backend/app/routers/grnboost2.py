from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Path
import httpx

from ..core.config import GRNBOOST2_BASE_URL

router = APIRouter()


@router.post("/infer-grn/{algorithm_name}", summary="Proxy GRNBoost2/Genie3 GRN inference")
async def proxy_grnboost2_infer_grn(
    algorithm_name: str = Path(..., description="要使用的算法: 'genie3' 或 'grnboost2'", enum=['genie3', 'grnboost2']),
    expression_file: UploadFile = File(..., description="基因表达矩阵 CSV 文件 (基因为行, 样本/细胞为列)"),
    tf_file: UploadFile = File(..., description="转录因子列表 CSV 文件 (单列，无表头)")
):
    """
    将上传的文件转发到独立的 GRNBoost2 服务。
    """
    try:
        expr_bytes = await expression_file.read()
        tf_bytes = await tf_file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取上传文件失败: {e}")
    finally:
        await expression_file.close()
        await tf_file.close()

    files = {
        "expression_file": (
            expression_file.filename,
            expr_bytes,
            expression_file.content_type or "text/csv",
        ),
        "tf_file": (
            tf_file.filename,
            tf_bytes,
            tf_file.content_type or "text/csv",
        )
    }

    try:
        print(f"正在连接 GRNBoost2 服务: {GRNBOOST2_BASE_URL}/infer-grn/{algorithm_name}")
        # 增加超时时间到 50 分钟（3000秒），因为 GRN 推断可能需要较长时间
        timeout = httpx.Timeout(3000.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{GRNBOOST2_BASE_URL}/infer-grn/{algorithm_name}", files=files)
            print(f"GRNBoost2 服务响应状态码: {resp.status_code}")
    except httpx.ConnectError as e:
        error_msg = f"无法连接到 GRNBoost2 服务 ({GRNBOOST2_BASE_URL}): {str(e)}"
        print(f"连接错误: {error_msg}")
        raise HTTPException(status_code=502, detail=error_msg)
    except httpx.TimeoutException as e:
        error_msg = f"连接 GRNBoost2 服务超时: {str(e)}"
        print(f"超时错误: {error_msg}")
        raise HTTPException(status_code=504, detail=error_msg)
    except httpx.RequestError as e:
        error_msg = f"请求 GRNBoost2 服务时发生错误: {str(e)}"
        print(f"请求错误: {error_msg}")
        raise HTTPException(status_code=502, detail=error_msg)
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        print(f"未知错误: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    if resp.status_code >= 400:
        error_detail = resp.text if hasattr(resp, 'text') else str(resp.content)
        print(f"GRNBoost2 服务返回错误 (状态码 {resp.status_code}): {error_detail}")
        raise HTTPException(status_code=resp.status_code, detail=f"GRNBoost2 服务错误: {error_detail}")

    return resp.json()

