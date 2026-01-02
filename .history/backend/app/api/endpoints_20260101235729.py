import os
import shutil
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session
from loguru import logger

from app.schemas.ocr import OCRResponse
from app.services.ocr_engine import ocr_service
from app.services.nlp_engine import nlp_service
from app.core.database import get_db
from app.models.question import Question
from app.models.user import User
from app.api.auth import get_current_user
from sqlalchemy import or_

from pydantic import BaseModel

# 定义一个简单的接收数据的模型
class QuestionUpdate(BaseModel):
    content: str

# 定义 API 路由对象
router = APIRouter()

# --- 新增：获取所有知识点标签的接口 (用于前端左侧菜单) ---
@router.get("/tags", response_model=List[str])
def get_all_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 查询当前用户所有题目的标签
    questions = db.query(Question).filter(Question.owner_id == current_user.id).all()
    
    unique_tags = set()
    for q in questions:
        if q.knowledge_tags:
            for tag_obj in q.knowledge_tags:
                if isinstance(tag_obj, dict):
                    unique_tags.add(tag_obj.get("label"))
                elif hasattr(tag_obj, 'label'):
                     unique_tags.add(tag_obj.label)
    
    return sorted(list(unique_tags))

@router.put("/questions/{question_id}")
def update_question(
    question_id: int,
    question_update: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 查找题目
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    
    # 权限检查 (只能改自己的，或者是管理员)
    if q.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改")
    
    # 更新内容
    q.content = question_update.content
    db.commit()
    db.refresh(q)
    return {"success": True, "msg": "更新成功"}

# --- 修改：get_history 支持筛选 ---
# 记得引入 from app.schemas.question import QuestionOut (如果你把 schema 分离了的话)
# 假设这里直接用 models 转 dict 或者你有对应的 response_model
@router.get("/history") # 这里简化了 response_model，你可以根据实际情况加
def get_history(
    skip: int = 0, 
    limit: int = 100, 
    keyword: str = None, 
    tag: str = None,     
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Question)
    
    if current_user.role != "admin":
        query = query.filter(Question.owner_id == current_user.id)
    
    if keyword:
        query = query.filter(Question.content.like(f"%{keyword}%"))
    
    if tag:
        # 简单匹配 JSON 字符串
        query = query.filter(Question.knowledge_tags.like(f'%{tag}%'))
    
    questions = query.order_by(Question.created_at.desc()).offset(skip).limit(limit).all()
    return questions

# --- 新增: PDF 转高清图 API ---
import fitz # PyMuPDF

@router.post("/upload_pdf")
def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")

    pdf_temp_dir = os.path.join("static", "pdf_temp")
    if not os.path.exists(pdf_temp_dir):
        os.makedirs(pdf_temp_dir)

    file_ext = file.filename.split(".")[-1]
    task_id = str(uuid.uuid4())
    pdf_filename = f"{task_id}.{file_ext}"
    pdf_path = os.path.join(pdf_temp_dir, pdf_filename)
    
    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_list = []
    try:
        doc = fitz.open(pdf_path)
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            mat = fitz.Matrix(2.0, 2.0) 
            pix = page.get_pixmap(matrix=mat)
            img_name = f"{task_id}_page_{page_index}.jpg"
            img_path = os.path.join(pdf_temp_dir, img_name)
            pix.save(img_path)
            image_list.append(f"pdf_temp/{img_name}")
        doc.close()
        return {"success": True, "total_pages": len(image_list), "images": image_list}
    except Exception as e:
        logger.error(f"PDF 处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 解析失败: {str(e)}")


# --- 核心：图片识别 API ---
@router.post("/recognize", response_model=OCRResponse)
def recognize_image(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    [Core API] 上传 -> OCR -> NLP(清洗+分类) -> 入库 -> 返回
    """
    # 1. 校验文件类型
    allowed_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    is_image_type = file.content_type.startswith("image/")
    
    if not (is_image_type or file_ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="不支持的文件类型，请上传图片")

    # 2. 生成路径
    unique_name = f"{uuid.uuid4()}{file_ext if file_ext else '.jpg'}"
    relative_path = f"images/{unique_name}"
    full_file_path = os.path.join("static", relative_path)
    os.makedirs(os.path.dirname(full_file_path), exist_ok=True)

    try:
        # 3. 保存文件
        with open(full_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # -------------------------------------------------------
        # STEP 1: OCR 识别
        # -------------------------------------------------------
        ocr_start = time.time()
        ocr_result = ocr_service.recognize(full_file_path)
        ocr_cost = time.time() - ocr_start
        
        raw_content = ocr_result.get("content", "")
        
        # 默认值
        final_content = raw_content 
        knowledge_tags = []
        nlp_cost = 0.0

        # -------------------------------------------------------
        # STEP 2: NLP 处理 (核心修改处)
        # -------------------------------------------------------
        if ocr_result["success"] and raw_content.strip():
            try:
                nlp_start = time.time()
                
                # 🔥🔥 重点：调用 analyze 而不是 classify 🔥🔥
                nlp_out = nlp_service.analyze(raw_content)
                
                # 获取清洗后的文本
                final_content = nlp_out.get("corrected_text", raw_content)
                # 获取标签
                knowledge_tags = nlp_out.get("tags", [])
                
                nlp_cost = time.time() - nlp_start
            except Exception as e:
                logger.error(f"NLP 处理失败: {e}")

        total_cost = ocr_cost + nlp_cost

        # -------------------------------------------------------
        # STEP 3: 数据库入库
        # -------------------------------------------------------
        if ocr_result["success"]:
            try:
                new_question = Question(
                    image_url=relative_path,
                    content=final_content,       # 存清洗后的文本
                    knowledge_tags=knowledge_tags,
                    owner_id=current_user.id,
                    status="pending"
                )
                db.add(new_question)
                db.commit()
                db.refresh(new_question)
                logger.success(f"✅ 题目入库成功 ID: {new_question.id}")
            except Exception as db_e:
                logger.error(f"❌ 数据库保存失败: {db_e}")
        
        return OCRResponse(
            success=ocr_result["success"],
            content=final_content,
            knowledge=knowledge_tags,
            cost_seconds=round(total_cost, 3),
            error=ocr_result.get("error")
        )

    except Exception as e:
        logger.exception("API 处理过程中发生严重错误")
        if os.path.exists(full_file_path):
            try:
                os.remove(full_file_path)
            except:
                pass
        
        return OCRResponse(
            success=False, content="", knowledge=[], cost_seconds=0.0, error=str(e)
        )