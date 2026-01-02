import re
from loguru import logger
from transformers import pipeline

class NLPEngine:
    def __init__(self):
        self.classifier = None

    def initialize(self):
        logger.info("正在加载 NLP 规则引擎...")
        # 这里的模型加载可以保留，也可以像之前一样 try-catch
        try:
            self.classifier = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
            logger.success("NLP 模型加载成功")
        except Exception as e:
            logger.warning(f"NLP 模型加载失败 (不影响排版功能): {e}")

    def analyze(self, text: str):
        # 1. 核心步骤：智能排版清洗
        clean_content = self.auto_fix_latex(text)
        
        # 2. 知识点分类 (如果 text 太短或模型没加载，返回空)
        labels = ["函数与导数", "三角函数", "数列", "平面向量", "立体几何", "解析几何", "概率统计", "集合与逻辑"]
        tags = []
        if self.classifier and len(clean_content) > 5:
            try:
                result = self.classifier(clean_content, labels, multi_label=True)
                tags = [{"label": l, "score": s} for l, s in zip(result['labels'], result['scores']) if s > 0.35]
            except:
                pass

        return {
            "corrected_text": clean_content,
            "tags": tags
        }

    # 🔥🔥🔥 核心：暴力的自动排版修复函数 🔥🔥🔥
    def auto_fix_latex(self, text: str) -> str:
        if not text: return ""

        # 0. 基础清理
        text = text.strip()
        # 统一标点
        text = text.replace("（", "(").replace("）", ")").replace("：", ": ")

        # ---------------------------------------------------------
        # 🔧 修复 1: 暴力修复分数断行 (针对 3/16 变成两行的问题)
        # ---------------------------------------------------------
        # 逻辑：如果有一行全是数字，下一行也全是数字，且两行都很短，
        # 我们有理由怀疑这是个断掉的分数。
        # 这是一个激进的策略，但对于试卷识别很有效。
        lines = text.split('\n')
        new_lines = []
        skip_next = False
        
        for i in range(len(lines)):
            if skip_next:
                skip_next = False
                continue
            
            curr_line = lines[i].strip()
            # 如果是最后一行，直接添加
            if i == len(lines) - 1:
                new_lines.append(curr_line)
                break
                
            next_line = lines[i+1].strip()
            
            # 检测特征：当前行是短数字，下一行也是短数字
            # 比如 "3" 和 "16"
            if curr_line.isdigit() and next_line.isdigit() and len(curr_line)<3 and len(next_line)<3:
                # 💥 发现断裂分数！合并它们！
                logger.info(f"触发分数合并: {curr_line} / {next_line}")
                new_lines.append(f"$\\frac{{{curr_line}}}{{{next_line}}}$")
                skip_next = True # 跳过下一行，因为已经合并了
            else:
                new_lines.append(curr_line)
        
        text = "\n".join(new_lines)

        # ---------------------------------------------------------
        # 🔧 修复 2: 常见的 OCR 上标错误
        # ---------------------------------------------------------
        # 把 x_2, y_2 变成 x^2, y^2 (仅限小写字母，防止把 H_2O 这种改错)
        text = re.sub(r'([a-z])_2', r'\1^2', text)
        text = re.sub(r'([a-z])_3', r'\1^3', text)
        
        # ---------------------------------------------------------
        # 🔧 修复 3: "裸奔" LaTeX 命令全自动包裹
        # ---------------------------------------------------------
        # 很多时候 OCR 识别出了 \sqrt{3} 但没加 $，导致显示原码。
        # 我们用正则查找所有常见的数学命令，如果它们不在 $ 里，就加上。
        
        math_commands = [
            r"\\sqrt", r"\\frac", r"\\boldsymbol", r"\\vec", r"\\overline",
            r"\\sin", r"\\cos", r"\\tan", r"\\ln", r"\\log",
            r"\\alpha", r"\\beta", r"\\theta", r"\\lambda", r"\\mu", r"\\pi",
            r"\\triangle", r"\\angle", r"\\perp"
        ]
        
        # 构建一个巨大的正则： (\\sqrt|\\frac|...)(...参数...)
        # 这是一个简化版策略：只要看到这些词，且前面没有 $，就尝试包裹它
        
        # 3.1 修复 \boldsymbol{A} -> $\mathbf{A}$ (改用更通用的 mathbf)
        text = re.sub(r'\\boldsymbol\s*\{(.+?)\}', r'$\\mathbf{\1}$', text)
        
        # 3.2 修复简单的 \sqrt{3} 或 \sqrt 3
        # 匹配 \sqrt 后面的内容，直到空格或标点
        def wrap_math(match):
            content = match.group(0)
            # 如果已经被 $ 包裹，忽略
            if content.startswith('$'): return content
            return f"${content}$"

        # 针对 \frac{a}{b}
        text = re.sub(r'\\frac\s*\{.+?\}\s*\{.+?\}', wrap_math, text)
        
        # 针对 \sqrt{...}
        text = re.sub(r'\\sqrt\s*\{.+?\}', wrap_math, text)
        
        # ---------------------------------------------------------
        # 🔧 修复 4: 关键结构优化 (题号、选项)
        # ---------------------------------------------------------
        # 把 "1." "2." 这种题号加粗并换行
        text = re.sub(r'(?<!\n)\n(\d+\.)', r'\n\n**\1**', text)
        
        # 把 "解：" "证明：" 变成独立行
        keywords = ["解", "证明", "分析"]
        for kw in keywords:
            text = re.sub(fr'(?<!\n)\s*({kw}[:：])', fr'\n\n**\1** ', text)

        # ---------------------------------------------------------
        # 🔧 修复 5: 最后的兜底
        # ---------------------------------------------------------
        # 有时候 OCR 会输出连续的两个 $$，比如 $$x$$，这没事。
        # 但有时候是 $ $x$ $，这会乱。清理一下。
        text = text.replace("$$", "$") # 先全变单$
        # text = text.replace("$$", "$$") # 如果需要多行公式再改回来，目前先用单行比较稳

        return text

nlp_service = NLPEngine()