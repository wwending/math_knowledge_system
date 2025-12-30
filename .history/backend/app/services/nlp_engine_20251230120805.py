import time
from loguru import logger
from transformers import pipeline

class NLPEngine:
    _instance = None
    _classifier = None
    
    # 定义我们的知识点标签体系 (基于你的目录)
    LABELS = [
        "集合与常用逻辑用语",
        "一元二次函数、方程与不等式",
        "函数与导数",
        "三角函数",
        "解三角形",
        "平面向量",
        "复数",
        "数列",
        "立体几何与空间向量",
        "解析几何",
        "计数原理",
        "概率统计"
    ]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NLPEngine, cls).__new__(cls)
        return cls._instance

    def initialize(self):
        """
        加载 NLP 模型 (Zero-Shot)
        """
        if self._classifier is not None:
            return

        logger.info("正在加载 NLP 知识点分类模型 (这可能需要下载约 400MB)...")
        start_time = time.time()
        
        try:
            # 选型理由：
            # model="joe32140/bert-base-chinese-zero-shot" 是一个专门针对中文优化的零样本分类模型
            # device=0 表示使用你的 RTX 2060
            self._classifier = pipeline(
                "zero-shot-classification", 
                # 这是一个支持中英混合的超强 Zero-Shot 模型
                model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", 
                device=0 
            )
            
            cost = time.time() - start_time
            logger.success(f"NLP 模型加载完成！耗时: {cost:.2f}s")
        except Exception as e:
            logger.error(f"NLP 模型加载失败: {e}")
            # 如果 GPU 显存不够，可以尝试设为 device=-1 (使用 CPU)
            raise e

    def classify(self, text: str) -> dict:
        """
        输入题目文本，输出可能性最高的前 3 个知识点
        """
        if not text or len(text.strip()) < 5:
            return {"top_label": "未知", "scores": {}}

        if self._classifier is None:
            self.initialize()

        # 1. 文本截断：如果题目太长，只取前 512 个字 (BERT 的限制)
        safe_text = text[:512]

        # 2. 推理
        # multi_label=True 允许一道题属于多个知识点 (比如既是函数又是导数)
        result = self._classifier(
            safe_text, 
            self.LABELS, 
            multi_label=True
        )

        # 3. 格式化结果
        # result['labels'] 是按概率从高到低排序的
        # result['scores'] 是对应的概率值
        
        top_labels = result['labels'][:3] # 取前三名
        top_scores = result['scores'][:3]
        
        return {
            "top_label": top_labels[0], # 概率最高的那个
            "all_predictions": [
                {"label": l, "score": round(s, 3)} 
                for l, s in zip(top_labels, top_scores)
            ]
        }

# 单例导出
nlp_service = NLPEngine()