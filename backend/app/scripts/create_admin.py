import argparse
import os

from app.core.database import SessionLocal
from app.core.security import get_password_hash, normalize_phone, validate_password_strength, utcnow
from app.models.user import User, UserRole, UserStatus


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update the bootstrap super admin user.")
    parser.add_argument("--phone", default=os.getenv("ADMIN_PHONE"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument("--display-name", default=os.getenv("ADMIN_DISPLAY_NAME", "Super Admin"))
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL"))
    args = parser.parse_args()

    if not args.phone:
        raise SystemExit("Missing admin phone. Use --phone or set ADMIN_PHONE.")
    if not args.password:
        raise SystemExit("Missing admin password. Use --password or set ADMIN_PASSWORD.")

    normalized_phone = normalize_phone(args.phone)
    validate_password_strength(args.password, phone=normalized_phone, display_name=args.display_name)

    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter((User.phone == normalized_phone) | (User.username == normalized_phone))
            .first()
        )
        now = utcnow()
        if user:
            user.username = normalized_phone
            user.phone = normalized_phone
            user.display_name = args.display_name.strip()
            user.role = UserRole.SUPER_ADMIN.value
            user.status = UserStatus.ACTIVE.value
            user.must_change_password = False
            user.hashed_password = get_password_hash(args.password)
            user.password_changed_at = now
            if args.email:
                user.email = args.email
            db.commit()
            print(f"Updated super admin user: {normalized_phone}")
            return

        user = User(
            username=normalized_phone,
            phone=normalized_phone,
            display_name=args.display_name.strip(),
            email=args.email,
            role=UserRole.SUPER_ADMIN.value,
            status=UserStatus.ACTIVE.value,
            must_change_password=False,
            hashed_password=get_password_hash(args.password),
            password_changed_at=now,
        )
        db.add(user)
        db.commit()
        print(f"Created super admin user: {normalized_phone}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
