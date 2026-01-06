import json
import time
import re
from openai import OpenAI
from app.core.config import settings

class NLPService:
    def __init__(self):
        # 打印配置信息，确保读到了 Key
        print(f"🔧 初始化 NLP 服务...")
        print(f"   - Base URL: {settings.DEEPSEEK_BASE_URL}")
        print(f"   - Model: {settings.DEEPSEEK_MODEL}")
        print(f"   - API Key: {settings.DEEPSEEK_API_KEY[:5]}*** (Len: {len(settings.DEEPSEEK_API_KEY)})")
        
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )

    def analyze(self, text: str):
        """
        发送 OCR 文本给 DeepSeek，要求返回 JSON 格式的清洗文本和标签
        """
        if not text:
            return {"corrected_text": "", "tags": []}

        start_time = time.time()
        print(f"🚀 [DeepSeek] 开始请求 API，文本长度: {len(text)}")

        prompt = f"""
        你是一个高中数学助教。请对以下OCR识别的数学题目文本进行处理：
        1. 修正OCR错误（如将 'ln' 误识别为 '1n'，'e^x' 格式错误等）。
        2. 将数学公式转换为标准的 LaTeX 格式（使用 $...$ 包裹行内公式,复杂的方程组、联立公式、分段函数必须使用双美元符号 $$...$$ 包裹（如 $$ \\begin{{cases}} ... \\end{{cases}} $$）。）。
        3. 提取3-5个关键知识点标签。
        4.保持题目原意不变。

        原始文本：
        {text}

        请务必只返回纯 JSON 格式，不要包含 ```json 代码块标记，格式如下：
        {{
            "corrected_text": "修复后的完整文本(包含LaTeX)",
            "tags": ["标签1", "标签2"]
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的数学助教，擅长处理 LaTeX 公式，严格遵循 JSON 格式输出的数学助手。"},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.1, # 低温度保证格式稳定
                max_tokens=2000
            )

            raw_content = response.choices[0].message.content.strip()
            print(f"📩 [DeepSeek] 收到响应 (耗时 {time.time() - start_time:.2f}s): {raw_content[:100]}...")

            # 清理可能的 Markdown 标记
            clean_json = raw_content.replace("```json", "").replace("```", "").strip()
            
            # 解析 JSON
            result = json.loads(clean_json)
            
            # 确保字段存在
            if "corrected_text" not in result:
                result["corrected_text"] = text # 降级处理
            if "tags" not in result:
                result["tags"] = []
                
            return result

        except Exception as e:
            print(f"❌ [DeepSeek Error] 调用失败: {e}")
            # 失败时返回原始内容，避免程序崩溃
            return {
                "corrected_text": text,
                "tags": ["AI分析失败"] 
            }

# 单例模式
nlp_service = NLPService()