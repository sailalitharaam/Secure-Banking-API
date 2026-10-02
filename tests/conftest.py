import asyncio
import os
import uuid
from decimal import Decimal
from typing import AsyncGenerator, Dict
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "False"
os.environ["STREAMING_BROKER_TYPE"] = "mock"

from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account, AccountType, KYCStatus
from app.models.user import User, UserRole

# Disable rate limiter for testing suite
limiter.enabled = False

# Use in-memory SQLite for high-speed isolated tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session per test function."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test HTTP client with overridden database dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def customer_user(db_session: AsyncSession) -> User:
    """Create and return a default Customer user."""
    user = User(
        UserID=uuid.uuid4(),
        Email="customer@example.com",
        PasswordHash=get_password_hash("Password123!"),
        Role=UserRole.CUSTOMER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create and return a Bank Admin user."""
    user = User(
        UserID=uuid.uuid4(),
        Email="admin@securebank.com",
        PasswordHash=get_password_hash("AdminPass123!"),
        Role=UserRole.BANK_ADMIN,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def customer_headers(customer_user: User) -> Dict[str, str]:
    """Return Authorization headers for Customer."""
    token = create_access_token(subject=customer_user.UserID, role=customer_user.Role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user: User) -> Dict[str, str]:
    """Return Authorization headers for Bank Admin."""
    token = create_access_token(subject=admin_user.UserID, role=admin_user.Role.value)
    return {"Authorization": f"Bearer {token}"}
