import os
import json
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
logger = logging.getLogger(__name__)

class LLMEngine:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com"
        self.model = "deepseek-chat"
        
        if not self.api_key:
            logger.warning("⚠️ DEEPSEEK_API_KEY 未配置！")

        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _get_system_prompt(self) -> str:
        return """
你是一位资深的高中数学教育专家和 LaTeX 排版工程师。
请处理OCR文本：
1. 修复语义和公式错误。
2. 使用 $...$ 和 $$...$$ 包裹公式。
3. 提取知识点。
4. 仅返回 JSON：{"corrected_text": "...", "tags": ["..."]}
"""

    async def analyze(self, raw_text: str) -> Dict[str, Any]:
        if not raw_text or not raw_text.strip():
            return {"corrected_text": "", "tags": []}

        if not self.api_key:
            return {"corrected_text": raw_text, "tags": ["API_KEY_MISSING"]}

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": f"原始 OCR 文本：\n{raw_text}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            result = response.choices[0].message.content
            data = json.loads(result)
            return {
                "corrected_text": data.get("corrected_text", raw_text),
                "tags": data.get("tags", [])
            }
        except Exception as e:
            logger.error(f"DeepSeek Error: {e}")
            return {"corrected_text": raw_text, "tags": ["API_ERROR"]}

# =================================================================
# 👇👇👇 这里的代码非常关键！必须要顶格写，不能有缩进！ 👇👇👇
# =================================================================
nlp_engine = LLMEngine()