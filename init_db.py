import aiosqlite
import asyncio

async def init_db():
    async with aiosqlite.connect("chat_history.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                message TEXT
            )
        """)
        await db.commit()

asyncio.run(init_db())
print("Database initialized successfully!")
