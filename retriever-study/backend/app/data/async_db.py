from typing import Optional, Any, Dict, List, AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy import Column, Integer, String, JSON, DateTime, func, ForeignKey, Table, select, delete
from sqlalchemy.orm import relationship, sessionmaker
import os
from datetime import datetime

# SQLAlchemy models
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    google_id = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    name = Column(String, nullable=True)
    picture_url = Column(String, nullable=True)
    courses = Column(JSON, default=[])
    bio = Column(String, nullable=True)
    prefs = Column(JSON, default={"studyStyle": [], "timeSlots": [], "locations": []})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owned_groups = relationship("Group", back_populates="owner")
    messages = relationship("Message", back_populates="sender")
    group_members = relationship("GroupMember", back_populates="user")

class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    tags = Column(JSON, default=[])
    time_prefs = Column(JSON, default=[])
    location = Column(String, nullable=True)
    max_members = Column(Integer, default=4)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="owned_groups")
    members = relationship("GroupMember", back_populates="group")
    messages = relationship("Message", back_populates="group")

class GroupMember(Base):
    __tablename__ = "group_members"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="group_members")
    group = relationship("Group", back_populates="members")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    group = relationship("Group", back_populates="messages")
    sender = relationship("User", back_populates="messages")

# Database URL from environment or default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/retriever_study")

# Create async engine
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Repository instances with actual database operations
class UserRepository:
    """User repository for database operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(
            select(User).filter(User.id == user_id)
        )
        return result.scalars().first()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).filter(User.email == email)
        )
        return result.scalars().first()

    async def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).filter(User.google_id == google_id)
        )
        return result.scalars().first()

    async def create_user(self, user_data: Dict[str, Any]) -> User:
        db_user = User(**user_data)
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user
    
    async def update_user(self, user_id: int, user_data: Dict[str, Any]) -> Optional[User]:
        user = await self.get_user(user_id)
        if not user:
            return None
            
        for key, value in user_data.items():
            setattr(user, key, value)
            
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def create_or_update_oauth_user(self, google_id: str, name: str, email: str, picture_url: str) -> User:
        user = await self.get_user_by_google_id(google_id)
        if user:
            user.name = name
            user.email = email
            user.picture_url = picture_url
            user.updated_at = datetime.utcnow()
        else:
            user = User(
                google_id=google_id,
                name=name,
                email=email,
                picture_url=picture_url,
                hashed_password="", # Not used for OAuth
            )
            self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_last_login(self, user_id: int) -> None:
        user = await self.get_user(user_id)
        if user:
            user.last_login = datetime.utcnow()
            await self.db.commit()

class GroupRepository:
    """Group repository for database operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_group(self, group_id: int) -> Optional[Group]:
        result = await self.db.execute(
            select(Group).filter(Group.id == group_id)
        )
        return result.scalars().first()
    
    async def create_group(self, group_data: Dict[str, Any], owner_id: int) -> Group:
        db_group = Group(**group_data, owner_id=owner_id)
        self.db.add(db_group)
        await self.db.commit()
        await self.db.refresh(db_group)
        return db_group
    
    async def add_member(self, group_id: int, user_id: int) -> bool:
        # Check if user is already a member
        result = await self.db.execute(
            select(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id
            )
        )
        if result.scalars().first():
            return False  # Already a member
            
        # Add as member
        member = GroupMember(group_id=group_id, user_id=user_id)
        self.db.add(member)
        await self.db.commit()
        return True
    
    async def remove_member(self, group_id: int, user_id: int) -> bool:
        result = await self.db.execute(
            delete(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id
            )
        )
        await self.db.commit()
        return result.rowcount > 0

    async def get_all_groups(self, limit: int = 20, offset: int = 0) -> List[Group]:
        result = await self.db.execute(
            select(Group).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def get_groups_for_member(self, user_id: int) -> List[Group]:
        result = await self.db.execute(
            select(Group).join(GroupMember).filter(GroupMember.user_id == user_id)
        )
        return result.scalars().all()

class MessageRepository:
    """Message repository for database operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_messages(self, group_id: int, limit: int = 100) -> List[Message]:
        result = await self.db.execute(
            select(Message)
            .filter(Message.group_id == group_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create_message(self, content: str, group_id: int, sender_id: int) -> Message:
        message = Message(
            content=content,
            group_id=group_id,
            sender_id=sender_id
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

# Dependency to get repositories
def get_repositories(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    return {
        "user_repo": UserRepository(db),
        "group_repo": GroupRepository(db),
        "message_repo": MessageRepository(db)
    }

async def initialize_async_database(database_url: str = None) -> None:
    """Initialize the async database connection and create tables."""
    global engine, AsyncSessionLocal
    
    if database_url:
        engine = create_async_engine(database_url, echo=True, future=True)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )

async def close_async_database() -> None:
    """Close the database connection."""
    await engine.dispose()

# For backward compatibility
async_db = engine