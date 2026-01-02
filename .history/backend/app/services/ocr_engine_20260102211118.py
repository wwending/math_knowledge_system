import requests
import base64
import os
from loguru import logger
from dotenv import load_dotenv # <--- 引入这个

# 1. 加载 .env 文件里的变量
load_dotenv()

class OCREngine:
    def __init__(self):
        # 2. 从环境变量中读取，而不是写死
        self.API_KEY = os.getenv("BAIDU_API_KEY")
        self.SECRET_KEY = os.getenv("BAIDU_SECRET_KEY")

        # 增加一个检查，防止忘记配置
        if not self.API_KEY or not self.SECRET_KEY:
            logger.critical("❌ 未找到百度 API Key！请检查 .env 文件是否配置正确。")
        
        self.access_token = None
        
        # 百度公式识别 API 地址
        self.OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/formula"
        self.TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"

    def initialize(self):
        """
        对于 API 模式，初始化主要是获取 Access Token
        """
        logger.info("正在连接百度 OCR API...")
        try:
            self.access_token = self.fetch_token()
            logger.success(f"百度 OCR 连接成功! Token: {self.access_token[:10]}...")
        except Exception as e:
            logger.error(f"无法连接百度 OCR: {e}")

    def fetch_token(self):
        """
        获取鉴权 Token
        """
        params = {
            "grant_type": "client_credentials",
            "client_id": self.API_KEY,
            "client_secret": self.SECRET_KEY
        }
        response = requests.post(self.TOKEN_URL, params=params)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            raise Exception(f"获取 Token 失败: {response.text}")

    def recognize(self, image_path: str):
        """
        读取本地图片 -> Base64 -> 发送给百度 -> 解析结果
        """
        if not self.access_token:
            self.access_token = self.fetch_token()

        try:
            # 1. 读取图片并转为 Base64
            with open(image_path, "rb") as f:
                img_data = f.read()
                b64_img = base64.b64encode(img_data).decode()

            # 2. 构造请求
            request_url = f"{self.OCR_URL}?access_token={self.access_token}"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            # 百度公式识别参数
            # image: 图像数据
            # recognize_granularity: small (小粒度，适合字符) / big (大粒度，适合行) - 推荐 small
            # detect_direction: true (检测朝向)
            data = {
                "image": b64_img,
                "detect_direction": "true",
                "recognize_granularity": "big" 
            }

            # 3. 发送请求
            logger.info(f"正在请求百度 OCR: {image_path}")
            response = requests.post(request_url, data=data, headers=headers)
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}", "content": ""}

            result_json = response.json()
            
            # 4. 解析结果
            if "error_code" in result_json:
                error_msg = result_json.get("error_msg")
                # 如果 Token 过期，重试一次
                if result_json.get("error_code") in [110, 111]:
                    logger.warning("Token 过期，刷新中...")
                    self.access_token = self.fetch_token()
                    return self.recognize(image_path) # 递归重试
                
                return {"success": False, "error": error_msg, "content": ""}

            # 5. 提取文字结果
            # 百度返回的是 words_result 列表
            words_result = result_json.get("words_result", [])
            
            # 拼接每一行的识别结果
            lines = []
            for item in words_result:
                # words 字段里通常就是 LaTeX 格式的内容
                lines.append(item.get("words", ""))
            
            final_content = "\n\n".join(lines)
            
            logger.success("百度 OCR 识别成功")
            return {
                "success": True, 
                "content": final_content, 
                "cost_seconds": 0.5 # API 响应很快
            }

        except Exception as e:
            logger.error(f"OCR 识别异常: {e}")
            return {"success": False, "error": str(e), "content": ""}

# 单例模式
ocr_service = OCREngine()