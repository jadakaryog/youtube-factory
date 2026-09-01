import sqlite3
import openai

def analyze_rejections():
    # Read rejection_log.txt
    with open('rejection_log.txt', 'r') as f:
        rejections = f.readlines()
    
    # Ask AI to summarize patterns
    prompt = f"""
    Here are rejection reasons from the last 30 days:
    {''.join(rejections[-30:])}
    
    Summarize the top 3 patterns. Then suggest improvements to the scriptwriter prompt.
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Save the improvements to your system prompt
    with open('system_prompt_improvements.txt', 'w') as f:
        f.write(response.choices[0].message.content)
    
    print("✅ Learning Edge updated!")

# Run this weekly
analyze_rejections()