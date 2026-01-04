import os
import requests
import base64
import logging
from dotenv import load_dotenv

# 加载 .env
load_dotenv()

logger = logging.getLogger(__name__)

class OCREngine:
    def __init__(self):
        # 百度 API Key 和 Secret Key (去百度云控制台看)
        self.api_key = os.getenv("BAIDU_API_KEY")
        self.secret_key = os.getenv("BAIDU_SECRET_KEY")
        self.access_token = None
        
        if not self.api_key or not self.secret_key:
            logger.warning("⚠️ 未配置 BAIDU_API_KEY 或 BAIDU_SECRET_KEY，OCR 将无法工作")

    def _get_access_token(self) -> str:
        """
        获取百度的 Access Token (鉴权)
        """
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        
        try:
            response = requests.post(url, params=params, timeout=5)
            data = response.json()
            if "access_token" in data:
                self.access_token = data["access_token"]
                return self.access_token
            else:
                logger.error(f"❌ 获取百度 Token 失败: {data}")
                return None
        except Exception as e:
            logger.error(f"❌ 连接百度鉴权接口失败: {e}")
            return None

    def ocr_image(self, image_bytes: bytes) -> str:
        """
        接收图片字节流 -> Base64编码 -> 发送 HTTP 请求 -> 返回文字
        """
        # 1. 确保有 Token
        if not self.access_token:
            if not self._get_access_token():
                return "OCR 鉴权失败，检查 API Key 配置"

        # 2. 图片 Base64 编码
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')

        # 3. 构造请求
        # 使用通用文字识别（标准版）接口
        request_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
        
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        params = {"access_token": self.access_token}
        data = {"image": img_b64}

        try:
            logger.info("📤 发送 OCR 请求到百度 API...")
            response = requests.post(request_url, data=data, params=params, headers=headers, timeout=10)
            result = response.json()

            # 4. 解析结果
            if "words_result" in result:
                # 提取所有行并拼接
                text_lines = [item["words"] for item in result["words_result"]]
                full_text = "\n".join(text_lines)
                logger.info("✅ OCR 识别成功")
                return full_text
            else:
                error_msg = result.get("error_msg", "未知错误")
                logger.error(f"❌ 百度 OCR 返回错误: {error_msg}")
                # 如果 Token 过期，这里可以加逻辑重试，暂时先直接返回错误
                return f"识别错误: {error_msg}"

        except Exception as e:
            logger.error(f"❌ OCR 请求异常: {e}")
            return f"请求异常: {str(e)}"

# =========================================================
# 实例化并导出变量，供 endpoints.py 使用
# =========================================================
ocr_engine = OCREngine()