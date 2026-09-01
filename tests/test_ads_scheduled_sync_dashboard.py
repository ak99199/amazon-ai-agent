from pathlib import Path

def test_dashboard_has_read_only_scheduled_health_without_controls():
 text=Path("templates/dashboard.html").read_text(encoding="utf-8")
 section=text[text.index("<h3>Scheduled Sync</h3>"):text.index("Recent Historical Sync Runs")]
 assert "Consecutive failures" in section and "Next due" in section and "Overdue" in section
 assert "force scheduled" not in section.lower() and "recover stale" not in section.lower() and "enable scheduled" not in section.lower()
