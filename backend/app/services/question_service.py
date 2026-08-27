from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.models.user import User
from app.schemas.question import QuestionUpdate

NOT_FOUND = "资源不存在"
QUESTION_TYPES = {"single_choice", "multiple_choice", "fill_blank", "solution", "judge", "unknown"}

def utcnow(): return datetime.now(timezone.utc)
def _expired(value):
    if not value:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= utcnow()
def _tags(tags):
    out=[]; seen=set()
    for tag in tags or []:
        label=(tag.get("label") if isinstance(tag,dict) else getattr(tag,"label","")).strip()
        score=tag.get("score",1.0) if isinstance(tag,dict) else getattr(tag,"score",1.0)
        if label and label not in seen: out.append({"label":label,"score":score}); seen.add(label)
    return out

def latest(db,qid): return db.query(QuestionRevision).filter_by(question_id=qid).order_by(QuestionRevision.rev_no.desc()).first()
def owned(db,user,qid, *, include_trash=False):
    q=db.query(Question).filter(Question.id==qid, Question.user_id==user.id).first()
    now=utcnow()
    if not q or q.purged_at or _expired(q.purge_at) or (not include_trash and q.deleted_at): raise HTTPException(404,NOT_FOUND)
    return q

def normalize_revision(q, rev):
    c=rev.content if rev and isinstance(rev.content,dict) else {}
    return {"text":c.get("text",q.content),"answer":c.get("answer",q.answer),"analysis":c.get("analysis",q.analysis),"knowledge_tags":_tags(c.get("knowledge_tags",q.knowledge_tags)),"question_type":c.get("question_type",q.question_type),"difficulty_level":c.get("difficulty_level",q.difficulty_level),"difficulty_label":c.get("difficulty_label",q.difficulty_label)}

def update(db,user,qid,payload:QuestionUpdate):
    q=owned(db,user,qid); rev=latest(db,qid)
    if payload.expected_revision_no is not None and (rev is None or rev.rev_no != payload.expected_revision_no):
        raise HTTPException(409, "版本冲突")
    cur=normalize_revision(q,rev)
    values=dict(cur)
    for field in payload.model_fields_set - {"expected_revision_no"}:
        if field == "question_type" and getattr(payload, field) not in QUESTION_TYPES:
            raise HTTPException(422, "非法题型")
        value=getattr(payload,field)
        if field in {"answer","analysis"}: value=(value or "").strip() or None
        if field=="content":
            value=value.strip()
            field="text"
        if field=="knowledge_tags": value=_tags(value)
        values[field]=value
    if values==cur: return q,False,rev
    q.content=values["text"]; q.answer=values["answer"]; q.analysis=values["analysis"]; q.knowledge_tags=values["knowledge_tags"]; q.question_type=values["question_type"]; q.difficulty_level=values["difficulty_level"]; q.difficulty_label=values["difficulty_label"]; q.metadata_generation=(q.metadata_generation or 0)+1
    n=(rev.rev_no if rev else 0)+1
    new=QuestionRevision(question=q,rev_no=n,content=values,source_asset_id=rev.source_asset_id if rev else None,figure_asset_id=rev.figure_asset_id if rev else None,crop_bbox=rev.crop_bbox if rev else None,change_reason="manual_edit")
    db.add(new)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "question_id" in str(exc).lower() and "rev_no" in str(exc).lower():
            raise HTTPException(409, "版本冲突") from exc
        raise
    db.refresh(q)
    return q, True, new

def trash(db,user,qid):
    q=owned(db,user,qid); q.deleted_at=utcnow(); q.purge_at=q.deleted_at+timedelta(days=30); q.metadata_generation=(q.metadata_generation or 0)+1; db.commit(); return q

def restore(db,user,qid):
    q=owned(db,user,qid,include_trash=True)
    if not q.deleted_at: raise HTTPException(409,"生命周期状态冲突")
    q.deleted_at=None; q.purge_at=None; db.commit(); return q

def permanent(db,user,qid):
    q=owned(db,user,qid,include_trash=True)
    if not q.deleted_at: raise HTTPException(409,"生命周期状态冲突")
    q.purged_at=utcnow(); q.metadata_generation=(q.metadata_generation or 0)+1; db.commit(); return q
