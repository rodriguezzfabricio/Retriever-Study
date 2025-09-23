"""
Integration tests for the database layer.

This test suite validates the database operations including:
- User CRUD operations
- Group CRUD operations
- Message CRUD operations
- Complex queries and relationships
- Data integrity constraints
"""

import os
import pytest
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Set test environment before importing app
os.environ['ENVIRONMENT'] = 'test'
os.environ['DB_TYPE'] = 'sqlite'

from app.data.database import Database, User, Group, Message, DB_FILE

# Test data
TEST_USER = {
    "userId": "test_user_123",
    "name": "Test User",
    "email": "test@example.com",
    "courses": ["CMSC341", "MATH301"],
    "bio": "Test bio",
    "prefs": {"study_style": ["focused"], "time_of_day": ["morning"]},
    "embedding": [0.1, 0.2, 0.3]
}

TEST_GROUP = {
    "groupId": "test_group_123",
    "courseCode": "CMSC341",
    "title": "Test Study Group",
    "description": "A test study group",
    "tags": ["algorithms", "data_structures"],
    "timePrefs": ["monday_10am"],
    "location": "Library",
    "ownerId": "test_user_123",
    "members": ["test_user_123"],
    "embedding": [0.1, 0.2, 0.3],
    "maxMembers": 4
}

TEST_MESSAGE = {
    "messageId": "msg_123",
    "groupId": "test_group_123",
    "senderId": "test_user_123",
    "content": "Hello, test message!",
    "createdAt": datetime.utcnow().isoformat(),
    "toxicityScore": 0.05
}

@pytest.fixture(scope="module")
def test_db():
    """Set up test database with test data."""
    # Initialize test database
    db = Database()
    
    # Create test tables if they don't exist
    conn = db._get_connection()
    cursor = conn.cursor()
    
    # Start with a clean state
    cursor.execute("DROP TABLE IF EXISTS messages")
    cursor.execute("DROP TABLE IF EXISTS groups")
    cursor.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    
    # Recreate tables
    db._init_sqlite()
    
    yield db
    
    # Clean up
    conn.close()
    try:
        os.remove(DB_FILE)
    except:
        pass

class TestUserOperations:
    """Test user-related database operations."""
    
    def test_create_user(self, test_db):
        """Test creating a new user."""
        user = User(**TEST_USER)
        created_user = test_db.create_user(user)
        
        assert created_user.userId == TEST_USER["userId"]
        assert created_user.name == TEST_USER["name"]
        assert created_user.email == TEST_USER["email"]
        assert created_user.courses == TEST_USER["courses"]
        assert created_user.bio == TEST_USER["bio"]
        assert created_user.prefs == TEST_USER["prefs"]
        assert created_user.embedding == TEST_USER["embedding"]
    
    def test_get_user(self, test_db):
        """Test retrieving a user by ID."""
        user = test_db.get_user(TEST_USER["userId"])
        
        assert user is not None
        assert user.userId == TEST_USER["userId"]
        assert user.email == TEST_USER["email"]
    
    def test_update_user(self, test_db):
        """Test updating user information."""
        updates = {
            "name": "Updated Name",
            "bio": "Updated bio",
            "courses": ["CMSC341", "MATH301", "CMSC313"]
        }
        
        updated_user = test_db.update_user(TEST_USER["userId"], updates)
        
        assert updated_user is not None
        assert updated_user.name == "Updated Name"
        assert updated_user.bio == "Updated bio"
        assert "CMSC313" in updated_user.courses
    
    def test_delete_user(self, test_db):
        """Test deleting a user."""
        # Create a test user to delete
        user_data = TEST_USER.copy()
        user_data["userId"] = "user_to_delete"
        user_data["email"] = "delete_me@example.com"
        test_db.create_user(User(**user_data))
        
        # Delete the user
        test_db.delete_user("user_to_delete")
        
        # Verify deletion
        deleted_user = test_db.get_user("user_to_delete")
        assert deleted_user is None

