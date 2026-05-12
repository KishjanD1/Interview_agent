# Todo List AI Agent (Powered by Groq)

This is an intelligent Todo List Agent that understands natural language.

## Features

- **Standard API**: Create, read, update, and delete tasks via REST endpoints.
- **AI Brain**: Send messages like "Add a task to call mom" to the `/chat` endpoint.
- **Tool Calling**: The AI can interact with the task list directly to add, list, or delete items.

## Setup

1.  **Install dependencies**:
    ```bash
    pip install fastapi uvicorn groq python-dotenv
    ```
2.  **Add your API Key**:
    Open the `.env` file and replace `your_groq_api_key_here` with your actual Groq API key.

## Running the Agent

Start the server:
```bash
python main.py
```

## How to use the AI

Send a `POST` request to `/chat`:
```json
{
  "message": "Add a task to buy groceries and list my tasks"
}
```

The AI will parse your request, add the task, and respond with the current list!
