import os
import sys

from app.core.database import SessionLocal
import app.models.item as models
from app.services.auth import get_password_hash


def create_superuser():
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        if os.getenv("APP_ENV", "dev") == "production":
            print("ADMIN_PASSWORD must be set when APP_ENV=production")
            sys.exit(1)
        password = "admin123"
        print("WARNING: ADMIN_PASSWORD not set, using the insecure dev default.")

    db = SessionLocal()
    try:
        # Check if an admin already exists to prevent duplicates
        existing_admin = db.query(models.Admin).filter(models.Admin.username == username).first()
        if existing_admin:
            print("Admin user already exists!")
            return

        # Hash the password and create the user
        new_admin = models.Admin(username=username, hashed_password=get_password_hash(password))

        db.add(new_admin)
        db.commit()
        print(f"Success! Admin user '{username}' created.")

    except Exception as e:
        print(f"Error creating admin: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_superuser()
