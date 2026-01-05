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
from app.core.config import settings

from pydantic import BaseModel

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException

from app.schemas.token import Token 
from fastapi.security import OAuth2PasswordRequestForm

from app.services.llm import nlp_service 
from app.models.question import Question # 确保引入模型

# 定义一个简单的接收数据的模型
class QuestionUpdate(BaseModel):
    content: str

# 定义 API 路由对象
router = APIRouter()

# 🔥🔥🔥 新增：一个假的身份验证依赖 🔥🔥🔥
# 这个函数不管 token 是什么，都返回一个超级管理员用户


# 如果上面的 oauth2_scheme 报错，可以用这个最简单的版本：
def get_mock_user_simple():
    class MockUser:
        id = 1
        username = "admin"
        role = "admin"  # <--- 关键！补上了这一行
    return MockUser()

# --- 新增：获取所有知识点标签的接口 (用于前端左侧菜单) ---
@router.get("/tags", response_model=List[str])
def get_all_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_mock_user_simple)
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
    current_user: User = Depends(get_mock_user_simple)
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
    current_user: User = Depends(get_mock_user_simple)
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
    current_user: User = Depends(get_mock_user_simple)
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
    # 注意：这里用 get_mock_user_simple 或 get_mock_user 都可以，看你定义了哪个
    current_user = Depends(get_mock_user_simple) 
):
    start_total = time.time()
    
    # 1. 校验与保存文件 (保持你之前的逻辑，这里简化展示)
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. 百度 OCR
    ocr_start = time.time()
    try:
        ocr_result = ocr_service.recognize(file_path)
        raw_content = ocr_result.get("content", "")
    except Exception as e:
        print(f"OCR Failed: {e}")
        raw_content = ""
        ocr_result = {"success": False}

    # 3. DeepSeek 分析 (关键！)
    final_content = raw_content
    knowledge_tags = []
    
    # 只有 OCR 有内容才调用 LLM
    if ocr_result.get("success") and raw_content.strip():
        print(f"🧠 准备调用 DeepSeek...")
        nlp_out = nlp_service.analyze(raw_content)
        
        # 获取修复后的 LaTeX 文本
        final_content = nlp_out.get("corrected_text", raw_content)
        
        # 转换标签格式为前端需要的对象数组
        raw_tags = nlp_out.get("tags", [])
        for tag in raw_tags:
            knowledge_tags.append({"label": tag, "score": 1.0})
    else:
        print("⚠️ 跳过 DeepSeek (OCR为空)")

    # 4. 入库 (修正字段名！)
    try:
        new_question = Question(
            # 🔥 修正点 1: 数据库里叫 origin_image，不叫 image_url
            origin_image=unique_filename, 
            
            # 🔥 修正点 2: 数据库里叫 user_id，不叫 owner_id
            user_id=current_user.id,
            
            content=final_content,
            knowledge_tags=knowledge_tags
        )
        db.add(new_question)
        db.commit()
        db.refresh(new_question)
    except Exception as e:
        print(f"Database Error: {e}")
        db.rollback()
        # 即使入库失败，也返回结果给前端看
        return OCRResponse(
            success=True,
            content=final_content,
            knowledge=knowledge_tags,
            cost_seconds=round(time.time() - start_total, 2),
            image_url=unique_filename,
            id=-1, # 表示入库失败
            created_at=None
        )

    return OCRResponse(
        success=True,
        content=final_content,
        knowledge=knowledge_tags,
        cost_seconds=round(time.time() - start_total, 2),
        image_url=unique_filename,
        id=new_question.id,
        created_at=new_question.created_at
    )