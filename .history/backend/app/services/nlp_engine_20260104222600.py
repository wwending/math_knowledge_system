import os
import json
import re
from loguru import logger
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class NLPEngine:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL")
        self.client = None

    def initialize(self):
        """初始化 DeepSeek 客户端"""
        if self.api_key and self.base_url:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                logger.success("✅ DeepSeek LLM 客户端初始化成功")
            except Exception as e:
                logger.error(f"❌ DeepSeek 初始化失败: {e}")
        else:
            logger.warning("⚠️ 未配置 DeepSeek API Key，智能分析无法使用")

    def analyze(self, text: str):
        """
        全权交给 DeepSeek 处理：
        1. 清洗 OCR 乱码（修复重复分数、断行、错误符号）
        2. 标准化 LaTeX 排版
        3. 提取知识点
        """
        if not text or not self.client:
            return {"corrected_text": text, "tags": []}

        logger.info("正在请求 DeepSeek 进行全能分析...")

        # --- 🔥 核心提示词：针对百度 OCR 的“脏数据”定向优化 ---
        system_prompt = """
你是一个高中数学排版专家和知识点分类助手。
你的任务是处理 OCR 识别出的原始混乱文本，输出标准的 Markdown + LaTeX 格式，并提取知识点。

### 输入数据常见错误（必须修复）：
1. **重复 LaTeX**：OCR 常把分数识别两遍，如 `\\frac{10}\\frac{10}{3}`，请修正为 `\\frac{10}{3}`。
2. **字符断裂**：如 `s i n` -> `\\sin`，`c o s` -> `\\cos`。
3. **符号错误**：如 `p = l` (字母l) 应修正为 `p = 1` (数字1)，`0'` 应修正为 `^\\circ` (度数)。
4. **缺失公式包围**：所有数学符号（包括单个字母 x, y, p, A, B）必须用 `$` 包裹，独立公式用 `$$`。

### 排版要求：
1. **题号**：如 "1." 或 "2." 请使用 `**1.**` 加粗。
2. **结构**：关键词（如 "**解法1：**"、"**已知**"）前请换行并加粗。
3. **向量**：使用 `\\vec{a}` 或 `\\mathbf{a}`。

### 输出格式（JSON）：
必须严格返回 JSON 格式，包含两个字段：
- `corrected_text`: 修复后的完整 Markdown 文本。
- `tags`: 一个字符串数组，包含 1-3 个核心知识点（如 ["抛物线", "焦点弦", "面积公式"]）。

不要输出任何 Markdown 代码块标记（如 ```json），直接输出 JSON 字符串。
"""

        user_prompt = f"请处理以下 OCR 原始文本：\n\n{text}"

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",  # 或 deepseek-v3
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                # 开启 JSON 模式 (DeepSeek 支持)
                response_format={"type": "json_object"}, 
                temperature=0.1, # 低温度，保证修复的准确性
                max_tokens=4000
            )

            result_content = response.choices[0].message.content
            logger.debug(f"DeepSeek 响应: {result_content}")

            # 解析 JSON
            try:
                data = json.loads(result_content)
                return {
                    "corrected_text": data.get("corrected_text", text),
                    "tags": data.get("tags", [])
                }
            except json.JSONDecodeError:
                # 兜底：如果模型没返回完美 JSON，尝试简单清洗
                logger.warning("DeepSeek 返回非标准 JSON，尝试提取")
                return {"corrected_text": result_content, "tags": []}

        except Exception as e:
            logger.error(f"DeepSeek 调用失败: {e}")
            return {"corrected_text": text, "tags": []}

nlp_service = NLPEngine()