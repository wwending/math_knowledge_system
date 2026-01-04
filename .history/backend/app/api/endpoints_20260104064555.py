import shutil
import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

# --- 内部模块 ---
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User

# 关键修改：只导入 Question，去掉 QuestionStatus
from app.models.question import Question 
from app.schemas.question import QuestionCreate, QuestionResponse, QuestionOut

# 导入引擎
from app.services.ocr_engine import ocr_engine 
from app.services.nlp_engine import nlp_engine 

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
    current_user: User = Depends(get_current_user)
):
    # 1. 保存图片
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    image_url = f"/static/images/{unique_filename}"

    # 2. 读取文件并 OCR
    with open(file_path, "rb") as image_file:
        image_bytes = image_file.read()
    
    raw_text = ocr_engine.ocr_image(image_bytes)

    # 3. NLP 分析
    nlp_result = await nlp_engine.analyze(raw_text)

    return {
        "image_url": image_url,
        "raw_text": raw_text,
        "corrected_text": nlp_result["corrected_text"],
        "knowledge_tags": nlp_result["tags"]
    }

# ==========================================
# 2. 题目管理接口
# ==========================================

@router.post("/questions/", response_model=QuestionResponse)
def create_question(
    question_in: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_question = Question(
        image_url=question_in.image_url,
        content=question_in.content,
        knowledge_tags=question_in.knowledge_tags,
        owner_id=current_user.id,
        status="pending"  # 直接使用字符串
    )
    
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

@router.get("/questions/", response_model=List[QuestionOut])
def read_questions(
    skip: int = 0, 
    limit: int = 20, 
    db: Session = Depends(get_db)
):
    questions = db.query(Question).offset(skip).limit(limit).all()
    return questions

@router.get("/questions/me", response_model=List[QuestionOut])
def read_my_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    questions = db.query(Question).filter(Question.owner_id == current_user.id).all()
    return questions

@router.get("/questions/{question_id}", response_model=QuestionOut)
def read_single_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return question