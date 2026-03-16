import logging
from sqlalchemy.orm import Session
from app.models.user import User
from app.utils.security import get_password_hash

logger = logging.getLogger(__name__)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def create_default_admin(db: Session) -> None:
    """
    如果 admin 账号不存在则自动创建。
    幂等操作——重启容器不会重复创建或覆盖已修改的密码。
    """
    existing = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if existing:
        logger.info(f"Admin account '{ADMIN_USERNAME}' already exists, skipping.")
        return

    admin = User(
        username=ADMIN_USERNAME,
        hashed_password=get_password_hash(ADMIN_PASSWORD),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    logger.info(f"Default admin account '{ADMIN_USERNAME}' created successfully.")