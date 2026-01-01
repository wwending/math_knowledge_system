import shutil
import os
import uuid
import time
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from loguru import logger
from sqlalchemy.orm import Session

# 引入数据模型
from app.schemas.ocr import OCRResponse
# 引入数据库依赖
from app.core.database import get_db
from app.models.question import Question
# 引入服务引擎
from app.services.ocr_engine import ocr_service
from app.services.nlp_engine import nlp_service

from typing import List # 记得加这个
from app.schemas.question import QuestionOut # <--- 新增引入

from app.api.auth import get_current_user # <--- 引入鉴权依赖
from app.models.user import User

router = APIRouter()

# --- 修改 1: 定义静态资源目录 (永久存储) ---
# 以前是 temp_uploads，现在改为 static/images
STATIC_DIR = "static/images"
# 确保目录存在，如果不存在会自动创建
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

@router.post("/recognize", response_model=OCRResponse)
def recognize_image(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # <--- 必须登录才能访问
):
    """
    [Core API] 上传 -> OCR -> NLP -> 入库 -> 返回
    """
    # 1. 校验
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="文件类型错误，请上传图片")

    # 2. 生成路径
    file_ext = file.filename.split(".")[-1]
    unique_name = f"{uuid.uuid4()}.{file_ext}"
    
    # relative_path: 存入数据库的路径 (例如: images/abc.jpg)
    # 前端访问时会拼接 /static/ 前缀
    relative_path = f"images/{unique_name}"
    
    # full_file_path: 后端保存文件的物理绝对/相对路径 (例如: static/images/abc.jpg)
    full_file_path = os.path.join("static", relative_path)

    try:
        # 3. 保存文件 (持久化存储)
        with open(full_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # -------------------------------------------------------
        # STEP 1: OCR 识别
        # -------------------------------------------------------
        ocr_result = ocr_service.recognize(full_file_path)
        
        final_content = ocr_result.get("content", "")
        knowledge_result = []
        total_cost = ocr_result.get("cost_seconds", 0.0)

        # -------------------------------------------------------
        # STEP 2: NLP 知识点分类
        # -------------------------------------------------------
        if ocr_result["success"] and len(final_content.strip()) > 0:
            try:
                nlp_start = time.time()
                nlp_out = nlp_service.classify(final_content)
                knowledge_result = nlp_out["all_predictions"]
                total_cost += (time.time() - nlp_start)
            except Exception as e:
                logger.error(f"NLP Error: {e}")

        # -------------------------------------------------------
        # STEP 3: 数据库入库 (Database Insert)
        # -------------------------------------------------------
        if ocr_result["success"]:
            try:
                new_question = Question(
                    image_url=relative_path,      # 存相对路径
                    content=final_content,        # 存识别出的文本
                    knowledge_tags=knowledge_result, # 存知识点 JSON
                    owner_id=current_user.id,  # <--- 记录上传者 ID
                    status="pending"           # <--- 默认待审核

                )
                db.add(new_question)
                db.commit()
                db.refresh(new_question)
                logger.success(f"✅ 题目已归档入库 ID: {new_question.id}")
            except Exception as db_e:
                logger.error(f"❌ 数据库保存失败: {db_e}")
                # 数据库保存失败不影响返回给前端结果，但要记录日志

        return OCRResponse(
            success=ocr_result["success"],
            content=final_content,
            knowledge=knowledge_result,
            cost_seconds=round(total_cost, 3),
            error=ocr_result.get("error")
        )

    except Exception as e:
        logger.exception("处理过程中发生严重错误")
        
        # --- 修改 2: 只有在严重错误时才考虑删除文件 ---
        # 如果处理彻底失败（比如连 OCR 都没跑通），为了不浪费硬盘空间，可以删掉
        if os.path.exists(full_file_path):
            try:
                os.remove(full_file_path)
            except:
                pass
                
        return OCRResponse(
            success=False, content="", knowledge=[], cost_seconds=0.0, error=str(e)
        )
    
    # --- 修改 3: 彻底移除了 finally 块 ---
    # 以前这里有 finally: os.remove(...)
    # 现在删掉了，因为如果成功了，我们要保留 static/images 下的文件

@router.get("/history", response_model=List[QuestionOut])
def get_history(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # <--- 必须登录
):
    """
    查询历史上传的题目 (按时间倒序)
    """
    query = db.query(Question)
    # 权限控制逻辑
    if current_user.role != "admin":
        # 普通用户只能看自己的
        query = query.filter(Question.owner_id == current_user.id)
    
    # 如果是 admin，默认看到所有 (query 不变)
    
    questions = query.order_by(Question.created_at.desc()).offset(skip).limit(limit).all()
    return questions