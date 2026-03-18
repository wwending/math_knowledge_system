import json

from loguru import logger
from openai import OpenAI

from app.core.config import settings


class NLPEngine:
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL
        self.client = None

    def initialize(self):
        if self.api_key and self.base_url:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                logger.success("DeepSeek client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize DeepSeek client: {e}")
        else:
            logger.warning("DeepSeek credentials are not configured")

    def analyze(self, text: str):
        if not text or not self.client:
            return {"corrected_text": text, "tags": []}

        logger.info("Calling DeepSeek analysis")

        system_prompt = """
You are a math formatting assistant. Clean OCR output, normalize Markdown and LaTeX,
and extract 1-3 knowledge tags. Return strict JSON with corrected_text and tags.
"""

        user_prompt = f"Process this OCR text and return JSON only:\n\n{text}"

        try:
            response = self.client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000,
            )

            result_content = response.choices[0].message.content
            logger.debug(f"DeepSeek response: {result_content}")

            try:
                data = json.loads(result_content)
                return {
                    "corrected_text": data.get("corrected_text", text),
                    "tags": data.get("tags", []),
                }
            except json.JSONDecodeError:
                logger.warning("DeepSeek returned non-JSON content")
                return {"corrected_text": result_content, "tags": []}

        except Exception as e:
            logger.error(f"DeepSeek call failed: {e}")
            return {"corrected_text": text, "tags": []}


nlp_service = NLPEngine()
