import schedule
import time

def run_pipeline():
    # Your script generation logic here
    print("🚀 Generating video for today...")

# Schedule 4 videos per week (Mon, Wed, Fri, Sun at 9 AM)
schedule.every().monday.at("09:00").do(run_pipeline)
schedule.every().wednesday.at("09:00").do(run_pipeline)
schedule.every().friday.at("09:00").do(run_pipeline)
schedule.every().sunday.at("09:00").do(run_pipeline)

while True:
    schedule.run_pending()
    time.sleep(60)