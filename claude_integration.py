from anthropic import Anthropic

client = Anthropic()

def get_insight_from_claude(lap_data, issue_data):
    prompt = f"""
    A sim racer uploaded a lap. Here's what they did wrong:
    
    Corner: {issue_data.get('corner', 'Unknown')}
    Issue: {issue_data.get('issue', 'Unknown')}
    Their speed: {issue_data.get('their_speed', 0)} kph
    Reference speed: {issue_data.get('ref_speed', 0)} kph
    Time delta: {issue_data.get('delta_time', 0)} seconds
    
    Give one sentence of actionable coaching advice in plain English.
    """
    
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=100,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text
