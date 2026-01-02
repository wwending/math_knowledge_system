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
        except Exception:
            logger.warning("NLP 模型仅使用规则引擎")

    def analyze(self, text: str):
        # 1. 深度清洗
        clean_content = self.deep_clean_latex(text)
        
        # 2. 知识点分类
        tags = []
        if self.classifier and len(clean_content) > 10:
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

    # 🔥🔥🔥 深度清洗函数 (正则风暴版) 🔥🔥🔥
    def deep_clean_latex(self, text: str) -> str:
        if not text: return ""

        # ================================
        # 0. 预处理：扫除隐形干扰字符
        # ================================
        text = text.strip()
        # 统一括号、冒号，去除奇怪的 Unicode 空格
        text = text.replace("（", "(").replace("）", ")").replace("：", ": ")
        text = text.replace("\u00A0", " ").replace("\r", "")
        
        # ================================
        # 1. 结构缝合：修复断裂的分数 (关键更新)
        # ================================
        # 使用 (?m) 开启多行模式，^ 和 $ 匹配行首行尾
        
        # 场景 A: 题号 + 分子 + 分母 (三行)
        # 匹配：行1是"1." -> 行2是数字 -> 行3是数字
        # 例子：
        # 1.
        # 16
        # 3
        # 替换为： **1.** $\frac{16}{3}$
        pattern_3_lines = r'(?m)^(\d+\.)\s*\n\s*(\d+)\s*\n\s*(\d+)\s*$'
        text = re.sub(pattern_3_lines, r'**\1** $\\frac{\2}{\3}$', text)

        # 场景 B: 纯数字断行 (两行)
        # 匹配：行1是短数字 -> 行2是短数字 (防止误伤普通段落，限制长度<5)
        # 例子：
        # 16
        # 3
        pattern_2_lines = r'(?m)^(\d{1,4})\s*\n\s*(\d{1,4})\s*$'
        text = re.sub(pattern_2_lines, r'$\\frac{\1}{\2}$', text)

        # ================================
        # 2. 顽固错误修复 (y_2, \{ \})
        # ================================
        
        # 🔧 修复 x_2 -> x^2
        # 使用 IGNORECASE (re.I) 忽略大小写，解决 Y_2 或 y_2
        # 逻辑：字母 + 下划线 + 2 -> 字母 + ^2
        text = re.sub(r'([a-zA-Z])_2', r'\1^2', text, flags=re.I)
        text = re.sub(r'([a-zA-Z])_3', r'\1^3', text, flags=re.I)

        # 🔧 去除多余的转义花括号
        # 现象：y=\{\sqrt{3}\} -> y={\sqrt{3}}
        # 这里的 \\\\{ 代表匹配 literal backslash + {
        text = re.sub(r'\\\{', r'{', text)
        text = re.sub(r'\\\}', r'}', text)
        
        # 🔧 修复 \boldsymbol{A} -> \mathbf{A}
        text = re.sub(r'\\boldsymbol\s*\{(.+?)\}', r'\\mathbf{\1}', text)

        # ================================
        # 3. 裸露 LaTeX 包裹
        # ================================
        # 先把 $$ 降级为 $
        text = text.replace("$$", "$")

        # 定义一个只包裹数学内容的函数
        def wrap_math(match):
            content = match.group(0)
            # 避免重复包裹
            if "$" in content: return content
            # 如果是单纯的题号 "1." 或者是汉字，不要包
            if re.match(r'^\d+\.$', content): return content
            return f" ${content}$ "

        # 匹配特征：
        # 1. \sqrt{...}
        # 2. \frac{...}{...}
        # 3. y^2=... 或 x^2...
        # 4. A=... (简单的等式)
        math_pattern = r'(\\sqrt\{.+?\}|\\frac\{.+?\}\{.+?\}|[a-zA-Z]\^2\s*[=><].+?)'
        text = re.sub(math_pattern, wrap_math, text)

        # 修复离散的根号: \sqrt 3 -> $\sqrt{3}$
        # 匹配 \sqrt 空格 数字
        text = re.sub(r'\\sqrt\s+(\d+)', r'$\\sqrt{\1}$', text)

        # ================================
        # 4. 版面优化
        # ================================
        # 题号加粗
        text = re.sub(r'(?m)^(\d+\.)', r'\n\n**\1**', text)
        
        # 关键词加粗换行
        keywords = ["解", "证明", "分析", "已知", "解法1", "解法2"]
        for kw in keywords:
            text = re.sub(fr'(?<!\n)\s*({kw}[:：]?)', fr'\n\n**\1** ', text)
            
        # 选择题选项优化
        patterns = [
            (r'(?<!\n)\s*(A\.|A\、|\(A\))', r'\n\n**A.** '),
            (r'(?<!\n)\s*(B\.|B\、|\(B\))', r'\n\n**B.** '),
            (r'(?<!\n)\s*(C\.|C\、|\(C\))', r'\n\n**C.** '),
            (r'(?<!\n)\s*(D\.|D\、|\(D\))', r'\n\n**D.** '),
        ]
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)

        # 最后去除多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text

nlp_service = NLPEngine()