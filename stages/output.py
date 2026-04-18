import subprocess
from datetime import date
from pathlib import Path

from models import DigestItem

DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _render_markdown(items: list[DigestItem], run_date: date) -> str:
    lines = [f"# Daily Digest — {run_date.isoformat()}\n"]
    for item in items:
        v = item.video

        heading = f"## [{v.title}]({v.url})"
        if item.relevance_score > 0:
            heading += f"  ·  ★ {item.relevance_score}/10"
        lines.append(heading)

        lines.append(f"**{v.channel}** · {v.published_at.strftime('%Y-%m-%d')}\n")
        lines.append(item.summary + "\n")

        if item.insights:
            highlighted = set(item.relevant_insights)
            for i, insight in enumerate(item.insights):
                text = f"**{insight}**" if i in highlighted else insight
                lines.append(f"- {text}")
            lines.append("")

        if item.tags:
            lines.append(" ".join(f"`{t}`" for t in item.tags))
            lines.append("")

        lines.append("---\n")
    return "\n".join(lines)


def _notify(title: str, body: str) -> None:
    script = f'display notification "{body}" with title "{title}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except Exception:
        pass


def write_output(items: list[DigestItem], output_dir: Path | None = None) -> Path:
    dest = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    dest.mkdir(parents=True, exist_ok=True)
    today = date.today()
    path = dest / f"digest_{today.isoformat()}.md"
    path.write_text(_render_markdown(items, today))
    print(f"[output] Written to {path}")
    _notify("Daily Digest", f"{len(items)} videos summarized → {path.name}")
    return path
