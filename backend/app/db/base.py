from sqlalchemy.orm import declarative_base

# 创建基类，所有的 Model (User, Question) 都要继承它
Base = declarative_base()