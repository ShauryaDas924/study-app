import os
import logging
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL missing in .env")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,

    # IMPORTANT:
    # Hosted Postgres poolers often have low session-client limits.
    # NullPool prevents SQLAlchemy from holding many open DB connections.
    poolclass=NullPool,
    pool_pre_ping=True,

    connect_args={
        "timeout": 20,
        "server_settings": {
            "statement_timeout": "180000",
        }
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
    class_=AsyncSession,
)

Base = declarative_base()

async def get_db():
    session = AsyncSessionLocal()

    try:
        yield session

    except Exception:
        try:
            await session.rollback()
        except Exception as exc:
            logger.warning("db_request_rollback_failed error_type=%s", type(exc).__name__)
        raise

    finally:
        try:
            if session.in_transaction():
                await session.rollback()
        except Exception as exc:
            logger.warning("db_session_rollback_failed error_type=%s", type(exc).__name__)

        try:
            await session.close()
        except Exception as exc:
            # Prevent stale/closed DB connections from turning successful requests into 500s.
            logger.warning("db_session_close_failed error_type=%s", type(exc).__name__)
