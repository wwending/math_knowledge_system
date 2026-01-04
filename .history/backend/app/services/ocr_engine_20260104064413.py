import os
import requests
import base64
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class OCREngine:
    def __init__(self):
        self.api_key = os.getenv("BAIDU_API_KEY")
        self.secret_key = os.getenv("BAIDU_SECRET_KEY")
        self.access_token = None

    def _get_access_token(self):
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        try:
            resp = requests.post(url, params=params).json()
            self.access_token = resp.get("access_token")
        except Exception as e:
            logger.error(f"百度 Token 获取失败: {e}")

    def ocr_image(self, image_bytes: bytes) -> str:
        if not self.api_key:
            return "OCR API KEY 未配置"
            
        if not self.access_token:
            self._get_access_token()

        request_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        params = {"access_token": self.access_token}
        data = {"image": img_b64}
        headers = {'content-type': 'application/x-www-form-urlencoded'}

        try:
            resp = requests.post(request_url, data=data, params=params, headers=headers)
            result = resp.json()
            if "words_result" in result:
                return "\n".join([w["words"] for w in result["words_result"]])
            return f"识别错误: {result.get('error_msg')}"
        except Exception as e:
            return f"请求异常: {e}"

# ==========================================
# 关键：这里定义变量名为 ocr_engine
# ==========================================
ocr_engine = OCREngine()