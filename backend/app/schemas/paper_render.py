from typing import Any, Literal, Optional

from pydantic import BaseModel


class PaperRenderRequest(BaseModel):
    template_type: Literal["homework"] = "homework"
    version: Literal["student"] = "student"
    paper_size: Literal["A4"] = "A4"
    group_by: Literal["question_type"] = "question_type"
    sort_by: Literal["position"] = "position"
    answer_area_mode: Literal["none", "after_each_question"] = "none"


class PaperRenderKnowledgeTag(BaseModel):
    label: str
    score: Optional[float] = None


class PaperRenderAnswerArea(BaseModel):
    mode: Literal["after_each_question"]
    lines: int = 4


class PaperRenderItem(BaseModel):
    paper_item_id: int
    question_id: int
    position: int
    display_number: int
    score: Optional[float] = None
    content: str
    question_type: str
    question_type_label: str
    knowledge_tags: list[PaperRenderKnowledgeTag]
    answer_area: Optional[PaperRenderAnswerArea] = None


class PaperRenderSection(BaseModel):
    key: str
    title: str
    items: list[PaperRenderItem]


class PaperRenderPaperMeta(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    item_count: int
    total_score: float


class PaperRenderLayout(BaseModel):
    show_answers: Literal[False] = False
    show_analysis: Literal[False] = False


class PaperRenderModel(BaseModel):
    template_type: Literal["homework"]
    version: Literal["student"]
    paper_size: Literal["A4"]
    group_by: Literal["question_type"]
    sort_by: Literal["position"]
    answer_area_mode: Literal["none", "after_each_question"]
    paper: PaperRenderPaperMeta
    layout: PaperRenderLayout
    sections: list[PaperRenderSection]
