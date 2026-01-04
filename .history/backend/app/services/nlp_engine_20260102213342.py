import re
from loguru import logger
from transformers import pipeline

class NLPEngine:
    def __init__(self):
        self.classifier = None

    # ✅ 把这个方法加回来了，main.py 启动时需要调用它
    def initialize(self):
        logger.info("正在初始化 NLP 引擎...")
        try:
            # 尝试加载分类模型 (如果加载失败不影响主流程)
            self.classifier = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
            logger.success("NLP 模型加载成功")
        except Exception as e:
            logger.warning(f"NLP 模型加载跳过，仅使用规则引擎: {e}")

    def analyze(self, text: str):
        # 保持原始文本的纯净，只做最小限度的标点统一
        # 把“脏活”全交给前端渲染引擎去做
        if not text:
            return {"corrected_text": "", "tags": []}

        clean_content = text.strip().replace("（", "(").replace("）", ")").replace("：", ": ")
        
        tags = []
        # 只有文本够长且模型加载成功才跑分类
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