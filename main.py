import os
import json
import psycopg2
import psycopg2.extras
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Rag based todo agent with fastapi")

# --- Models ---
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    history: List[ChatMessage]
    message: str

# --- DB Logic ---
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

def db_add_todo(title: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO todos (title) VALUES (%s) RETURNING id;", (title,))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id

def db_get_all_todos():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM todos ORDER BY id DESC;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- UI (Clean Single Column) ---
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Rag based todo agent with fastapi</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background: #020617; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { width: 500px; background: rgba(15, 23, 42, 0.9); border: 1px solid #1e293b; border-radius: 28px; padding: 2rem; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.7); display: flex; flex-direction: column; }
        h1 { color: #38bdf8; font-size: 1.3rem; text-align: center; margin-bottom: 1.5rem; text-transform: uppercase; letter-spacing: 1px; }
        .chat-box { height: 350px; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; padding-right: 10px; margin-bottom: 1.5rem; }
        .msg { padding: 12px 18px; border-radius: 18px; font-size: 0.95rem; max-width: 85%; line-height: 1.5; }
        .user { background: #1e293b; align-self: flex-end; border-bottom-right-radius: 4px; border: 1px solid #334155; }
        .agent { background: #075985; align-self: flex-start; border-bottom-left-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
        .input-area { display: flex; gap: 12px; }
        input { flex: 1; background: #0f172a; border: 1px solid #334155; border-radius: 14px; padding: 14px; color: white; outline: none; transition: 0.2s; }
        input:focus { border-color: #38bdf8; box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.1); }
        button { background: #38bdf8; color: #020617; border: none; padding: 0 24px; border-radius: 14px; font-weight: 700; cursor: pointer; transition: 0.3s; }
        button:hover { background: #7dd3fc; transform: translateY(-1px); }
    </style>
</head>
<body>
    <div class="container">
        <h1>Rag based todo agent with fastapi</h1>
        <div class="chat-box" id="chat">
            <div class="msg agent">Hello! I am your RAG Agent. I can manage your database tasks through our conversation.</div>
        </div>
        <div class="input-area">
            <input type="text" id="input" placeholder="What's on my list?..." onkeypress="if(event.key=='Enter') send()">
            <button onclick="send()">Send</button>
        </div>
    </div>
    <script>
        let history = [];
        async function send() {
            const input = document.getElementById('input');
            const chat = document.getElementById('chat');
            const val = input.value.trim();
            if(!val) return;
            
            chat.innerHTML += `<div class="msg user">${val}</div>`;
            input.value = '';
            chat.scrollTop = chat.scrollHeight;

            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: val, history: history})
            });
            const data = await res.json();
            
            chat.innerHTML += `<div class="msg agent">${data.response}</div>`;
            chat.scrollTop = chat.scrollHeight;
            history.push({role: 'user', content: val}, {role: 'assistant', content: data.response});
        }
    </script>
</body>
</html>
"""

# --- RAG Endpoint ---

@app.get("/", response_class=HTMLResponse)
def home(): return HTML_CONTENT

@app.post("/api/chat")
def chat_rag(request: ChatRequest):
    try:
        # RETRIEVAL step
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, title, completed FROM todos ORDER BY id DESC;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        context = "\n".join([f"ID: {r['id']}, Task: {r['title']}, Status: {'Done' if r['completed'] else 'Pending'}" for r in rows])

        SYSTEM_PROMPT = f"""
        You are the 'Rag based todo agent with fastapi'.
        Current Database Context:
        {context if context else "Empty"}
        
        Respond with JSON: {{"action": "add"|"chat", "title": "...", "message": "..."}}
        """

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in request.history: messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": request.message})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(response.choices[0].message.content)
        
        if ai_data.get("action") == "add":
            db_add_todo(ai_data.get("title"))
            return {"response": f"Added '{ai_data.get('title')}' to the database."}
        
        return {"response": ai_data.get("message", "Processed.")}

    except Exception as e:
        return {"response": f"Error: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
