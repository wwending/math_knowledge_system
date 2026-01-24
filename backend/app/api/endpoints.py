import os
import shutil
import time
import uuid
import fitz  # PyMuPDF
from datetime import datetime
from typing import List, Optional, Union, Any

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from loguru import logger

# 数据库与配置
from app.core.database import get_db
from app.core.config import settings

# 服务
from app.services.ocr_engine import ocr_service
from app.services.llm import nlp_service

# 模型
from app.models.question import Question
from app.models.user import User
from app.api.auth import get_current_user


# 初始化路由
router = APIRouter()

# ==========================================
# 1. Pydantic Schema 定义
# ==========================================

# 接收修改内容的模型
class QuestionUpdate(BaseModel):
    content: str

# 知识点标签模型
class KnowledgeTag(BaseModel):
    label: str
    score: float

# OCR 结果响应模型
class OCRResponse(BaseModel):
    success: bool
    content: str
    knowledge: List[KnowledgeTag]
    cost_seconds: float
    image_url: Optional[str] = None
    id: int
    created_at: Optional[datetime] = None

# Question list/detail response models
class QuestionListItem(BaseModel):
    id: int
    content: Optional[str] = None
    knowledge_tags: List[KnowledgeTag] = []
    origin_image: Optional[str] = None
    created_at: Optional[datetime] = None

class QuestionDetail(BaseModel):
    id: int
    content: Optional[str] = None
    knowledge_tags: List[KnowledgeTag] = []
    origin_image: Optional[str] = None
    created_at: Optional[datetime] = None

# ==========================================
# 2. 依赖注入 (Mock User)
# ==========================================

def normalize_tags(raw_tags: Any) -> List[KnowledgeTag]:
    tags: List[KnowledgeTag] = []
    if not raw_tags:
        return tags
    for tag_obj in raw_tags:
        if isinstance(tag_obj, dict):
            tags.append(KnowledgeTag(label=tag_obj.get("label"), score=tag_obj.get("score", 1.0)))
        elif hasattr(tag_obj, "label"):
            tags.append(KnowledgeTag(label=getattr(tag_obj, "label"), score=getattr(tag_obj, "score", 1.0)))
        else:
            tags.append(KnowledgeTag(label=str(tag_obj), score=1.0))
    return tags

# ==========================================
# 3. API 接口实现
# ==========================================

# --- 接口: 获取所有知识点标签 (修复了字段名) ---
@router.get("/tags", response_model=List[str])
def get_all_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 🔥 修正：使用 user_id 而不是 owner_id
    questions = db.query(Question).filter(Question.user_id == current_user.id).all()
    
    unique_tags = set()
    for q in questions:
        if q.knowledge_tags:
            for tag_obj in q.knowledge_tags:
                # 兼容 dict 和 object 两种存储格式
                if isinstance(tag_obj, dict):
                    unique_tags.add(tag_obj.get("label"))
                elif hasattr(tag_obj, 'label'):
                     unique_tags.add(tag_obj.label)
                elif isinstance(tag_obj, str):
                    unique_tags.add(tag_obj)
    
    return sorted(list(unique_tags))

