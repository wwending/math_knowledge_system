import re
from loguru import logger
from transformers import pipeline

class NLPEngine:
    def __init__(self):
        self.classifier = None

    def initialize(self):
        try:
            self.classifier = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
            logger.success("NLP 模型加载成功")
        except:
            logger.warning("NLP 模型仅使用规则引擎")

    def analyze(self, text: str):
        # 百度出来的结果通常比较好，只需要轻微清洗
        clean_content = self.clean_baidu_result(text)
        
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

    def clean_baidu_result(self, text: str) -> str:
        if not text: return ""
        
        text = text.strip()
        # 统一标点
        text = text.replace("（", "(").replace("）", ")").replace("：", ": ")
        
        # 百度的一个小毛病：有时候分数 \frac 1 2 没加括号
        # 简单的修复（可选）
        
        # 结构优化：给关键词加粗换行 (百度的换行通常是正确的，这里主要是加粗)
        keywords = ["解", "证明", "分析", "已知"]
        for kw in keywords:
            # 百度可能已经换行了，所以兼容一下
            text = re.sub(fr'(?<!\n)\s*({kw}[:：]?)', fr'\n\n**\1** ', text)
            
        # 题号加粗
        text = re.sub(r'(?m)^(\d+\.)', r'\n\n**\1**', text)

        # 选项加粗
        patterns = [
            (r'(A\.|A\、)', r'\n\n**A.** '),
            (r'(B\.|B\、)', r'\n\n**B.** '),
            (r'(C\.|C\、)', r'\n\n**C.** '),
            (r'(D\.|D\、)', r'\n\n**D.** '),
        ]
        for p, r in patterns:
            text = re.sub(p, r, text)

        return text

nlp_service = NLPEngine()