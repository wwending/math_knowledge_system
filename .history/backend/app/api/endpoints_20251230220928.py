import shutil
import os
import uuid
import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from loguru import logger

from sqlalchemy.orm import Session
from fastapi import Depends
from app.core.database import get_db
from app.models.question import Question # 导入模型

# 引入数据模型
from app.schemas.ocr import OCRResponse
# 引入两大服务引擎
from app.services.ocr_engine import ocr_service
from app.services.nlp_engine import nlp_service

router = APIRouter()

STATIC_DIR = "static/images"
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# 临时图片存储目录
UPLOAD_DIR = "temp_uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/recognize", response_model=OCRResponse)
async def recognize_image(file: UploadFile = File(...)):
    """
    [Core API] 
    1. 接收图片 -> 2. OCR识别文字 -> 3. NLP分类知识点 -> 4. 返回综合结果
    """
    # 1. 校验文件类型
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="文件类型错误，请上传图片")

    # 2. 生成唯一文件名，保存到本地
    file_ext = file.filename.split(".")[-1]
    unique_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        # 保存文件流
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # -------------------------------------------------------
        # STEP 1: OCR 识别 (Pix2Text)
        # -------------------------------------------------------
        # 注意: 这里的 recognize 是同步阻塞的。
        # 在高并发生产环境中，建议放入 Celery 任务队列或使用 run_in_executor
        ocr_result = ocr_service.recognize(file_path)
        
        # 准备默认的返回数据
        final_content = ocr_result.get("content", "")
        knowledge_result = []
        total_cost = ocr_result.get("cost_seconds", 0.0)

        # -------------------------------------------------------
        # STEP 2: NLP 知识点分类 (BERT Zero-Shot)
        # -------------------------------------------------------
        # 只有当 OCR 成功且识别出了文字时，才进行分类
        if ocr_result["success"] and len(final_content.strip()) > 0:
            try:
                # 记录 NLP 开始时间
                nlp_start = time.time()
                
                # 调用 NLP 引擎
                nlp_out = nlp_service.classify(final_content)
                knowledge_result = nlp_out["all_predictions"]
                
                # 累加耗时
                nlp_cost = time.time() - nlp_start
                total_cost += nlp_cost
                
                logger.info(f"NLP 分类完成，耗时: {nlp_cost:.2f}s | Top: {nlp_out['top_label']}")
            
            except Exception as e:
                # 如果 NLP 挂了（比如显存爆了），不要让整个请求失败，只记录错误
                logger.error(f"NLP 分类步骤失败: {e}")
                # 此时 knowledge_result 保持为空即可

        # -------------------------------------------------------
        # STEP 3: 构建响应
        # -------------------------------------------------------
        return OCRResponse(
            success=ocr_result["success"],
            content=final_content,
            knowledge=knowledge_result,  # 返回分类结果
            cost_seconds=round(total_cost, 3), # 返回总耗时
            error=ocr_result.get("error")
        )

    except Exception as e:
        logger.exception("处理图片时发生未捕获异常")
        return OCRResponse(
            success=False, 
            content="", 
            knowledge=[],
            cost_seconds=0.0, 
            error=str(e)
        )
    
    finally:
        # 4. 清理临时文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass