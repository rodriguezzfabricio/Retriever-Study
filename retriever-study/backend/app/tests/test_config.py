"""
Test configuration for the application.
"""
from pydantic import BaseModel

class Config(BaseModel):
    app_name: str = "Retriever Study API (Test)"
    environment: str = "test"
    debug: bool = True
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_retriever_study"
    jwt_secret: str = "test-secret-key"
    google_client_id: str = "test-google-client-id"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

# Create a singleton instance
config = Config()

def get_config():
    """Get the configuration instance."""
    return config
