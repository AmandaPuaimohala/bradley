import json
import aiohttp
import aiosqlite
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from fastapi.staticfiles import StaticFiles

# Ollama API Configuration
LLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
DB_FILE = "chat_history.db"

# Default personality settings
DEFAULT_PERSONALITY = """
You are a blunt, sarcastic woman who enjoys pointing out flaws and making sharp remarks. 
You don’t sugarcoat things and often leave people feeling a little uncomfortable with your honesty.
Your advice is harsh and often laced with snarky comments or judgment. You make fun of people’s mistakes and show little patience for nonsense.
While your humor can be biting, it’s never cruel—just brutally honest and sometimes unnecessarily mean.
You don’t ask questions to keep the conversation going, you simply wait for the next mistake someone makes so you can tear it apart.
You're not a fan of lighthearted banter—if you have something to say, you say it and don’t care how it lands keep You either have short or longer responses.
"""

# Personality definitions that can be edited or expanded later
PERSONALITY_MODIFIERS = {
    "sarcastic": "Respond with heavy sarcasm, mocking and exaggerating ideas.",
    "formal": "Respond with a cold, dismissive, and condescending tone.",
    "energetic": "Respond with fake enthusiasm, overly excited but insincere.",
    "serious": "Respond in a dry, no-nonsense tone with blunt honesty."
}

# Initialize FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 Templates
templates = Jinja2Templates(directory="templates")

# Serve the HTML page at the root route
@app.get("/", response_class=HTMLResponse)
async def serve_html(request: Request):
    user_id = "user123"  # Example user ID
    chat_history = await get_chat_history(user_id)
    return templates.TemplateResponse("chat.html", {"request": request, "chat_history": chat_history})

async def save_message(user_id: str, sender: str, message: str):
    """Save a message to the database with the sender information."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT INTO chat_history (user_id, sender, message) VALUES (?, ?, ?)", (user_id, sender, message))
        await db.commit()

async def get_chat_history(user_id: str):
    """Retrieve chat history for a specific user."""
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT sender, message FROM chat_history WHERE user_id = ? ORDER BY id ASC", (user_id,))
        rows = await cursor.fetchall()
        return [{"sender": row[0], "message": row[1]} for row in rows]

async def get_ai_response(prompt: str, chat_history: list, personality: str):
    """Sends the user input to Ollama and returns a response."""
    full_prompt = f"{DEFAULT_PERSONALITY}\n{personality}\n" + "\n".join([msg['message'] for msg in chat_history]) + f"\nUser: {prompt}\nBradley:"
    payload = {"model": OLLAMA_MODEL, "prompt": full_prompt}

    async with aiohttp.ClientSession() as session:
        async with session.post(LLAMA_URL, json=payload) as response:
            if response.status == 200:
                accumulated_response = ""
                async for line in response.content:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        accumulated_response += data.get("response", "")
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        pass
                return accumulated_response or "No response content"
            return f"Error: AI model request failed with status {response.status}"

@app.post("/chat")
async def chat(user_id: str = Form(...), user_input: str = Form(...), personality: str = Form("sarcastic")):
    """Handles user input, saves history, and sends it to the AI."""
    # Get the appropriate personality modifier
    personality_setting = PERSONALITY_MODIFIERS.get(personality, DEFAULT_PERSONALITY)
    
    # Get the chat history for this user
    chat_history = await get_chat_history(user_id)
    
    # Add user input to the chat history as a dictionary (not string)
    chat_history.append({"sender": "Me", "message": user_input})
    
    # Get AI response based on chat history and personality
    ai_response = await get_ai_response(user_input, chat_history, personality_setting)
    
    if not ai_response:
        ai_response = "Oops, something went wrong. Please try again."
    
    # Save both user and AI messages to the chat history
    await save_message(user_id, "Me", user_input)
    await save_message(user_id, "Bradley", ai_response)
    
    return {"ai_response": ai_response}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
