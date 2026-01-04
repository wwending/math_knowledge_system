# test_deepseek.py (放在 backend 根目录)
import asyncio
from app.services.nlp_engine import correct_text

text = "y y ^ { 2 } = 4 x" # 测试文本
print("开始测试...")
result = asyncio.run(correct_text(text))
print("测试结果:", result)