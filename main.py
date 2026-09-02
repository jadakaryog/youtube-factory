from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import json
import os
from pathlib import Path
from datetime import datetime
from upstash_redis.asyncio import Redis

# YouTube Upload Imports
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import asyncio

app = FastAPI()

# Get the absolute path to the templates folder
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ============================================
# Initialize Redis
# ============================================
redis = Redis.from_env()

# ============================================
# Helper Functions
# ============================================
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
# YouTube Upload Function
# ============================================
async def upload_to_youtube(video_id: str, title: str, description: str, tags: str, thumbnail_path: str = None):
    """
    Upload a video to YouTube.
    """
    # Get credentials from environment variable or use local file
    credentials_json = os.environ.get("GOOGLE_CREDENTIALS")
    
    if credentials_json:
        # Use credentials from environment variable (Render)
        import tempfile
        import json as json_lib
        
        # Write credentials to a temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_file.write(credentials_json)
        temp_file.close()
        credentials_path = temp_file.name
    else:
        # Use local file (development)
        credentials_path = "client_secret.json"
    
    try:
        # Set up OAuth flow
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/youtube.upload']
        )
        credentials = flow.run_local_server(port=0)
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Prepare video metadata
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags.split(',') if tags else [],
            },
            'status': {
                'privacyStatus': 'public'  # Change to 'unlisted' for testing
            }
        }
        
        # Upload video
        video_path = f"/media/videos/{video_id}/final.mp4"
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        
        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        
        response = await asyncio.to_thread(request.execute)
        return response['id']
    
    finally:
        # Clean up temporary file if we created one
        if credentials_json and 'credentials_path' in locals():
            os.unlink(credentials_path)

# ============================================
# API Endpoints
# ============================================

@app.get("/api/videos", response_class=JSONResponse)
async def get_all_videos():
    video_ids = await redis.smembers("videos:all")
    
    videos = []
    for video_id in video_ids:
        video_data = await redis.hgetall(f"video:{video_id}")
        if video_data:
            videos.append({
                "id": video_id,
                "topic": video_data.get("topic"),
                "status": video_data.get("status"),
                "created_at": video_data.get("created_at", ""),
            })
    
    videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return videos

@app.get("/api/videos/{video_id}", response_class=JSONResponse)
async def get_video(video_id: str):
    video_data = await redis.hgetall(f"video:{video_id}")
    if not video_data:
        return {"error": "Video not found"}
    return video_to_dict(video_data)

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
    try:
        # 1. Get video details from Redis
        video_data = await redis.hgetall(f"video:{video_id}")
        if not video_data:
            return {"error": "Video not found"}
        
        # 2. Get selected title and thumbnail (or use defaults)
        title = video_data.get("selected_title") or video_data.get("title_variants", "[]").split(",")[0]
        description = video_data.get("description", "")
        tags = video_data.get("tags", "")
        thumbnail = video_data.get("selected_thumbnail", "")
        
        # 3. Upload to YouTube
        youtube_id = await upload_to_youtube(
            video_id,
            title,
            description,
            tags,
            thumbnail
        )
        
        # 4. Update Redis
        await redis.hset(f"video:{video_id}", "status", "PUBLISHED")
        await redis.hset(f"video:{video_id}", "youtube_video_id", youtube_id)
        await redis.srem("videos:pending", video_id)
        
        return {"status": "published", "youtube_id": youtube_id}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/reject/{video_id}")
async def reject_video(video_id: str):
    await redis.hset(f"video:{video_id}", "status", "FAILED")
    await redis.hset(f"video:{video_id}", "failure_reason", "Rejected by user")
    await redis.srem("videos:pending", video_id)
    return {"status": "rejected"}

# ============================================
# Startup Event
# ============================================
@app.on_event("startup")
async def startup():
    video_count = await redis.scard("videos:all")
    if video_count == 0:
        video_id = "test-001"
        await redis.hset(f"video:{video_id}", "id", video_id)
        await redis.hset(f"video:{video_id}", "topic", "How AI is Changing YouTube Forever")
        await redis.hset(f"video:{video_id}", "status", "PENDING_APPROVAL")
        await redis.hset(f"video:{video_id}", "title_variants", json.dumps(["AI is Taking Over YouTube", "YouTube AI Revolution 2024", "How AI Creates Videos"]))
        await redis.hset(f"video:{video_id}", "thumbnail_urls", json.dumps([
            "https://via.placeholder.com/1280x720/1a1a2e/ffffff?text=Thumbnail+1",
            "https://via.placeholder.com/1280x720/16213e/ffffff?text=Thumbnail+2",
            "https://via.placeholder.com/1280x720/0f3460/ffffff?text=Thumbnail+3"
        ]))
        await redis.hset(f"video:{video_id}", "description", "This video explains how AI is transforming content creation on YouTube.")
        await redis.hset(f"video:{video_id}", "tags", "AI, YouTube, Automation")
        await redis.hset(f"video:{video_id}", "created_at", str(datetime.now()))
        
        await redis.sadd("videos:all", video_id)
        await redis.sadd("videos:pending", video_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
