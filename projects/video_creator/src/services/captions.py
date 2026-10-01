"""Caption helpers shared by the headless pipeline."""

# Must stay identical to the sentence in AIGenerator's prompt.
DISCLAIMER = (
    "הבהרה: הסרטונים בעמוד Parties 24/7 נאספים ממקורות שונים, ולא תמיד ידוע לנו מי צילם או מי בעל הזכויות. "
    "אם אתה/את הצלם/ת או בעל/ת הזכויות—שלח/י לנו הודעה עם פרטי קרדיט ונוסיף. "
    "אם תרצו להסיר תוכן, נטפל בזה בהקדם."
)

SEPARATOR = "\n-\n"


def finalize_caption(caption: str) -> str:
    """
    Guarantee the legal disclaimer is present exactly once, inserted before a trailing
    hashtag line when there is one. The calling model never has to copy it.
    """
    caption = (caption or "").strip()
    if DISCLAIMER in caption:
        return caption

    lines = caption.splitlines()
    if lines and lines[-1].lstrip().startswith("#"):
        head = "\n".join(lines[:-1]).rstrip()
        parts = [p for p in (head, DISCLAIMER, lines[-1].strip()) if p]
        return SEPARATOR.join(parts)
    return SEPARATOR.join(p for p in (caption, DISCLAIMER) if p)
