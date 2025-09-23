from typing import Optional, Any, Dict, List, Generator
from fastapi import Depends
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, func, ForeignKey, Table, select, delete
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship
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
    expires_at = Column(DateTime, nullable=True)
    department = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)
    meeting_type = Column(String, nullable=True)
    time_slot = Column(String, nullable=True)
    study_style = Column(JSON, nullable=True)
    group_size = Column(String, nullable=True)
    
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
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/retriever_study")

# Create sync engine
engine = create_engine(DATABASE_URL, echo=True)

# Create sync session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Repository instances with actual database operations
class UserRepository:
    """User repository for database operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.google_id == google_id).first()

    def create_user(self, user_data: Dict[str, Any]) -> User:
        db_user = User(**user_data)
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def update_user(self, user_id: int, user_data: Dict[str, Any]) -> Optional[User]:
        user = self.get_user(user_id)
        if not user:
            return None
            
        for key, value in user_data.items():
            setattr(user, key, value)
            
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_or_update_oauth_user(self, google_id: str, name: str, email: str, picture_url: str) -> User:
        user = self.get_user_by_google_id(google_id)
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
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_last_login(self, user_id: int) -> None:
        user = self.get_user(user_id)
        if user:
            user.last_login = datetime.utcnow()
            self.db.commit()

class GroupRepository:
    """Group repository for database operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_group(self, group_id: int) -> Optional[Group]:
        return self.db.query(Group).filter(Group.id == group_id).first()
    
    def create_group(self, group_data: Dict[str, Any], owner_id: int) -> Group:
        db_group = Group(**group_data, owner_id=owner_id)
        self.db.add(db_group)
        self.db.commit()
        self.db.refresh(db_group)
        return db_group
    
    def add_member(self, group_id: int, user_id: int) -> Optional[Group]:
        # Check if user is already a member
        member = self.db.query(GroupMember).filter(GroupMember.group_id == group_id, GroupMember.user_id == user_id).first()
        if member:
            return self.get_group(group_id)  # Already a member, return the group
            
        # Add as member
        member = GroupMember(group_id=group_id, user_id=user_id)
        self.db.add(member)
        self.db.commit()
        return self.get_group(group_id)
    
    def remove_member(self, group_id: int, user_id: int) -> bool:
        result = self.db.execute(
            delete(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id
            )
        )
        self.db.commit()
        return result.rowcount > 0

    def get_all_groups(self, limit: int = 20, offset: int = 0) -> List[Group]:
        return self.db.query(Group).offset(offset).limit(limit).all()

    def get_groups_for_member(self, user_id: int) -> List[Group]:
        return self.db.query(Group).join(GroupMember).filter(GroupMember.user_id == user_id).all()

class MessageRepository:
    """Message repository for database operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_messages(self, group_id: int, limit: int = 100) -> List[Message]:
        return self.db.query(Message).filter(Message.group_id == group_id).order_by(Message.created_at.desc()).limit(limit).all()
    
    def create_message(self, content: str, group_id: int, sender_id: int) -> Message:
        message = Message(
            content=content,
            group_id=group_id,
            sender_id=sender_id
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency to get repositories
def get_repositories(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {
        "user_repo": UserRepository(db),
        "group_repo": GroupRepository(db),
        "message_repo": MessageRepository(db)
    }

def initialize_database(database_url: str = None) -> None:
    """Initialize the database connection and create tables."""
    global engine, SessionLocal
    
    if database_url:
        engine = create_engine(database_url, echo=True)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
        
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def close_database() -> None:
    """Close the database connection."""
    engine.dispose()

# For backward compatibility
db = engine
