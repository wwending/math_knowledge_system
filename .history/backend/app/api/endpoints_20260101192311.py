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

import fitz # PyMuPDF
import uuid
import shutil
import os

from sqlalchemy import or_

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

@router.get("/tags", response_model=List[str])
def get_all_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 查询当前用户所有题目的标签
    # 注意：这里是简化实现。生产环境建议建一个单独的 Tags 表
    questions = db.query(Question).filter(Question.owner_id == current_user.id).all()
    
    unique_tags = set()
    for q in questions:
        if q.knowledge_tags:
            for tag_obj in q.knowledge_tags:
                if isinstance(tag_obj, dict):
                    unique_tags.add(tag_obj.get("label"))
                # 兼容可能的不同数据格式
                elif hasattr(tag_obj, 'label'):
                     unique_tags.add(tag_obj.label)
    
    return sorted(list(unique_tags))

@router.get("/history", response_model=List[QuestionOut])
def get_history(
    skip: int = 0, 
    limit: int = 100, 
    keyword: str = None, # 新增搜索关键词
    tag: str = None,     # 新增标签筛选
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

    # --- 核心筛选逻辑 ---
    # 1. 关键词搜索 (搜索内容)
    if keyword:
        query = query.filter(Question.content.like(f"%{keyword}%"))
    
    # 2. 标签筛选 (因为是 JSON 存的，这里用简单的字符串匹配做 Hack)
    # 标准做法应该用 JSON 查询，但 SQLite 对此支持有限，这样最稳妥
    if tag:
        # 匹配 JSON 字符串中包含该 tag 的记录
        query = query.filter(Question.knowledge_tags.like(f'%{tag}%'))
    
    # 按时间倒序
    questions = query.order_by(Question.created_at.desc()).offset(skip).limit(limit).all()
    return questions
    

@router.post("/upload_pdf")
def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user) # 只有登录用户可以用
):
    # 1. 验证是否为 PDF
    if not file.content_type.endswith("pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")

    # 2. 准备目录
    pdf_temp_dir = os.path.join("static", "pdf_temp")
    if not os.path.exists(pdf_temp_dir):
        os.makedirs(pdf_temp_dir)

    # 3. 保存 PDF 原文件
    file_ext = file.filename.split(".")[-1]
    pdf_filename = f"{uuid.uuid4()}.{file_ext}"
    pdf_path = os.path.join(pdf_temp_dir, pdf_filename)
    
    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 4. 核心逻辑: PDF -> 图片列表
    image_urls = []
    try:
        doc = fitz.open(pdf_path) # 打开 PDF
        # 遍历每一页
        for i in range(len(doc)):
            page = doc.load_page(i)
            # 设置缩放矩阵 (2.0 表示 2 倍清晰度，OCR 需要高清图)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            
            # 保存图片
            page_img_name = f"{pdf_filename}_page_{i}.jpg"
            page_img_path = os.path.join(pdf_temp_dir, page_img_name)
            pix.save(page_img_path)
            
            # 记录相对路径供前端访问
            image_urls.append(f"images/pdf_temp/{page_img_name}") # 注意这里路径要对应 mount 配置
            
        doc.close()
        
        # 修正返回路径: 我们的 static mount 在 /static
        # 所以前端访问应该是 http://host/static/pdf_temp/xxx.jpg
        # 这里返回相对路径: pdf_temp/xxx.jpg
        return {
            "success": True, 
            "total_pages": len(image_urls), 
            "images": [f"pdf_temp/{os.path.basename(p)}" for p in image_urls]
        }

    except Exception as e:
        logger.error(f"PDF 处理失败: {e}")
        raise HTTPException(status_code=500, detail="PDF 解析失败")