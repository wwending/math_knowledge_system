import os
import argparse

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User

def main():
    parser = argparse.ArgumentParser(description="Create or update an admin user.")
    parser.add_argument("--username", default=os.getenv("ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL"))
    args = parser.parse_args()

    if not args.password:
        raise SystemExit("❌ Missing admin password. Use --password or set ADMIN_PASSWORD in environment.")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()
        if user:
            # 更新为管理员 + 重置密码（更安全：你可以按需改成只在 role!=admin 才更新）
            user.role = "admin"
            user.is_active = True
            user.hashed_password = get_password_hash(args.password)
            if args.email:
                user.email = args.email
            db.commit()
            print(f"✅ Updated admin user: {args.username}")
            return

        user = User(
            username=args.username,
            email=args.email,
            role="admin",
            is_active=True,
            hashed_password=get_password_hash(args.password),
        )
        db.add(user)
        db.commit()
        print(f"✅ Created admin user: {args.username}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
