import pytest
from app.data.async_db import engine, Base

@pytest.mark.asyncio
async def test_create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
