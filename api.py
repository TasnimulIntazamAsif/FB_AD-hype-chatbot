import os
import logging
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chatbot import ADPreferenceChatbot

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# ============================================
# Lifespan context manager (FastAPI 0.112+)
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up AD Hype Chatbot...")
    get_chatbot()
    yield
    # Shutdown
    logger.info("Shutting down AD Hype Chatbot...")

# ============================================
# FastAPI App with lifespan
# ============================================
app = FastAPI(
    title="AD Hype Chatbot",
    version="2.0.0",
    lifespan=lifespan
)

chatbot: ADPreferenceChatbot | None = None


class ChatRequest(BaseModel):
    message: str


def get_chatbot() -> ADPreferenceChatbot:
    global chatbot
    if chatbot is None:
        chatbot = ADPreferenceChatbot()
        chatbot.initialize()
    return chatbot


# ============================================
# Routes
# ============================================
@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def status():
    bot = get_chatbot()
    db_connected = bot.db_manager.is_connected()
    openai_configured = bot.openai_client.client is not None

    db_message = "Connected" if db_connected else "Database connection failed. Check `.env` credentials."
    if not db_connected and bot.db_manager.conn_params.get("host"):
        db_message = (
            f"Could not connect to {bot.db_manager.conn_params['host']}:"
            f"{bot.db_manager.conn_params.get('port', 5432)}"
        )

    return {
        "database": {
            "connected": db_connected,
            "host": bot.db_manager.conn_params.get("host"),
            "database_name": bot.db_manager.conn_params.get("dbname"),
            "schema": bot.db_manager.schema,
            "tables_discovered": len(bot.db_manager.get_table_names()),
            "message": db_message,
        },
        "openai": {
            "configured": openai_configured,
            "model": bot.openai_client.model,
        },
    }


@app.get("/api/schema")
async def schema():
    bot = get_chatbot()
    if not bot.db_manager.is_connected():
        raise HTTPException(status_code=503, detail="Database not connected")
    return await asyncio.to_thread(bot.db_manager.get_schema_dict)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    bot = get_chatbot()
    try:
        result = await asyncio.to_thread(bot.process_question, message)
        return {
            "response": result.get("response", ""),
            "sql_query": result.get("sql_query"),
            "sql_results": result.get("sql_results", []),
            "rows_returned": result.get("rows_returned", 0),
            "data_found": result.get("data_found", False),
            "query_type": result.get("query_type", "nl2sql"),
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {
            "response": f"Sorry, an error occurred: {str(e)}",
            "error": str(e),
            "sql_query": None,
            "sql_results": [],
        }


# ============================================
# Static Files
# ============================================
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ============================================
# Run
# ============================================
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    print("=" * 50)
    print("AD Hype Chatbot (NL2SQL) starting...")
    print(f"Open: http://localhost:{port}")
    print("=" * 50)
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)