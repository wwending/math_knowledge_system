import time
from loguru import logger
from transformers import pipeline

import re
from loguru import logger
from transformers import pipeline

import re

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
        
    # --- 🆕 升级版：智能排版与纠错 ---
    def clean_text(self, text: str) -> str:
        if not text:
            return ""

        # 0. 基础预处理
        text = text.strip()
        # 统一中文括号和冒号
        text = text.replace("（", "(").replace("）", ")").replace("：", ": ")
        
        # 1. 🚑 截图问题专项修复：x_2, y_2 -> x^2, y^2
        # 高中数学里，抛物线 y^2=2px 和直线方程中，x_2 极大概率是 OCR 识别错了 x^2
        # 我们用正则把 x_2, y_2 替换为 x^2, y^2
        text = re.sub(r'([xy])_2', r'\1^2', text)

        # 2. 🚑 截图问题专项修复：\boldsymbol -> \mathbf
        # 很多简单的 KaTeX 配置不渲染 boldsymbol，且 OCR 经常忘了加 $
        # 我们直接把它变成简单的粗体，并强制加上 $ 包裹
        # 逻辑：查找 \boldsymbol{X}，替换为 $\mathbf{X}$
        text = re.sub(r'\\boldsymbol\{(\w+)\}', r'$\\mathbf{\1}$', text)

        # 3. 🚑 截图问题专项修复：裸露的 \sqrt, \frac 等
        # 如果 \sqrt 前面没有 $，给它补上。
        # 这里的逻辑是：如果遇到以 \ 开头的数学命令，且它不在 $...$ 内部（简化判断），就给它包上
        # 简单暴力的补救：
        text = text.replace(r'\sqrt', r'$\sqrt$') # 先弄坏，再用下一行修
        text = text.replace(r'$$\sqrt$$', r'$\sqrt') # 修复重复加的情况
        # 这种正则比较难写完美，建议优先用下面的“人工编辑”方案兜底

        # 4. 结构优化：关键词换行加粗
        keywords = ["解", "证明", "分析", "已知", "求", "解法1", "解法2", "解法一", "解法二", "注意"]
        for kw in keywords:
            text = re.sub(fr'(?<!\n)\s*({kw}[:：]?)', fr'\n\n**\1** ', text)

        # 5. 选择题排版
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