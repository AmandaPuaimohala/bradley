import aiosqlite
import asyncio

async def init_db():
    try:
        async with aiosqlite.connect("chat_history.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sender TEXT NOT NULL
                )
            """)
            await db.commit()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization failed: {e}")

asyncio.run(init_db())
