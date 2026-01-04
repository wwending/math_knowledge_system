import os
from openai import AsyncOpenAI
from dotenv import load_dotenv  # <--- 1. 导入这个库

# 2. 加载 .env 文件
# 这行代码会自动寻找当前目录或父目录下的 .env 文件并将变量注入到环境变量中
load_dotenv() 

# 3. 从环境变量获取 Key
API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 4. 初始化客户端
client = None
if API_KEY:
    try:
        client = AsyncOpenAI(
            api_key=API_KEY,
            base_url="https://api.deepseek.com"
        )
    except Exception as e:
        print(f"❌ NLP引擎初始化失败: {e}")
else:
    print("❌ 警告: 未在 .env 文件中找到 DEEPSEEK_API_KEY")

# 3. 定义核心函数 (这就是 test_deepseek.py 要找的那个函数)
async def correct_text(text: str) -> str:
    """
    使用 DeepSeek 修正 OCR 识别出来的数学公式文本
    """
    if not client:
        print("⚠️ DeepSeek 客户端未初始化 (缺少 API Key)，直接返回原文本")
        return text

    print(f"🔄 正在请求 DeepSeek 修正文本 (长度: {len(text)})...")
    
    try:
        response = await client.chat.completions.create(
            model="deepseek-chat", # 或者 deepseek-coder，视官方文档而定
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "你是一个专业的数学公式OCR修正助手。"
                        "用户的输入是OCR识别出的原始LaTeX文本，其中包含乱码和错误。"
                        "请修正数学逻辑错误和LaTeX语法错误。"
                        "注意：只返回修正后的纯文本，不要包含任何Markdown格式（如 ```latex ... ```），也不要包含解释性文字。"
                    )
                },
                {"role": "user", "content": text}
            ],
            stream=False
        )
        
        # 获取结果
        corrected_content = response.choices[0].message.content.strip()
        
        # 简单的清洗：有时候大模型还是会忍不住加 ```
        corrected_content = corrected_content.replace("```latex", "").replace("```", "").strip()
        
        print("✅ DeepSeek 修正成功!")
        return corrected_content

    except Exception as e:
        print(f"❌ DeepSeek 调用出错: {e}")
        # 出错时为了保证流程不中断，返回原始文本
        return text