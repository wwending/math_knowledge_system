import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 项目基础信息
    PROJECT_NAME: str = "Math Knowledge System"
    API_V1_STR: str = "/api/v1"
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./math_knowledge.db"
    
    # JWT 安全配置
    SECRET_KEY: str = "CHANGE_THIS_TO_A_SECURE_RANDOM_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    
    # 📂 文件上传配置
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "static", "uploads")
    
    # ==========================================
    # 第三方 API 配置 (补全了缺失的字段)
    # ==========================================
    BAIDU_API_KEY: str = ""
    BAIDU_SECRET_KEY: str = ""
    
    DEEPSEEK_API_KEY: str = ""
    # 👇 刚才报错就是因为缺了这两行，现在补上
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    class Config:
        env_file = ".env"
        case_sensitive = True
        # 👇 关键！告诉 Pydantic：如果 .env 里有多余的变量，直接忽略，不要报错
        extra = "ignore"

# 实例化
settings = Settings()

# 自动创建目录
if not os.path.exists(settings.UPLOAD_DIR):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)