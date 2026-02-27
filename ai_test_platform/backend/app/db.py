from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .core.config import settings


class Base(DeclarativeBase):
    pass


DATABASE_URL = settings.database_url
_connect_args = {} if "sqlite" not in DATABASE_URL else {"check_same_thread": False}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    from sqlalchemy.orm import Session

    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

