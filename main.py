from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json
import os
from pathlib import Path

app = FastAPI()

# Get the absolute path to the templates folder
# This works on both Render and local development
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Create folders if they don't exist
Path("media/videos").mkdir(parents=True, exist_ok=True)

# Setup templates with absolute path
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Setup database
def init_db():
    conn = sqlite3.connect("youtube_factory.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            topic TEXT,
            status TEXT DEFAULT 'PENDING_APPROVAL',
            script TEXT,
            description TEXT,
            tags TEXT,
            title_variants TEXT,
            thumbnail_urls TEXT,
            selected_title TEXT,
            selected_thumbnail TEXT,
            youtube_video_id TEXT,
            failure_reason TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Add dummy video for testing
def add_dummy_video():
    conn = sqlite3.connect("youtube_factory.db")
    count = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    if count == 0:
        conn.execute("""
            INSERT INTO videos (id, topic, status, title_variants, thumbnail_urls, description, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "test-001",
            "How AI is Changing YouTube Forever",
            "PENDING_APPROVAL",
            json.dumps(["AI is Taking Over YouTube", "YouTube AI Revolution 2024", "How AI Creates Videos"]),
            json.dumps([
                "https://via.placeholder.com/1280x720/1a1a2e/ffffff?text=Thumbnail+1",
                "https://via.placeholder.com/1280x720/16213e/ffffff?text=Thumbnail+2",
                "https://via.placeholder.com/1280x720/0f3460/ffffff?text=Thumbnail+3"
            ]),
            "This video explains how AI is transforming content creation on YouTube.",
            "AI, YouTube, Automation"
        ))
    conn.commit()
    conn.close()

add_dummy_video()

# API endpoint to get all videos for the sidebar
@app.get("/api/videos", response_class=JSONResponse)
async def get_all_videos():
    conn = sqlite3.connect("youtube_factory.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, topic, status, created_at FROM videos WHERE status IN ('PENDING_APPROVAL', 'FAILED') ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

# API endpoint to get a specific video
@app.get("/api/videos/{video_id}", response_class=JSONResponse)
async def get_video(video_id: str):
    conn = sqlite3.connect("youtube_factory.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    if not row:
        return {"error": "Video not found"}
    
    return {
        "id": row["id"],
        "topic": row["topic"],
        "script": row["script"] or "Sample script",
        "description": row["description"] or "",
        "tags": row["tags"] or "",
        "title_variants": json.loads(row["title_variants"]) if row["title_variants"] else ["Title 1", "Title 2", "Title 3"],
        "thumbnail_urls": json.loads(row["thumbnail_urls"]) if row["thumbnail_urls"] else [],
        "status": row["status"],
        "video_url": "",
        "selected_title": row["selected_title"],
        "selected_thumbnail": row["selected_thumbnail"]
    }

# Dashboard page
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        # If template fails, show fallback with error details
        return HTMLResponse(content=f"""
        <html>
            <head><title>YouTube Factory</title></head>
            <body style="background:#0a0a0f; color:white; font-family: Arial; padding:40px;">
                <h1>🎬 YouTube Factory</h1>
                <h2>⚠️ Template Error</h2>
                <p>Error: {str(e)}</p>
                <p>Looking for templates at: {TEMPLATES_DIR}</p>
                <p>Files in this directory: {list(BASE_DIR.iterdir())}</p>
                <p>Files in templates folder: {list(TEMPLATES_DIR.iterdir()) if TEMPLATES_DIR.exists() else 'Templates folder not found'}</p>
            </body>
        </html>
        """, status_code=500)

@app.post("/api/approve/{video_id}")
async def approve_video(video_id: str):
    conn = sqlite3.connect("youtube_factory.db")
    conn.execute("UPDATE videos SET status = 'UPLOADING' WHERE id = ?", (video_id,))
    conn.commit()
    conn.close()
    return {"status": "approved"}

@app.post("/api/reject/{video_id}")
async def reject_video(video_id: str):
    conn = sqlite3.connect("youtube_factory.db")
    conn.execute("UPDATE videos SET status = 'FAILED' WHERE id = ?", (video_id,))
    conn.commit()
    conn.close()
    return {"status": "rejected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
