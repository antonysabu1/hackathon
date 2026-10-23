from claude_integration import get_insight_from_claude

issue_data = {
    "corner": "Turn 3",
    "issue": "late_brake_release",
    "their_speed": 85,
    "ref_speed": 95,
    "delta_time": 0.3
}

result = get_insight_from_claude({}, issue_data)
print(result)
