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
        # 1. 针对百度结果进行清洗和封装
        clean_content = self.clean_baidu_result(text)
        
        # 2. 知识点分类
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

    # 🔥🔥🔥 百度 OCR 专属清洗逻辑 🔥🔥🔥
    def clean_baidu_result(self, text: str) -> str:
        if not text: return ""
        
        # 1. 基础预处理
        text = text.strip()
        text = text.replace("（", "(").replace("）", ")").replace("：", ": ")
        
        # 2. 🚑 紧急修复：给裸露的 LaTeX 穿上衣服 ($...$)
        # 百度返回的经常是纯 LaTeX 代码，比如 \frac{1}{2}，我们需要变成 $\frac{1}{2}$
        
        # 定义一个正则，匹配常见的 LaTeX 模式
        # 包括：\开头命令、^{上标}、_{下标}、运算符号
        
        # 策略：先把现有的 $ 去掉，防止重复包裹，然后重新识别
        text = text.replace("$", "") 

        def wrap_math(match):
            content = match.group(0)
            # 过滤掉普通的中文字符或标点，只包裹真正的数学部分
            if not content.strip(): return content
            return f" ${content}$ "

        # 正则含义：
        # 1. \left ... \right (百度很喜欢用这个)
        # 2. \command{...} 或 \command 
        # 3. 包含 ^ 或 _ 的式子
        # 4. 包含 = < > 的式子 (且周围有字母)
        
        # A. 优先处理大块结构 \left( ... \right)
        text = re.sub(r'\\left\(.+?\\right\)', wrap_math, text)
        
        # B. 处理 \frac{...}{...} 和 \sqrt{...}
        # 注意：这里用简单的贪婪匹配可能会有问题，但在试卷场景通常够用
        text = re.sub(r'\\(frac|sqrt|sin|cos|tan|ln|log|vec|overrightarrow)\s*\{.+?\}', wrap_math, text)
        text = re.sub(r'\\(alpha|beta|theta|lambda|mu|pi|triangle|angle|perp|circ)', wrap_math, text)

        # C. 处理带有上标下标的式子 (比如 x^2, a_n)
        # 匹配：字母/数字 接着 ^ 或 _ 接着 字母/数字/{...}
        text = re.sub(r'[a-zA-Z0-9]+\s*[\^_]\s*([a-zA-Z0-9]+|\{.+?\})', wrap_math, text)

        # D. 处理孤立的分数 (1/2 这种没转义的)
        text = re.sub(r'(?<!\d)(\d+)\s*/\s*(\d+)(?!\d)', r' $\\frac{\1}{\2}$ ', text)

        # 3. 结构优化
        # 题号加粗 (1. 2.)
        text = re.sub(r'(?m)^(\d+\.)', r'\n\n**\1**', text)
        
        # 关键词加粗
        keywords = ["解", "证明", "分析", "已知", "求"]
        for kw in keywords:
            text = re.sub(fr'(?<!\n)\s*({kw}[:：]?)', fr'\n\n**\1** ', text)

        # 选项加粗
        patterns = [
            (r'(A\.|A\、)', r'\n\n**A.** '),
            (r'(B\.|B\、)', r'\n\n**B.** '),
            (r'(C\.|C\、)', r'\n\n**C.** '),
            (r'(D\.|D\、)', r'\n\n**D.** '),
        ]
        for p, r in patterns:
            text = re.sub(p, r, text)

        # 4. 收尾清理
        # 修复可能出现的重复 $ (比如 $$x$$) -> $x$
        text = re.sub(r'\$+', '$', text)
        # 修复 $ $ 空匹配
        text = text.replace("$  $", " ")
        
        return text

nlp_service = NLPEngine()