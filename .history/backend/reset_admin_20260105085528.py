import sys
import os

# 1. 这一步是为了让 Python 能找到 app 文件夹
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.user import User
# 如果你用了 passlib 进行密码加密，需要引入 context
# 如果你之前没配加密，直接存明文，这里可能要改。
# 这里假设你使用了标准的 passlib.context
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    def get_password_hash(password):
        return pwd_context.hash(password)
except ImportError:
    # 如果没装 passlib，就先用明文 (仅限紧急修复)
    print("⚠️ 未找到 passlib，将使用明文密码")
    def get_password_hash(password):
        return password

def reset_admin():
    db = SessionLocal()
    try:
        # 检查是否已有 admin
        user = db.query(User).filter(User.username == "admin").first()
        if user:
            print("✅ 管理员用户 (admin) 已存在，无需创建。")
            # 也可以在这里强制重置密码
            # user.hashed_password = get_password_hash("123456")
            # db.commit()
            return

        # 创建新管理员
        print("🛠️ 正在创建管理员用户...")
        new_user = User(
            username="admin",
            email="admin@example.com",
            # 注意：这里要看你的数据库模型叫 hashed_password 还是 password
            hashed_password=get_password_hash("123456"), 
            is_active=True,
            role="admin" # 如果你的模型有 role 字段
        )
        
        db.add(new_user)
        db.commit()
        print("🎉 恢复成功！")
        print("账号: admin")
        print("密码: 123456")
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        # 打印一下 User 模型的字段，方便排查
        print("提示：请检查 app/models/user.py 里的字段名是否匹配")
    finally:
        db.close()

if __name__ == "__main__":
    reset_admin()