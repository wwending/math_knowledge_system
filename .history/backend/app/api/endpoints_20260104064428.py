import shutil
import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.question import Question, QuestionStatus
from app.schemas.question import QuestionCreate, QuestionResponse, QuestionOut

# === 关键导入点 ===
# 必须和上面两步定义的变量名一致
from app.services.ocr_engine import ocr_engine 
from app.services.nlp_engine import nlp_engine 

router = APIRouter()
UPLOAD_DIR = "app/static/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/ocr/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # 1. 保存图片
    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # 2. 读取图片进行 OCR
    with open(path, "rb") as f:
        img_bytes = f.read()
    
    # 调用 ocr_engine
    raw_text = ocr_engine.ocr_image(img_bytes)

    # 3. 调用 nlp_engine
    nlp_result = await nlp_engine.analyze(raw_text)

    return {
        "image_url": f"/static/images/{filename}",
        "raw_text": raw_text,
        "corrected_text": nlp_result["corrected_text"],
        "knowledge_tags": nlp_result["tags"]
    }

# 简单的题目接口保留
@router.post("/questions/", response_model=QuestionResponse)
def create_question(q: QuestionCreate, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    db_q = Question(
        image_url=q.image_url, 
        content=q.content, 
        knowledge_tags=q.knowledge_tags,
        owner_id=u.id,
        status="pending"
    )
    db.add(db_q)
    db.commit()
    db.refresh(db_q)
    return db_q

@router.get("/questions/", response_model=List[QuestionOut])
def list_questions(db: Session = Depends(get_db)):
    return db.query(Question).all()

@router.get("/questions/me", response_model=List[QuestionOut])
def my_questions(db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    return db.query(Question).filter(Question.owner_id == u.id).all()