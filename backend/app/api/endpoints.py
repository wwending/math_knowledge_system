import shutil
import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.ocr import OCRResponse
from app.services.ocr_engine import ocr_service

router = APIRouter()

# 临时文件夹 (用来暂存上传的图片)
UPLOAD_DIR = "temp_uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/recognize", response_model=OCRResponse)
async def recognize_image(file: UploadFile = File(...)):
    """
    [POST] 上传图片 -> 返回 LaTeX/Markdown
    """
    # 1. 简单的文件校验
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="文件类型错误，请上传图片")

    # 2. 生成唯一文件名 (防止多人上传同名文件冲突)
    file_ext = file.filename.split(".")[-1]
    unique_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        # 3. 保存上传的流到本地文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 4. 调用我们在 service 层写好的 OCR 引擎
        # 注意：这里是同步调用，如果并发高，建议放入 Celery 队列 (Phase 2 优化)
        result = ocr_service.recognize(file_path)

        return OCRResponse(
            success=result["success"],
            content=result["content"],
            cost_seconds=result.get("cost_seconds", 0.0),
            error=result.get("error")
        )

    except Exception as e:
        return OCRResponse(
            success=False, 
            content="", 
            cost_seconds=0.0, 
            error=str(e)
        )
    
    finally:
        # 5. 清理战场：删除临时图片
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass # 删除失败不影响主流程