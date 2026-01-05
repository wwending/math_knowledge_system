import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 项目基础信息
    PROJECT_NAME: str = "Math Knowledge System"
    API_V1_STR: str = "/api/v1"
    
    # 数据库配置 (默认 SQLite)
    DATABASE_URL: str = "sqlite:///./math_knowledge.db"
    
    # JWT 安全配置
    SECRET_KEY: str = "CHANGE_THIS_TO_A_SECURE_RANDOM_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8天过期
    
    # 📂 文件上传配置 (关键！之前的报错是因为找不到这个)
    # 自动获取当前 backend 目录下的 static/uploads
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "static", "uploads")
    
    # 第三方 API (从 .env 读取)
    BAIDU_API_KEY: str = ""
    BAIDU_SECRET_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

# 🔥🔥🔥 这一步最关键！实例化并导出对象 🔥🔥🔥
settings = Settings()

# 自动创建上传目录，防止报错
if not os.path.exists(settings.UPLOAD_DIR):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)