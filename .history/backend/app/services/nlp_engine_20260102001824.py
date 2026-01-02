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
            logger.warning("NLP 模型加载跳过，仅使用规则引擎")

    def analyze(self, text: str):
        # 1. 先进行暴力的文本整形
        clean_content = self.auto_fix_latex(text)
        
        # 2. 知识点分类 (仅当文本足够长时)
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

    # 🔥🔥🔥 终极排版修复逻辑 🔥🔥🔥
    def auto_fix_latex(self, text: str) -> str:
        if not text: return ""

        # ==========================
        # 1. 全局字符清洗 (去壳)
        # ==========================
        text = text.strip()
        # 统一括号
        text = text.replace("（", "(").replace("）", ")").replace("：", ": ")
        # ⚠️ 关键：去除 OCR 错误生成的转义花括号 \{ \} -> { }
        # 这一步能解决 y=\{\sqrt{3}\} 显示花括号的问题
        text = text.replace(r"\{", "{").replace(r"\}", "}")
        
        # ==========================
        # 2. 专项错误纠正 (基因改造)
        # ==========================
        # 修复 x_2, y_2 -> x^2, y^2
        # 针对 y_2=4x, x_2+y_2=1 这种常见方程
        text = re.sub(r'([xy])_2([=\+\-\s])', r'\1^2\2', text)  # y_2= -> y^2=
        text = re.sub(r'([xy])_2$', r'\1^2', text)              # 结尾的 y_2
        
        # 修复 \boldsymbol{A} -> \mathbf{A} (加粗向量)
        text = re.sub(r'\\boldsymbol\s*\{(.+?)\}', r'\\mathbf{\1}', text)
        
        # ==========================
        # 3. 智能分数合并 (接骨)
        # ==========================
        # 针对截图里：第一行 "1.", 第二行 "16", 第三行 "3" 的情况
        lines = text.split('\n')
        new_lines = []
        skip_count = 0
        
        for i in range(len(lines)):
            if skip_count > 0:
                skip_count -= 1
                continue
            
            curr = lines[i].strip()
            
            # 检查是否有足够的后续行
            if i + 2 < len(lines):
                next1 = lines[i+1].strip()
                next2 = lines[i+2].strip()
                
                # 模式 A: 纯数字断行 (16 \n 3)
                if curr.isdigit() and next1.isdigit() and len(curr)<4 and len(next1)<4:
                    # 合并为分数
                    new_lines.append(f"$\\frac{{{curr}}}{{{next1}}}$")
                    skip_count = 1
                    continue

                # 模式 B: 题号夹杂分数 (1. \n 16 \n 3) -> 变成 **1.** 16/3
                # 检查 curr 是否是 "1." 这种格式
                is_index = re.match(r'^\d+\.$', curr)
                if is_index and next1.isdigit() and next2.isdigit():
                    logger.info(f"修复题号后的断裂分数: {curr} {next1}/{next2}")
                    # 合并成一行： **1.** $\frac{16}{3}$
                    new_lines.append(f"**{curr}** $\\frac{{{next1}}}{{{next2}}}$")
                    skip_count = 2 # 跳过后面两行
                    continue

            new_lines.append(curr)
        
        text = "\n".join(new_lines)

        # ==========================
        # 4. LaTeX 包裹 (穿衣)
        # ==========================
        # 自动检测裸露的数学命令并加 $
        
        # 4.1 先把已经有的 $$ 拆成 $ (避免嵌套混乱)
        text = text.replace("$$", "$")
        
        # 4.2 暴力包裹策略：
        # 只要这一行包含 \sqrt, \frac, \mathbf, = (且不是文本的=), 就尝试整行包裹
        # 但为了安全，我们用正则只包裹特定的片段
        
        def wrap_math(match):
            content = match.group(0)
            # 如果已经在 $ 里面，不动
            if "$" in content: return content
            return f" ${content}$ "

        # 匹配常见的数学片段
        # 比如 \sqrt{3} 或者 \frac{a}{b} 或者 y^2=4x
        math_pattern = r'(\\sqrt\{.+?\}|\\frac\{.+?\}\{.+?\}|[xy]\^2\s*=\s*.+?)'
        text = re.sub(math_pattern, wrap_math, text)

        # 针对 \textcircled{1} 这种序号
        text = re.sub(r'\\textcircled\{.+?\}', wrap_math, text)

        # ==========================
        # 5. 最终清理
        # ==========================
        # 修复重复的 $ (比如 $$x$$)
        text = text.replace("$$", "$").replace("  ", " ")
        
        # 结构优化：给“解”字加粗换行
        keywords = ["解", "证明", "分析", "已知"]
        for kw in keywords:
            text = re.sub(fr'(?<!\n)\s*({kw}[:：])', fr'\n\n**\1** ', text)

        return text

nlp_service = NLPEngine()