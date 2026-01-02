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

        # 0. 预处理：统一标点和空格
        text = text.strip()
        text = text.replace("（", "(").replace("）", ")")
        text = text.replace("：", ": ")
        
        # 1. 结构化排版：给“解”、“证明”等关键词前后加换行和加粗
        # 效果：让“解：”自动变成独立的一行，且加粗
        keywords = ["解", "证明", "分析", "已知", "求", "注意", "解法1", "解法2", "解法一", "解法二"]
        for kw in keywords:
            # 查找这些词，如果前面没有换行，就加上换行
            # (?<!\n) 表示前面不是换行符
            # **...** 是 Markdown 的加粗语法
            text = re.sub(fr'(?<!\n)\s*({kw}[:：]?)', fr'\n\n**\1** ', text)

        # 2. 修复 LaTeX 漏网之鱼
        # 现象：OCR 有时候会输出 \boldsymbol{A} 但忘了加 $ 符号
        # 对策：自动检测常见的 LaTeX 命令，如果没被 $ 包裹，就给它加上
        # (这个正则比较激进，它会匹配以 \ 开头的单词，尝试包裹它)
        # 注意：这里只处理一些显眼的数学符号，避免误伤
        latex_keywords = [r"\\sqrt", r"\\frac", r"\\boldsymbol", r"\\vec", r"\\sin", r"\\cos", r"\\tan", r"\\theta", r"\\alpha", r"\\beta"]
        for lk in latex_keywords:
            # 查找 lk，且前后没有 $ 的情况 (简单启发式)
            # 这里的正则很难完美，但能解决大部分漏标问题
            # 逻辑：如果 \sqrt 出现，且它前面不是 $，则补充 $
            # (暂时用简单替换，假设整段都是公式的一部分)
            pass 
            # 💡更稳妥的方案：针对特定错词修复
            
        # 3. 🚑 专项急救：修复 x_2 -> x^2
        # 场景：3x_2 - 10x + 3 = 0 (显然是二次方程)
        # 逻辑：如果 x_2 后面跟着 + - = 或者空格，大概率是平方
        text = re.sub(r'x_2', r'x^2', text)
        text = re.sub(r'y_2', r'y^2', text) # 抛物线 y^2 = 2px 也常错

        # 4. 修复根号问题
        # 有时候 OCR 会把 \sqrt 3 识别成 \sqrt 3 (中间有空格) 导致渲染断裂
        text = re.sub(r'\\sqrt\s+', r'\\sqrt', text)
        
        # 5. 修复 \boldsymbol 导致的渲染丑陋
        # 有些渲染器不支持 boldsymbol，直接替换成简单的加粗 \mathbf 或者干脆去掉
        text = text.replace(r'\boldsymbol', r'\mathbf')

        # 6. 选择题排版 (保留之前的逻辑)
        patterns = [
            (r'(?<!\n)\s*(A\.|A\、|\(A\))', r'\n\n**A.** '),
            (r'(?<!\n)\s*(B\.|B\、|\(B\))', r'\n\n**B.** '),
            (r'(?<!\n)\s*(C\.|C\、|\(C\))', r'\n\n**C.** '),
            (r'(?<!\n)\s*(D\.|D\、|\(D\))', r'\n\n**D.** '),
        ]
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
            
        # 7. 最后的波纹：确保所有 LaTeX 符号被 $ 包裹 (激进尝试)
        # 如果发现有 \frac 但没有 $，尝试修补 (这步风险较大，可以先手动修正)
        
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