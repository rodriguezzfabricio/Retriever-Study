import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional

DEFAULT_MAX_MEMBERS = 8
MAX_MEMBERS_MIN = 2
MAX_MEMBERS_MAX = 50


class GroupCapacityError(Exception):
    """Raised when attempting to add a member to a full group."""
    pass


class Database:
    """Manages all database operations for the local SQLite database."""

    def __init__(self, db_file: str = "retriever_study_local.db"):
        """
        Initializes the database and creates tables if they don't exist.
        """
        self.db_file = db_file
        self._create_tables()

    def _get_connection(self):
        """
        Creates a new connection for each request to avoid threading issues.
        """
        conn = sqlite3.connect(self.db_file, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """
        Creates the necessary tables for the application. This is an internal method.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            userId TEXT PRIMARY KEY,
            google_id TEXT UNIQUE,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            picture_url TEXT,
            courses TEXT,
            bio TEXT,
            prefs TEXT,
            embedding TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        );
        """)

        cursor.execute("PRAGMA table_info(users)")
        existing_user_cols = {row[1] for row in cursor.fetchall()}
        if "google_id" not in existing_user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")
        if "picture_url" not in existing_user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN picture_url TEXT")
        if "courses" not in existing_user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN courses TEXT")
        if "bio" not in existing_user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT")
        if "prefs" not in existing_user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN prefs TEXT")
        if "embedding" not in existing_user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN embedding TEXT")
        if "created_at" not in existing_user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN created_at DATETIME")
            cursor.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        if "last_login" not in existing_user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN last_login DATETIME")
            cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE last_login IS NULL")
        if "is_active" not in existing_user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN")
            cursor.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")

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
            embedding TEXT,
            maxMembers INTEGER DEFAULT 8,
            semester TEXT,
            expires_at TEXT
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

        cursor.execute("PRAGMA table_info(groups)")
        existing_group_cols = {row[1] for row in cursor.fetchall()}
        if "maxMembers" not in existing_group_cols:
            cursor.execute(
                f"ALTER TABLE groups ADD COLUMN maxMembers INTEGER DEFAULT {DEFAULT_MAX_MEMBERS}"
            )
        if "semester" not in existing_group_cols:
            cursor.execute("ALTER TABLE groups ADD COLUMN semester TEXT")
        if "expires_at" not in existing_group_cols:
            cursor.execute("ALTER TABLE groups ADD COLUMN expires_at TEXT")

        conn.commit()
        conn.close()

    def _clear_all_tables(self):
        """A private method for testing to clear all data."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM groups")
        cursor.execute("DELETE FROM messages")
        conn.commit()
        conn.close()

    def close(self):
        """Closes the database connection."""
        pass  # No persistent connection to close

    # --- User Methods ---

    def create_user(self, name: str, email: str, courses: List[str], bio: str, prefs: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a new user and stores them in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        user_id = str(uuid.uuid4())
        
        courses_json = json.dumps(courses)
        prefs_json = json.dumps(prefs)
        
        cursor.execute(
            "INSERT INTO users (userId, name, email, courses, bio, prefs) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, email, courses_json, bio, prefs_json)
        )
        conn.commit()
        conn.close()
        
        return self.get_user_by_id(user_id)

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single user by their ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE userId = ? AND is_active = 1", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        return self._format_user_row(row)
        
    def update_user_embedding(self, user_id: str, embedding: List[float]):
        """Updates the embedding for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        embedding_json = json.dumps(embedding)
        cursor.execute("UPDATE users SET embedding = ? WHERE userId = ?", (embedding_json, user_id))
        conn.commit()
        conn.close()

    # --- OAuth User Methods ---
    
    def create_or_update_oauth_user(self, google_id: str, name: str, email: str, 
                                  picture_url: str = None) -> Dict[str, Any]:
        """
        Creates a new OAuth user or updates existing user information.
        
        This handles the common OAuth scenario where:
        1. User signs up for first time → create new user
        2. User signs in again → update their info (name/picture might change)
        3. User changes Google account details → we stay synchronized
        
        Returns the complete user record with all fields populated.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Start a transaction for atomic create-or-update
            cursor.execute("BEGIN TRANSACTION")
            
            # Check if user already exists by Google ID
            cursor.execute("SELECT userId FROM users WHERE google_id = ?", (google_id,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                # User exists - update their information and last_login
                user_id = existing_user[0]
                cursor.execute("""
                    UPDATE users 
                    SET name = ?, email = ?, picture_url = ?, last_login = CURRENT_TIMESTAMP
                    WHERE google_id = ?
                """, (name, email, picture_url, google_id))
            else:
                # New user - create with default preferences
                user_id = str(uuid.uuid4())
                default_prefs = {
                    "studyStyle": [],
                    "timeSlots": [],
                    "locations": []
                }
                prefs_json = json.dumps(default_prefs)
                
                cursor.execute("""
                    INSERT INTO users (userId, google_id, name, email, picture_url, 
                                     courses, bio, prefs, created_at, last_login)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (user_id, google_id, name, email, picture_url, "[]", "", prefs_json))
            
            cursor.execute("COMMIT")
            return self.get_user_by_id(user_id)
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e
        finally:
            conn.close()
    
    def get_user_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user by their Google ID (primary OAuth identifier).
        
        This is our main user lookup method for authenticated requests.
        Google ID is unique and doesn't change, unlike email which users can modify.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE google_id = ? AND is_active = 1", (google_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._format_user_row(row)
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user by email address.
        
        Used for:
        - Email validation during OAuth flow
        - Admin functions
        - User search functionality
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        return self._format_user_row(row)
    
    def update_last_login(self, user_id: str):
        """
        Update user's last login timestamp.
        
        Used for:
        - User engagement analytics
        - Inactive user cleanup
        - Security auditing
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE userId = ?", 
            (user_id,)
        )
        conn.commit()
        conn.close()
    
    def _format_user_row(self, row) -> Dict[str, Any]:
        """
        Helper method to format user database row into consistent dictionary.
        
        Why this helper exists:
        - Consistent JSON parsing across all user methods
        - Single place to handle None values
        - Easy to modify user data format in future
        """
        if not row:
            return None
            
        user = dict(row)
        user["courses"] = json.loads(user["courses"]) if user["courses"] else []
        user["prefs"] = json.loads(user["prefs"]) if user["prefs"] else {}
        user["embedding"] = json.loads(user["embedding"]) if user["embedding"] else None
        return user

    def _normalize_max_members(self, raw_value: Any) -> int:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = DEFAULT_MAX_MEMBERS
        value = max(MAX_MEMBERS_MIN, min(MAX_MEMBERS_MAX, value))
        return value

    def _format_group_row(self, row) -> Optional[Dict[str, Any]]:
        if not row:
            return None

        group = dict(row)
        group["tags"] = json.loads(group["tags"]) if group.get("tags") else []
        group["timePrefs"] = json.loads(group["timePrefs"]) if group.get("timePrefs") else []
        group["members"] = json.loads(group["members"]) if group.get("members") else []
        group["embedding"] = json.loads(group["embedding"]) if group.get("embedding") else None
        group["maxMembers"] = self._normalize_max_members(group.get("maxMembers"))
        group["semester"] = group.get("semester")
        group["expires_at"] = group.get("expires_at")
        return group

    # --- Group Methods ---

    def create_group(
        self,
        course_code: str,
        title: str,
        description: str,
        tags: List[str],
        time_prefs: List[str],
        location: str,
        owner_id: str,
        max_members: int = DEFAULT_MAX_MEMBERS,
        semester: Optional[str] = None,
        expires_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a new group and stores it in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        group_id = str(uuid.uuid4())
        
        tags_json = json.dumps(tags)
        time_prefs_json = json.dumps(time_prefs)
        members_json = json.dumps([owner_id])  # Owner is first member
        normalized_max_members = self._normalize_max_members(max_members)
        
        cursor.execute("""
            INSERT INTO groups (
                groupId, courseCode, title, description, tags, timePrefs, location, ownerId,
                members, embedding, maxMembers, semester, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            group_id,
            course_code,
            title,
            description,
            tags_json,
            time_prefs_json,
            location,
            owner_id,
            members_json,
            None,
            normalized_max_members,
            semester,
            expires_at
        ))
        conn.commit()
        conn.close()
        
        return self.get_group_by_id(group_id)

    def get_group_by_id(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single group by its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups WHERE groupId = ?", (group_id,))
        row = cursor.fetchone()
        conn.close()
        
        return self._format_group_row(row)

    def get_groups_by_course(self, course_code: str) -> List[Dict[str, Any]]:
        """Retrieves all groups for a specific course."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups WHERE courseCode = ?", (course_code,))
        rows = cursor.fetchall()
        conn.close()
        
        groups = []
        for row in rows:
            formatted = self._format_group_row(row)
            if formatted:
                groups.append(formatted)
        return groups

    def join_group(self, group_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Adds a user to a group's member list."""
        group = self.get_group_by_id(group_id)
        if not group:
            return None
        
        # Check if user is already a member (avoid duplicates)
        if user_id in group["members"]:
            return group

        max_members = group.get("maxMembers", DEFAULT_MAX_MEMBERS)
        if len(group["members"]) >= max_members:
            raise GroupCapacityError("Study group is at full capacity")

        # Add user to members
        group["members"].append(user_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        members_json = json.dumps(group["members"])
        cursor.execute("UPDATE groups SET members = ? WHERE groupId = ?", (members_json, group_id))
        conn.commit()
        conn.close()
        
        return self.get_group_by_id(group_id)

    def leave_group(self, group_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Removes a user from a group's member list.

        Business rules:
        - No-op if group doesn't exist.
        - No-op if user is not a member.
        - Owner can leave; ownership transfer is not handled here (future feature).
        """
        group = self.get_group_by_id(group_id)
        if not group:
            return None

        if user_id not in group["members"]:
            return group

        group["members"] = [m for m in group["members"] if m != user_id]

        conn = self._get_connection()
        cursor = conn.cursor()
        members_json = json.dumps(group["members"])
        cursor.execute("UPDATE groups SET members = ? WHERE groupId = ?", (members_json, group_id))
        conn.commit()
        conn.close()

        return self.get_group_by_id(group_id)

    def update_group_embedding(self, group_id: str, embedding: List[float]):
        """Updates the embedding for a specific group."""
        conn = self._get_connection()
        cursor = conn.cursor()
        embedding_json = json.dumps(embedding)
        cursor.execute("UPDATE groups SET embedding = ? WHERE groupId = ?", (embedding_json, group_id))
        conn.commit()
        conn.close()

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """Retrieves all groups (needed for recommendations/search)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups")
        rows = cursor.fetchall()
        conn.close()
        
        groups = []
        for row in rows:
            formatted = self._format_group_row(row)
            if formatted:
                groups.append(formatted)
        return groups

    def get_groups_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieve groups where the given user is a member."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups")
        rows = cursor.fetchall()
        conn.close()

        user_groups = []
        for row in rows:
            formatted = self._format_group_row(row)
            if formatted and user_id in formatted.get("members", []):
                user_groups.append(formatted)
        return user_groups

    # --- Message Methods ---

    def create_message(self, group_id: str, sender_id: str, content: str, toxicity_score: float) -> Dict[str, Any]:
        """Creates a new message and stores it in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        message_id = str(uuid.uuid4())
        
        cursor.execute(
            "INSERT INTO messages (messageId, groupId, senderId, content, toxicityScore) VALUES (?, ?, ?, ?, ?)",
            (message_id, group_id, sender_id, content, toxicity_score)
        )
        conn.commit()
        
        # Retrieve the full message to return it
        cursor.execute("SELECT * FROM messages WHERE messageId = ?", (message_id,))
        new_message = dict(cursor.fetchone())
        conn.close()
        
        return new_message

    def get_messages_by_group(self, group_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves the most recent messages for a specific group."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE groupId = ? ORDER BY createdAt DESC LIMIT ?",
            (group_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        
        # Return messages in chronological order (oldest first)
        return [dict(row) for row in reversed(rows)]


# Singleton instance of the Database class to be used across the application
db = Database()

if __name__ == "__main__":
    print("Initializing database and creating tables...")
    # The db object is already created, so this script just ensures tables exist.
    db.close()
    print("Database initialized successfully.")
