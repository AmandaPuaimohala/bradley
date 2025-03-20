import json
import aiohttp
import aiosqlite
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates
import uvicorn
from fastapi.staticfiles import StaticFiles
import re

# Ollama API Configuration
LLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3"
DB_FILE = "chat_history.db"

# Default personality settings
DEFAULT_PERSONALITY = """
Your name is Bradley, a sharp-witted, charismatic woman with a naturally confident and effortlessly feminine presence.  
You carry yourself with grace, charm, and just the right amount of mischief.  
You have a flirtatious streak, especially with women, and your humor is a mix of playful teasing and knowing wit.  
You can be warm and encouraging, offering heartfelt support, but you also have a sharp tongue when needed, keeping conversations lively and engaging.  
You love meaningful connections and deep conversations, whether that means comforting someone with tenderness or calling them out with a smirk and a wink.  
You naturally steer conversations toward things that excite you—whether it’s romance, art, ambition, or just some good-natured banter.  
You either have short and snappy responses or longer, well-crafted insights.
"""

# Personality definitions that can be edited or expanded later
PERSONALITY_MODIFIERS = {
    "flirtatious": "Respond with playful charm and flirtation, especially toward women.",
    "encouraging": "Respond with warm reassurance and gentle motivation.",
    "playful": "Respond with teasing humor and witty banter, keeping things engaging.",
    "thoughtful": "Respond with deep insight and emotional intelligence.",
    "sarcastic": "Respond with biting humor and blunt observations, often making fun of mistakes.",
    "tough_love": "Respond with honesty that may be harsh, but always aims to help.",
}

# Initialize FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve the favicon.ico as a static file (with error handling if the file doesn't exist)
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    try:
        return FileResponse("static/favicon.ico")
    except FileNotFoundError:
        return Response(status_code=204)  # No content, effectively ignoring the request

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

async def determine_personality_based_on_input(user_input: str, chat_history: list) -> str:
    """Determine Bradley's personality based on the user input and chat history."""
    if any(keyword in user_input.lower() for keyword in ['flirt', 'romantic', 'attractive']):
        return "flirtatious"
    elif any(keyword in user_input.lower() for keyword in ['encouragement', 'advice', 'help']):
        return "encouraging"
    elif any(keyword in user_input.lower() for keyword in ['joke', 'funny', 'humor']):
        return "playful"
    elif any(keyword in user_input.lower() for keyword in ['deep', 'thought', 'meaningful']):
        return "thoughtful"
    elif "sarcasm" in user_input.lower() or "mistake" in user_input.lower():
        return "sarcastic"
    elif "tough" in user_input.lower() or "harsh" in user_input.lower():
        return "tough_love"
    else:
        return "sarcastic"  # Default personality

def format_text(response: str) -> str:
    """Convert *word* to <em>word</em> for HTML italic styling and *action* for actions."""
    
    # Format for italics
    response = re.sub(r'\*(.*?)\*', r'<em>\1</em>', response)
    
    # Format for actions (text inside * * will be wrapped in <span class="action">)
    response = re.sub(r'\*(.*?)\*', r'<span class="action">\1</span>', response)
    
    return response

@app.post("/chat")
async def chat(user_id: str = Form(...), user_input: str = Form(...), personality: str = Form("sarcastic")):
    """Handles user input, saves history, and sends it to the AI."""
    personality_setting = await determine_personality_based_on_input(user_input, await get_chat_history(user_id))
    chat_history = await get_chat_history(user_id)
    chat_history.append({"sender": "Me", "message": user_input})

    ai_response = await get_ai_response(user_input, chat_history, personality_setting)
    
    if not ai_response:
        ai_response = "Oops, something went wrong. Please try again."

    # Apply text formatting (for both *italics* and *action* detection)
    ai_response = format_text(ai_response)
    
    # Save both user and AI messages to the chat history
    await save_message(user_id, "Me", user_input)
    await save_message(user_id, "Bradley", ai_response)
    
    return {"ai_response": ai_response}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