# --- 接口: 修改题目内容 ---
@router.put("/questions/{question_id}")
def update_question(
    question_id: int,
    question_update: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # æ¥æ¾é¢ç®
    q = db.query(Question).filter(
        Question.id == question_id,
        Question.user_id == current_user.id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="é¢ç®ä¸å­å¨")

    # æ´æ°åå®¹
    q.content = question_update.content
    db.commit()
    db.refresh(q)
    return {"success": True, "msg": "æ´æ°æå"}

@router.get("/history", response_model=List[OCRResponse])
def read_history(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 查询数据库，按时间倒序
    questions = (
        db.query(Question)
        .filter(Question.user_id == current_user.id)
        .order_by(Question.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    results = []
    print(f"🔍 正在读取历史记录，共找到 {len(questions)} 条...")

    for q in questions:
        # print(f"   -> [ID:{q.id}] DB存的文件名: '{q.origin_image}'") # 调试用，可注释

        # 转换 Tag 格式
        k_tags = []
        if q.knowledge_tags:
            for t in q.knowledge_tags:
                if isinstance(t, dict):
                    k_tags.append(KnowledgeTag(label=t.get("label"), score=t.get("score", 1.0)))
                else:
                    k_tags.append(KnowledgeTag(label=str(t), score=1.0))
        
        results.append(OCRResponse(
            success=True,
            content=q.content or "",
            knowledge=k_tags,
            cost_seconds=0.0,
            image_url=q.origin_image,
            id=q.id,
            created_at=q.created_at
        ))
        
    return results

# --- 接口: PDF 转图片 ---
@router.post("/upload_pdf")
def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")

    # 确保目录存在 (static 必须已在 main.py 挂载)
    pdf_temp_dir = os.path.join(settings.BASE_DIR, "static", "pdf_temp") 
    # 如果 settings 没有 BASE_DIR，可以用相对路径: os.path.join("static", "pdf_temp")
    if not os.path.exists(pdf_temp_dir):
        os.makedirs(pdf_temp_dir, exist_ok=True)

    file_ext = file.filename.split(".")[-1]
    task_id = str(uuid.uuid4())
    pdf_filename = f"{task_id}.{file_ext}"
    pdf_path = os.path.join(pdf_temp_dir, pdf_filename)
    
    # 保存 PDF
    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_list = []
    try:
        # 打开 PDF
        doc = fitz.open(pdf_path)
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            
            # 设置缩放 (2.0 = 200% 清晰度)
            mat = fitz.Matrix(2.0, 2.0) 
            pix = page.get_pixmap(matrix=mat)
            
            img_name = f"{task_id}_page_{page_index}.jpg"
            img_path = os.path.join(pdf_temp_dir, img_name)
            
            # 保存图片
            pix.save(img_path)
            
            # 返回给前端的 URL 路径 (注意不需要 static/ 前缀，如果前端通过 /static 访问)
            # 或者返回相对路径，由前端拼接
            image_list.append(f"pdf_temp/{img_name}")
            
        doc.close()
        return {"success": True, "total_pages": len(image_list), "images": image_list}
        
    except Exception as e:
        logger.error(f"PDF 处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 解析失败: {str(e)}")

# --- 接口: 图片识别 (核心) ---
@router.post("/recognize", response_model=OCRResponse)
def recognize_image(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_total = time.time()
    
    # 1. 保存文件
    file_ext = os.path.splitext(file.filename)[1].lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    print(f"💾 正在保存文件: {file_path}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. 百度 OCR
    try:
        ocr_result = ocr_service.recognize(file_path)
        raw_content = ocr_result.get("content", "")

        # 👇👇👇 【新增】在这里打印原始数据 👇👇👇
        print("="*30)
        print("🧐 [DEBUG]  OCR 原始输出:")
        print(raw_content)
        print("="*30)
        # 👆👆👆 【新增结束】 👆👆👆
    except Exception as e:
        print(f"❌ OCR Failed: {e}")
        raw_content = ""
        ocr_result = {"success": False}

    # 3. DeepSeek 分析
    final_content = raw_content
    knowledge_tags = []
    
    if ocr_result.get("success") and raw_content.strip():
        print(f"🧠 准备调用 AI分析...")
        nlp_out = nlp_service.analyze(raw_content)
        final_content = nlp_out.get("corrected_text", raw_content)
        
        raw_tags = nlp_out.get("tags", [])
        for tag in raw_tags:
            knowledge_tags.append({"label": tag, "score": 1.0})
    else:
        print("⚠️ 跳过 AI分析 (OCR为空)")

    # 4. 入库
    try:
        new_question = Question(
            origin_image=unique_filename, 
            user_id=current_user.id,  # 🔥 统一使用 user_id
            content=final_content,
            knowledge_tags=knowledge_tags
        )
        db.add(new_question)
        db.commit()
        db.refresh(new_question)
        print(f"✅ 数据库写入成功! ID: {new_question.id}")
        
    except Exception as e:
        print(f"❌ Database Error: {e}")
        db.rollback()
        return OCRResponse(
            success=True, content=final_content, knowledge=knowledge_tags, 
            cost_seconds=round(time.time() - start_total, 2), 
            image_url=unique_filename, id=-1, created_at=None
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

# --- API: question list (current user) ---
@router.get("/questions", response_model=List[QuestionListItem])
def list_questions(
    skip: int = 0,
    limit: int = 50,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Question).filter(Question.user_id == current_user.id)
    if q:
        query = query.filter(Question.content.contains(q))
    questions = query.order_by(Question.created_at.desc(), Question.id.desc()).offset(skip).limit(limit).all()

    return [
        QuestionListItem(
            id=item.id,
            content=item.content,
            knowledge_tags=normalize_tags(item.knowledge_tags),
            origin_image=item.origin_image,
            created_at=item.created_at
        )
        for item in questions
    ]

# --- API: question detail (current user) ---
@router.get("/questions/{question_id}", response_model=QuestionDetail)
def get_question_detail(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.user_id == current_user.id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    return QuestionDetail(
        id=question.id,
        content=question.content,
        knowledge_tags=normalize_tags(question.knowledge_tags),
        origin_image=question.origin_image,
        created_at=question.created_at
    )
