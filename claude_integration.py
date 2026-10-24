from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic

client = Anthropic()

def get_insight_from_claude(lap_data, issue_data):
    prompt = f"""
    A sim racer uploaded a lap. Here's what they did wrong:
    
    Corner: {issue_data.get('corner', 'Unknown')}
    Issue: {issue_data.get('issue', 'Unknown')}
    Their speed: {issue_data.get('their_speed', 0)} kph
    Reference speed: {issue_data.get('ref_speed', 0)} kph
    Speed deficit: {issue_data.get('speed_delta', 0)} kph slower than reference at this point
    
    Give one sentence of actionable coaching advice in plain English.
    """    
    message = client.messages.create(
    model="claude-sonnet-5-5",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    for block in message.content:
        if block.type == "text":
            return block.text
    return "No text response generated."