class TestGroupOperations:
    """Test group-related database operations."""
    
    def test_create_group(self, test_db):
        """Test creating a new group."""
        # Make sure the owner exists
        user = User(**TEST_USER)
        test_db.create_user(user)
        
        # Create group
        group = Group(**TEST_GROUP)
        created_group = test_db.create_group(group)
        
        assert created_group.groupId == TEST_GROUP["groupId"]
        assert created_group.title == TEST_GROUP["title"]
        assert created_group.ownerId == TEST_GROUP["ownerId"]
        assert TEST_USER["userId"] in created_group.members
    
    def test_get_group(self, test_db):
        """Test retrieving a group by ID."""
        group = test_db.get_group(TEST_GROUP["groupId"])
        
        assert group is not None
        assert group.groupId == TEST_GROUP["groupId"]
        assert group.title == TEST_GROUP["title"]
    
    def test_update_group(self, test_db):
        """Test updating group information."""
        updates = {
            "title": "Updated Group Title",
            "description": "Updated description",
            "maxMembers": 6
        }
        
        updated_group = test_db.update_group(TEST_GROUP["groupId"], updates)
        
        assert updated_group is not None
        assert updated_group.title == "Updated Group Title"
        assert updated_group.description == "Updated description"
        assert updated_group.maxMembers == 6
    
    def test_join_group(self, test_db):
        """Test adding a member to a group."""
        # Create a test user to join the group
        user_data = TEST_USER.copy()
        user_data["userId"] = "new_member"
        user_data["email"] = "new_member@example.com"
        test_db.create_user(User(**user_data))
        
        # Join the group
        updated_group = test_db.join_group(TEST_GROUP["groupId"], "new_member")
        
        assert updated_group is not None
        assert "new_member" in updated_group.members
    
    def test_leave_group(self, test_db):
        """Test removing a member from a group."""
        # First join the group
        test_db.join_group(TEST_GROUP["groupId"], "new_member")
        
        # Now leave the group
        updated_group = test_db.leave_group(TEST_GROUP["groupId"], "new_member")
        
        assert updated_group is not None
        assert "new_member" not in updated_group.members

class TestMessageOperations:
    """Test message-related database operations."""
    
    def test_create_message(self, test_db):
        """Test creating a new message."""
        # Create test group and user if they don't exist
        user = User(**TEST_USER)
        test_db.create_user(user)
        group = Group(**TEST_GROUP)
        test_db.create_group(group)
        
        # Create message
        message = Message(**TEST_MESSAGE)
        created_message = test_db.create_message(message)
        
        assert created_message.messageId == TEST_MESSAGE["messageId"]
        assert created_message.content == TEST_MESSAGE["content"]
        assert created_message.senderId == TEST_MESSAGE["senderId"]
        assert created_message.groupId == TEST_MESSAGE["groupId"]
    
    def test_get_messages_by_group(self, test_db):
        """Test retrieving messages for a group."""
        messages = test_db.get_messages_by_group(TEST_MESSAGE["groupId"], limit=10)
        
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert messages[0].content == TEST_MESSAGE["content"]
    
    def test_delete_message(self, test_db):
        """Test deleting a message."""
        # Create a test message to delete
        message_data = TEST_MESSAGE.copy()
        message_data["messageId"] = "msg_to_delete"
        message = Message(**message_data)
        test_db.create_message(message)
        
        # Delete the message
        test_db.delete_message("msg_to_delete")
        
        # Verify deletion
        messages = test_db.get_messages_by_group(TEST_MESSAGE["groupId"], limit=100)
        message_ids = [msg.messageId for msg in messages]
        assert "msg_to_delete" not in message_ids

class TestComplexQueries:
    """Test complex database queries and relationships."""
    
    def test_find_groups_by_course(self, test_db):
        """Test finding groups by course code."""
        groups = test_db.find_groups_by_course("CMSC341")
        
        assert isinstance(groups, list)
        assert any(g.groupId == TEST_GROUP["groupId"] for g in groups)
    
    def test_find_groups_by_owner(self, test_db):
        """Test finding groups by owner ID."""
        groups = test_db.find_groups_by_owner(TEST_USER["userId"])
        
        assert isinstance(groups, list)
        assert any(g.groupId == TEST_GROUP["groupId"] for g in groups)
    
    def test_find_user_groups(self, test_db):
        """Test finding all groups a user is a member of."""
        groups = test_db.find_user_groups(TEST_USER["userId"])
        
        assert isinstance(groups, list)
        assert any(g.groupId == TEST_GROUP["groupId"] for g in groups)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
