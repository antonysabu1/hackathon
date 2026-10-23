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
def chat_about_lap(question, lap_time, sectors, issues):
    issues_text = "\n".join([
        f"- At {i['distance_m']}m (t={i['time']}s): {i['issue_type']}, "
        f"{i['speed_delta']} kph slower than reference"
        for i in issues
    ]) if issues else "No significant issues detected."

    sectors_text = "\n".join([
        f"Sector {s['sector']}: {round(s['time'], 2)}s (runs from t={round(sum(x['time'] for x in sectors[:s['sector']-1]), 2)}s to t={round(sum(x['time'] for x in sectors[:s['sector']]), 2)}s)"
        for s in sectors
    ])

    prompt = f"""
You are a sim racing coach talking directly to a driver. They just completed a lap in {lap_time} seconds.

Sector breakdown:
{sectors_text}

Issues detected compared to a reference lap (each tagged with the time in the lap it happened):
{issues_text}

The driver asks: "{question}"

Answer their question directly using the data above. If they ask about a specific sector, only reference issues whose timestamp falls inside that sector's time range. Keep it to 2-4 sentences, plain English, like a real coach — not generic AI filler.
"""

    message = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    for block in message.content:
        if block.type == "text":
            return block.text
    return "No response generated."
