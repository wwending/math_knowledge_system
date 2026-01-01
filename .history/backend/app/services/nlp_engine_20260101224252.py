import time
from loguru import logger
from transformers import pipeline

import re
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
        
    # --- 🆕 新增：文本清洗与整形核心逻辑 ---
    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        
        # 1. 基础清洗：去除多余空格，统一标点
        text = text.strip()
        text = text.replace("（", "(").replace("）", ")") # 统一括号
        
        # 2. 修复常见 OCR 公式错误 (Pix2Text 特有怪癖修复)
        # 比如把 $ x $ 变成 $x$ (去空格)
        # text = re.sub(r'\$\s+(.*?)\s+\$', r'$\1$', text)
        
        # 3. 核心功能：选择题自动排版 (识别 A. B. C. D.)
        # 逻辑：找到 A. xxx B. xxx，在它们前面加换行符
        patterns = [
            (r'(?<!\n)\s*(A\.|A\、|\(A\))', r'\n\n**A.** '),
            (r'(?<!\n)\s*(B\.|B\、|\(B\))', r'\n\n**B.** '),
            (r'(?<!\n)\s*(C\.|C\、|\(C\))', r'\n\n**C.** '),
            (r'(?<!\n)\s*(D\.|D\、|\(D\))', r'\n\n**D.** '),
        ]
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)

        return text

    def analyze(self, text: str):
        # 1. 先清洗文本
        clean_content = self.clean_text(text)
        
        # 2. 再做分类
        labels = ["函数与导数", "三角函数", "数列", "平面向量", "立体几何", "解析几何", "概率统计", "集合与逻辑"]
        try:
            if self.classifier:
                result = self.classifier(clean_content, labels, multi_label=True)
                # 过滤置信度 > 0.3 的
                tags = [{"label": l, "score": s} for l, s in zip(result['labels'], result['scores']) if s > 0.3]
            else:
                tags = []
        except:
            tags = []

        # 3. 返回清洗后的文本 (content) 和 标签
        return {
            "corrected_text": clean_content, # 返回清洗后的版本
            "tags": tags
        }

# 单例导出
nlp_service = NLPEngine()