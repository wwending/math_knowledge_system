import os
import json
import re
from loguru import logger
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class NLPEngine:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL")
        self.client = None

    def initialize(self):
        if self.api_key and self.base_url:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                logger.success("✅ DeepSeek LLM 客户端初始化成功")
            except Exception as e:
                logger.error(f"❌ DeepSeek 初始化失败: {e}")
        else:
            logger.warning("⚠️ 未配置 DeepSeek API Key，智能清洗将不可用")

    def analyze(self, text: str):
        """
        输入：百度 OCR 的原始文本 (裸露 LaTeX，无排版)
        输出：{"corrected_text": "标准Markdown+Latex", "tags": ["知识点"]}
        """
        if not text or not self.client:
            return {"corrected_text": text, "tags": []}

        logger.info("正在请求 DeepSeek 进行智能清洗...")

        # --- 核心提示词 (Prompt Engineering) ---
        system_prompt = """
你是一个高中数学排版专家和知识点分类助手。
你的任务是处理OCR识别出的原始数学题目文本，输出标准的 Markdown + LaTeX 格式。

要求如下：
1. **LaTeX 规范**：
   - 将所有数学公式用 `$` (行内) 或 `$$` (独立行) 包裹。
   - 修复 OCR 常见的断裂分数（如 "1" 换行 "16" 换行 "3" -> `\\frac{16}{3}`）。
   - 修复 OCR 错误（如 `x_2` -> `x^2`, `\\sqrt` 后面漏掉参数等）。
   - 保持 `\\frac`, `\\sqrt`, `\\sin` 等标准命令。
   - 向量请使用 `\\vec{a}` 或 `\\mathbf{a}`。

2. **排版规范**：
   - 题号（如 "1."）需要加粗，例如 `**1.**`。
   - 关键词（如 "解："、"证明："、"已知"）前换行并加粗，例如 `\n\n**解：**`。
   - 选项 A, B, C, D 需要换行并加粗。

3. **知识点标签**：
   - 根据题目内容，推断 1-3 个高中数学知识点（如 "导数", "圆锥曲线", "三角函数"）。

4. **输出格式**：
   - 必须只返回一个合法的 JSON 对象。
   - 格式：`{"corrected_text": "...", "tags": ["tag1", "tag2"]}`
"""

        user_prompt = f"请处理以下 OCR 原始文本：\n\n{text}"

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat", # 或者 deepseek-v3
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={ "type": "json_object" }, # 强制 JSON 模式
                temperature=0.1 # 低温度，保证输出稳定
            )

            result_content = response.choices[0].message.content
            logger.debug(f"DeepSeek 原始响应: {result_content}")

            # 解析 JSON
            data = json.loads(result_content)
            
            return {
                "corrected_text": data.get("corrected_text", text),
                "tags": data.get("tags", [])
            }

        except Exception as e:
            logger.error(f"DeepSeek 调用失败: {e}")
            # 降级处理：如果 API 挂了，返回原文本
            return {"corrected_text": text, "tags": []}

nlp_service = NLPEngine()