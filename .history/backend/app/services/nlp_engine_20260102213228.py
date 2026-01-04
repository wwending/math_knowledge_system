import re
from loguru import logger
from transformers import pipeline

class NLPEngine:
    def __init__(self):
        try:
            self.classifier = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
        except:
            pass

    def analyze(self, text: str):
        # 保持原始文本的纯净，只做最小限度的标点统一
        # 把“脏活”全交给前端渲染引擎去做
        clean_content = text.strip().replace("（", "(").replace("）", ")").replace("：", ": ")
        
        tags = []
        if self.classifier and len(clean_content) > 5:
            try:
                labels = ["函数与导数", "三角函数", "数列", "平面向量", "立体几何", "解析几何", "概率统计"]
                result = self.classifier(clean_content, labels, multi_label=True)
                tags = [{"label": l, "score": s} for l, s in zip(result['labels'], result['scores']) if s > 0.4]
            except:
                pass

        return {
            "corrected_text": clean_content,
            "tags": tags
        }

nlp_service = NLPEngine()