from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import json
import os
from pathlib import Path
from datetime import datetime
from upstash_redis.asyncio import Redis

app = FastAPI()

# Get the absolute path to the templates folder
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ============================================
# PART 1: Initialize Redis (Code Block #2)
# ============================================
# Initialize the Redis client using environment variables
redis = Redis.from_env()

# Helper function to store video data as a dictionary
def video_to_dict(row: dict) -> dict:
    """Converts a video hash from Redis to a dictionary for our API."""
    return {
        "id": row.get("id"),
        "topic": row.get("topic"),
        "status": row.get("status", "PENDING_APPROVAL"),
        "script": row.get("script", "Sample script"),
        "description": row.get("description", ""),
        "tags": row.get("tags", ""),
        "title_variants": json.loads(row.get("title_variants", "[]")),
        "thumbnail_urls": json.loads(row.get("thumbnail_urls", "[]")),
        "selected_title": row.get("selected_title"),
        "selected_thumbnail": row.get("selected_thumbnail"),
    }

# ============================================
# PART 2: API Endpoints (Code Block #3)
# ============================================

# API endpoint to get all videos
@app.get("/api/videos", response_class=JSONResponse)
async def get_all_videos():
    # Get all video IDs from a Redis set
    video_ids = await redis.smembers("videos:all")
    
    videos = []
    for video_id in video_ids:
        # Get the video data as a hash
        video_data = await redis.hgetall(f"video:{video_id}")
        if video_data:
            videos.append({
                "id": video_id,
                "topic": video_data.get("topic"),
                "status": video_data.get("status"),
                "created_at": video_data.get("created_at", ""),
            })
    
    # Sort videos by creation date (newest first)
    videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return videos

# API endpoint to get a specific video
@app.get("/api/videos/{video_id}", response_class=JSONResponse)
async def get_video(video_id: str):
    video_data = await redis.hgetall(f"video:{video_id}")
    if not video_data:
        return {"error": "Video not found"}
    
    return video_to_dict(video_data)

# Dashboard page
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        return HTMLResponse(content=f"""
        <html>
            <head><title>YouTube Factory</title></head>
            <body style="background:#0a0a0f; color:white; font-family: Arial; padding:40px;">
                <h1>🎬 YouTube Factory</h1>
                <h2>⚠️ Template Error</h2>
                <p>Error: {str(e)}</p>
            </body>
        </html>
        """, status_code=500)

@app.post("/api/approve/{video_id}")
async def approve_video(video_id: str):
    # Update the status in Redis
    await redis.hset(f"video:{video_id}", "status", "UPLOADING")
    # Remove from the pending set
    await redis.srem("videos:pending", video_id)
    return {"status": "approved"}

@app.post("/api/reject/{video_id}")
async def reject_video(video_id: str):
    await redis.hset(f"video:{video_id}", "status", "FAILED")
    await redis.hset(f"video:{video_id}", "failure_reason", "Rejected by user")
    # Remove from the pending set
    await redis.srem("videos:pending", video_id)
    return {"status": "rejected"}

# ============================================
# PART 3: Startup Event (Code Block #4)
# ============================================
@app.on_event("startup")
async def startup():
    # Check if we already have videos
    video_count = await redis.scard("videos:all")
    if video_count == 0:
        video_id = "test-001"
        # Store video data as a Redis hash
        await redis.hset(f"video:{video_id}", mapping={
            "id": video_id,
            "topic": "How AI is Changing YouTube Forever",
            "status": "PENDING_APPROVAL",
            "title_variants": json.dumps(["AI is Taking Over YouTube", "YouTube AI Revolution 2024", "How AI Creates Videos"]),
            "thumbnail_urls": json.dumps([
                "https://via.placeholder.com/1280x720/1a1a2e/ffffff?text=Thumbnail+1",
                "https://via.placeholder.com/1280x720/16213e/ffffff?text=Thumbnail+2",
                "https://via.placeholder.com/1280x720/0f3460/ffffff?text=Thumbnail+3"
            ]),
            "description": "This video explains how AI is transforming content creation on YouTube.",
            "tags": "AI, YouTube, Automation",
            "created_at": str(datetime.now())
        })
        # Add the video ID to the "all videos" set and the "pending" set
        await redis.sadd("videos:all", video_id)
        await redis.sadd("videos:pending", video_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
