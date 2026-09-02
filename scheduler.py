import schedule
import time
import requests
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Your Render dashboard URL
DASHBOARD_URL = "https://youtube-factory-e8ec.onrender.com"
GENERATE_ENDPOINT = f"{DASHBOARD_URL}/api/generate"

# Topics for each day of the week (customize these!)
TOPICS = {
    "monday": "Latest trends in AI technology",
    "wednesday": "How to make money with YouTube automation",
    "friday": "Top 10 AI tools you need to know",
    "sunday": "Future of content creation with AI"
}

def generate_video_for_day(day: str):
    """Generate a video for a specific day."""
    topic = TOPICS.get(day)
    if not topic:
        logger.error(f"No topic found for {day}")
        return
    
    logger.info(f"🎬 Generating video for {day}: {topic}")
    
    try:
        response = requests.post(
            GENERATE_ENDPOINT,
            json={"topic": topic},
            timeout=600  # 10 minute timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Video generated successfully: {data}")
        else:
            logger.error(f"❌ Generation failed: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Error generating video: {str(e)}")

def run_scheduler():
    """Run the scheduler with 4 videos per week."""
    logger.info("🚀 YouTube Factory Scheduler Started")
    logger.info(f"📅 Schedule: Monday, Wednesday, Friday, Sunday at 9:00 AM")
    
    # Schedule videos
    schedule.every().monday.at("09:00").do(generate_video_for_day, "monday")
    schedule.every().wednesday.at("09:00").do(generate_video_for_day, "wednesday")
    schedule.every().friday.at("09:00").do(generate_video_for_day, "friday")
    schedule.every().sunday.at("09:00").do(generate_video_for_day, "sunday")
    
    # Optional: Health check every hour to keep the service alive
    schedule.every(1).hour.do(lambda: logger.info("🔄 Scheduler is alive"))
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    run_scheduler()
