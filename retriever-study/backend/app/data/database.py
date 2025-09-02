import os
import json
import sqlite3
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid

DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # or "dynamodb"
DB_FILE = "retriever_study_local.db"

@dataclass
class User:
    userId: str
    name: str
    email: str
    courses: List[str]
    bio: str
    prefs: Dict[str, Any]
    embedding: Optional[List[float]] = None

@dataclass  
class Group:
    groupId: str
    courseCode: str
    title: str
    description: str
    tags: List[str]
    timePrefs: List[str]
    location: str
    ownerId: str
    members: List[str]
    embedding: Optional[List[float]] = None

@dataclass
class Message:
    messageId: str
    groupId: str
    senderId: str
    content: str
    createdAt: str
    toxicityScore: float

class Database:
    def __init__(self):
        self.db_type = DB_TYPE
        if self.db_type == "sqlite":
            self._init_sqlite()
    
    def _init_sqlite(self):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            userId TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            courses TEXT,
            bio TEXT,
            prefs TEXT,
            embedding TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            groupId TEXT PRIMARY KEY,
            courseCode TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            timePrefs TEXT,
            location TEXT,
            ownerId TEXT NOT NULL,
            members TEXT,
            embedding TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            messageId TEXT PRIMARY KEY,
            groupId TEXT NOT NULL,
            senderId TEXT NOT NULL,
            content TEXT NOT NULL,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            toxicityScore REAL
        );
        """)

        conn.commit()
        conn.close()

    def _get_connection(self):
        if self.db_type == "sqlite":
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            import boto3
            return boto3.resource('dynamodb')

    # User operations
    def create_user(self, user: User) -> User:
        if self.db_type == "sqlite":
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (userId, name, email, courses, bio, prefs, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user.userId,
                user.name,
                user.email,
                json.dumps(user.courses),
                user.bio,
                json.dumps(user.prefs),
                json.dumps(user.embedding) if user.embedding else None
            ))
            conn.commit()
            conn.close()
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        if self.db_type == "sqlite":
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE userId = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return User(
                    userId=row['userId'],
                    name=row['name'],
                    email=row['email'],
                    courses=json.loads(row['courses']) if row['courses'] else [],
                    bio=row['bio'] or "",
                    prefs=json.loads(row['prefs']) if row['prefs'] else {},
                    embedding=json.loads(row['embedding']) if row['embedding'] else None
                )
        return None

    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Optional[User]:
        if self.db_type == "sqlite":
            conn = self._get_connection()
            cursor = conn.cursor()
            
            set_clauses = []
            values = []
            for key, value in updates.items():
                if key in ['courses', 'prefs', 'embedding']:
                    values.append(json.dumps(value))
                else:
                    values.append(value)
                set_clauses.append(f"{key} = ?")
            
            values.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE userId = ?", values)
            conn.commit()
            conn.close()
            
            return self.get_user(user_id)
        return None

    # Group operations  
    def create_group(self, group: Group) -> Group:
        if self.db_type == "sqlite":
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO groups (groupId, courseCode, title, description, tags, timePrefs, location, ownerId, members, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                group.groupId,
                group.courseCode,
                group.title,
                group.description,
                json.dumps(group.tags),
                json.dumps(group.timePrefs),
                group.location,
                group.ownerId,
                json.dumps(group.members),
                json.dumps(group.embedding) if group.embedding else None
            ))
            conn.commit()
            conn.close()
        return group

    def get_group(self, group_id: str) -> Optional[Group]:
        if self.db_type == "sqlite":
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM groups WHERE groupId = ?", (group_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return Group(
                    groupId=row['groupId'],
                    courseCode=row['courseCode'],
                    title=row['title'],
                    description=row['description'] or "",
                    tags=json.loads(row['tags']) if row['tags'] else [],
                    timePrefs=json.loads(row['timePrefs']) if row['timePrefs'] else [],
                    location=row['location'] or "",
                    ownerId=row['ownerId'],
                    members=json.loads(row['members']) if row['members'] else [],
                    embedding=json.loads(row['embedding']) if row['embedding'] else None
                )
        return None

    def get_groups_by_course(self, course_code: str) -> List[Group]:
        groups = []
        if self.db_type == "sqlite":
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM groups WHERE courseCode = ?", (course_code,))
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                groups.append(Group(
                    groupId=row['groupId'],
                    courseCode=row['courseCode'],
                    title=row['title'],
                    description=row['description'] or "",
                    tags=json.loads(row['tags']) if row['tags'] else [],
                    timePrefs=json.loads(row['timePrefs']) if row['timePrefs'] else [],
                    location=row['location'] or "",
                    ownerId=row['ownerId'],
                    members=json.loads(row['members']) if row['members'] else [],
                    embedding=json.loads(row['embedding']) if row['embedding'] else None
                ))
        return groups

    def get_all_groups(self) -> List[Group]:
        groups = []
        if self.db_type == "sqlite":
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM groups")
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                groups.append(Group(
                    groupId=row['groupId'],
                    courseCode=row['courseCode'],
                    title=row['title'],
                    description=row['description'] or "",
                    tags=json.loads(row['tags']) if row['tags'] else [],
                    timePrefs=json.loads(row['timePrefs']) if row['timePrefs'] else [],
                    location=row['location'] or "",
                    ownerId=row['ownerId'],
                    members=json.loads(row['members']) if row['members'] else [],
                    embedding=json.loads(row['embedding']) if row['embedding'] else None
                ))
        return groups

    def join_group(self, group_id: str, user_id: str) -> Optional[Group]:
        group = self.get_group(group_id)
        if group and user_id not in group.members:
            group.members.append(user_id)
            if self.db_type == "sqlite":
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE groups SET members = ? WHERE groupId = ?", 
                             (json.dumps(group.members), group_id))
                conn.commit()
                conn.close()
        return group

    # Message operations
    def create_message(self, message: Message) -> Message:
        if self.db_type == "sqlite":
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (messageId, groupId, senderId, content, createdAt, toxicityScore)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                message.messageId,
                message.groupId,
                message.senderId,
                message.content,
                message.createdAt,
                message.toxicityScore
            ))
            conn.commit()
            conn.close()
        return message

    def get_messages(self, group_id: str, limit: int = 50) -> List[Message]:
        messages = []
        if self.db_type == "sqlite":
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages WHERE groupId = ? 
                ORDER BY createdAt DESC LIMIT ?
            """, (group_id, limit))
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                messages.append(Message(
                    messageId=row['messageId'],
                    groupId=row['groupId'],
                    senderId=row['senderId'],
                    content=row['content'],
                    createdAt=row['createdAt'],
                    toxicityScore=row['toxicityScore'] or 0.0
                ))
        return messages

# Global database instance
db = Database()