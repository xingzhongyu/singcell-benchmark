from fastapi import APIRouter, HTTPException, UploadFile, File
import httpx

from ..core.config import SCDGRN_BASE_URL

router = APIRouter()


@router.post("/infer-grn-with-training/", summary="Proxy scDGRN GRN inference with training")
async def proxy_scdgrn_infer_grn(
    expression_zip: UploadFile = File(..., description="A ZIP archive containing 6 chronologically named CSV files of gene expression data."),
):
    """
    将上传的 ZIP 文件转发到独立的 scDGRN 服务进行训练和推断。
    **警告:** 这是一个计算密集型操作，可能需要较长时间。
    """
    if not expression_zip.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP archive.")

    try:
        zip_bytes = await expression_zip.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取上传文件失败: {e}")
    finally:
        await expression_zip.close()

    files = {
        "expression_zip": (
            expression_zip.filename,
            zip_bytes,
            expression_zip.content_type or "application/zip",
        )
    }

    try:
        print(f"正在连接 scDGRN 服务: {SCDGRN_BASE_URL}/infer-grn-with-training/")
        # 增加超时时间到 50 分钟（3000秒），因为 GRN 训练和推断可能需要较长时间
        timeout = httpx.Timeout(3000.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{SCDGRN_BASE_URL}/infer-grn-with-training/", files=files)
            print(f"scDGRN 服务响应状态码: {resp.status_code}")
    except httpx.ConnectError as e:
        error_msg = f"无法连接到 scDGRN 服务 ({SCDGRN_BASE_URL}): {str(e)}"
        print(f"连接错误: {error_msg}")
        raise HTTPException(status_code=502, detail=error_msg)
    except httpx.TimeoutException as e:
        error_msg = f"连接 scDGRN 服务超时: {str(e)}"
        print(f"超时错误: {error_msg}")
        raise HTTPException(status_code=504, detail=error_msg)
    except httpx.RequestError as e:
        error_msg = f"请求 scDGRN 服务时发生错误: {str(e)}"
        print(f"请求错误: {error_msg}")
        raise HTTPException(status_code=502, detail=error_msg)
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        print(f"未知错误: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    if resp.status_code >= 400:
        error_detail = resp.text if hasattr(resp, 'text') else str(resp.content)
        print(f"scDGRN 服务返回错误 (状态码 {resp.status_code}): {error_detail}")
        raise HTTPException(status_code=resp.status_code, detail=f"scDGRN 服务错误: {error_detail}")

    return resp.json()

