from fastapi import APIRouter, HTTPException, UploadFile, File
import httpx

from ..core.config import CEFCON_BASE_URL

router = APIRouter()


@router.post("/infer-grn/", summary="Proxy CEFCON GRN inference")
async def proxy_cefcon_infer_grn(
    expression_file: UploadFile = File(..., description="基因表达矩阵 CSV 文件 (基因为行, 细胞/样本为列)")
):
    """
    将上传的文件转发到独立的 CEFCON 服务。
    """
    try:
        expr_bytes = await expression_file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取上传文件失败: {e}")
    finally:
        await expression_file.close()

    files = {
        "expression_file": (
            expression_file.filename,
            expr_bytes,
            expression_file.content_type or "text/csv",
        )
    }

    try:
        print(f"正在连接 CEFCON 服务: {CEFCON_BASE_URL}/infer-grn/")
        # 增加超时时间到 50 分钟（3000秒），因为 GRN 推断可能需要较长时间
        timeout = httpx.Timeout(3000.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{CEFCON_BASE_URL}/infer-grn/", files=files)
            print(f"CEFCON 服务响应状态码: {resp.status_code}")
    except httpx.ConnectError as e:
        error_msg = f"无法连接到 CEFCON 服务 ({CEFCON_BASE_URL}): {str(e)}"
        print(f"连接错误: {error_msg}")
        raise HTTPException(status_code=502, detail=error_msg)
    except httpx.TimeoutException as e:
        error_msg = f"连接 CEFCON 服务超时: {str(e)}"
        print(f"超时错误: {error_msg}")
        raise HTTPException(status_code=504, detail=error_msg)
    except httpx.RequestError as e:
        error_msg = f"请求 CEFCON 服务时发生错误: {str(e)}"
        print(f"请求错误: {error_msg}")
        raise HTTPException(status_code=502, detail=error_msg)
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        print(f"未知错误: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    if resp.status_code >= 400:
        error_detail = resp.text if hasattr(resp, 'text') else str(resp.content)
        print(f"CEFCON 服务返回错误 (状态码 {resp.status_code}): {error_detail}")
        raise HTTPException(status_code=resp.status_code, detail=f"CEFCON 服务错误: {error_detail}")

    # CEFCON 返回的格式是 nx.to_pandas_edgelist 的结果
    # 通常是 {source, target, weights_combined} 或其他边属性
    # 需要转换为统一的 {source, target, weight} 格式
    result_data = resp.json()
    if isinstance(result_data, list) and len(result_data) > 0:
        # 检查返回数据的格式并转换
        converted_data = []
        for item in result_data:
            # CEFCON 使用 nx.to_pandas_edgelist，返回 source, target 和边属性
            if 'source' in item and 'target' in item:
                # 优先使用 weights_combined（CEFCON 的标准格式）
                weight = item.get('weights_combined') or item.get('weight') or item.get('importance') or 0.0
                converted_data.append({
                    'source': str(item['source']),
                    'target': str(item['target']),
                    'weight': float(weight) if weight is not None else 0.0
                })
            elif 'from' in item and 'to' in item:
                # 兼容 from/to 格式
                weight = item.get('weights_combined') or item.get('weight') or 0.0
                converted_data.append({
                    'source': str(item['from']),
                    'target': str(item['to']),
                    'weight': float(weight) if weight is not None else 0.0
                })
            elif 'TF' in item and 'target' in item:
                # 兼容其他可能的格式
                weight = item.get('importance') or item.get('weight') or 0.0
                converted_data.append({
                    'source': str(item['TF']),
                    'target': str(item['target']),
                    'weight': float(weight) if weight is not None else 0.0
                })
            else:
                # 如果格式不匹配，尝试直接使用
                converted_data.append(item)
        return converted_data
    
    return result_data

