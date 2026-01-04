import shutil
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.orm import Session

# --- 内部模块引入 ---
from app.core.database import get_db
from app.api.dependencies import get_current_user  # 确保你有这个依赖文件
from app.services.ocr_engine import ocr_engine
from app.services.nlp_engine import nlp_engine   # 引入刚才更新的异步引擎

# --- 模型与Schema引入 ---
from app.models.user import User
from app.models.question import Question, QuestionStatus # 引入枚举(如果有)或直接用字符串
from app.schemas.question import QuestionCreate, QuestionResponse, QuestionOut

router = APIRouter()

# 图片保存路径
UPLOAD_DIR = "app/static/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==========================================
# 1. OCR 与 AI 分析接口
# ==========================================

@router.post("/ocr/analyze", summary="上传图片并进行OCR+AI修正")
async def analyze_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user) # 只有登录用户才能上传
):
    """
    1. 保存上传的图片
    2. 调用百度 OCR 识别原始文本
    3. 调用 DeepSeek (NLP) 进行数学公式修正和标签提取
    """
    # 1. 生成唯一文件名并保存图片
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 生成可访问的 URL (假设你的静态文件挂载在 /static)
    # 前端访问路径: http://localhost:8000/static/images/xxxx.jpg
    image_url = f"/static/images/{unique_filename}"

    # 2. 调用 OCR 引擎 (同步方法)
    # 读取文件字节流用于 OCR
    with open(file_path, "rb") as image_file:
        image_bytes = image_file.read()
    
    try:
        raw_text = ocr_engine.ocr_image(image_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR 识别失败: {str(e)}")

    # 3. 调用 NLP 引擎 (异步方法 - 关键修改)
    # 返回格式: {"corrected_text": "...", "tags": ["...", "..."]}
    try:
        nlp_result = await nlp_engine.analyze(raw_text)
    except Exception as e:
        # 如果 NLP 挂了，至少返回 OCR 结果，不让前端报错
        nlp_result = {"corrected_text": raw_text, "tags": []}

    return {
        "image_url": image_url,
        "raw_text": raw_text,
        "corrected_text": nlp_result["corrected_text"],
        "knowledge_tags": nlp_result["tags"]
    }

# ==========================================
# 2. 题目管理接口 (Questions)
# ==========================================

@router.post("/questions/", response_model=QuestionResponse, summary="创建新题目")
def create_question(
    question_in: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    将前端确认后的题目保存到数据库
    自动绑定 owner_id 为当前登录用户
    """
    # 创建数据库模型
    db_question = Question(
        image_url=question_in.image_url,
        content=question_in.content,   # 这是 DeepSeek 修正后，用户可能又手动修改过的最终文本
        knowledge_tags=question_in.knowledge_tags, # 列表会自动转存为 JSON
        
        # 自动注入字段
        owner_id=current_user.id,
        status="pending" # 默认为待审核
    )
    
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

@router.get("/questions/", response_model=List[QuestionOut], summary="获取题目列表")
def read_questions(
    skip: int = 0, 
    limit: int = 20, 
    db: Session = Depends(get_db)
):
    """
    获取所有题目（分页）
    通常用于首页 Feed 流
    """
    questions = db.query(Question).offset(skip).limit(limit).all()
    return questions

@router.get("/questions/me", response_model=List[QuestionOut], summary="获取我的题目")
def read_my_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    只获取当前登录用户发布的题目
    """
    # 利用 SQLAlchemy 的反向查询，或者直接查 Question 表
    # 方式 1: 直接查 Question 表
    questions = db.query(Question).filter(Question.owner_id == current_user.id).all()
    
    # 方式 2: 如果 User 模型里配置了 questions 关系，也可以用 current_user.questions
    # 但要注意 Lazy Load 问题，方式 1 更稳妥
    
    return questions

@router.get("/questions/{question_id}", response_model=QuestionOut, summary="获取单个题目详情")
def read_single_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return question