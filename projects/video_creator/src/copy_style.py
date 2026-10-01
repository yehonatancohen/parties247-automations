"""
House style for Parties 24/7 copy, plus a linter that rejects the clichés that make AI-written
captions sound like ads. The guide is what the calling model reads; the linter is the safety net.

Calibrated on the account's own posts, e.g.
  "תגידו, זה... זה באמת הוא שם בקהל?! 🤯🕵️ / הדיג'יי הבינלאומי John Summit התגנב לקהל בפסטיבל EDC Las Vegas
   בתור בליין. איך הייתם מגיבים אם הייתם רואים אותו?"
  "ב-10.9 זה קורה! פסטיבל SOL & SOM חוזר🤍"
"""
import re

GUIDE = """\
קול הכתיבה של Parties 24/7
==========================
כתוב כמו מי שמכיר את הסצנה וסיפר לחבר משהו שראה הערב: ישיר, חם, קצר, בעברית מדוברת. לא כמו מודעה.

1. עובדות קודם
   - מי, איפה, מתי, מה קרה. שם אמן / פסטיבל / מקום / תאריך, אבל רק אם הם ידועים מההודעה של המשתמש או
     מ-inspect_source. אסור להמציא שמות, תאריכים או מקומות (לא "רפאל", לא "אמש בתל אביב" בלי מקור).
   - אין עובדות? כתוב על מה שרואים בסרטון בלבד, או שאל את המשתמש שאלה אחת קצרה: "מה קורה בסרטון?".

2. כותרת (על השלט הגדול): 2-4 מילים, עובדתית או שם. לא סיסמה.
   טוב: "John Summit בקהל" | "SOL & SOM חוזר" | "סוכות עם ממוריז" | "דרקו בחתונה"
   רע:  "אנרגיה מטורפת! 🔥" | "הלילה הכי חם" | "חייבים לראות"

3. גוף (שורה מתחת לכותרת): משפט אחד קצר עם מידע קונקרטי, עד ~12 מילים.
   טוב: "מתגנב לקהל ב-EDC Las Vegas" | "10.9, סוכות, שתי במות"
   רע:  "אנרגיה שטרם נראתה" | "תראו מה קורה כשהאפטר מתחיל"

4. כיתוב לאינסטגרם
   - שורה ראשונה שגורמת לעצור: שאלה אמיתית או משפט עם הפתעה אחת. לא "וואו" ולא "לא תאמינו".
   - אחריה 1-2 משפטים עובדתיים (מי / איפה / מה קרה).
   - אפשר שאלה לצופה בסוף ("איך הייתם מגיבים?") כשיש בה היגיון.
   - שורה אחת של 3-5 האשטגים: שם האמן / האירוע / #מסיבות. לא 15.
   - את ההבהרה המשפטית לא כותבים, היא מתווספת לבד.

5. אימוג'י וסימנים: עד שני אימוג'י בכל הכיתוב, אחד בכותרת או בגוף. סימן קריאה אחד לכל היותר.
   בלי שרשראות כמו 🔥🔥🔥 ובלי לפתוח ב"היי" / "שימו לב" / "תראו".

6. לא להשתמש בקלישאות: אנרגיה מטורפת, אנרגיה שטרם נראתה, לא תאמינו, חייבים לראות, הלילה הכי חם,
   בלתי נשכח, מטורף, וואו וואו, עוד לא ראיתם. ולא בתרגומים מאנגלית ("מרים את האפטר").

דוגמאות טובות מהעמוד:
   כיתוב: "תגידו, זה... זה באמת הוא שם בקהל?! 🤯🕵️
           הדיג'יי הבינלאומי John Summit התגנב לקהל בפסטיבל EDC Las Vegas בתור בליין. איך הייתם מגיבים אם
           הייתם רואים אותו?
           #JohnSummit #EDCLasVegas #מסיבות #EDM"
   כיתוב: "ב-10.9 זה קורה! פסטיבל SOL & SOM חוזר🤍"
"""

PROMO_GUIDE = """
קידום בתשלום (kind="promo")
===========================
פוסט שמקדם אירוע, פסטיבל או מסיבה בשביל לקוח. אותו קול ישיר, אבל בנוי כמו הודעה: עובדות, ואז הנעה לפעולה.
בקשת הלקוח מגיעה בדרך כלל במשפט אחד ("הדיג'יי X מגיע לפסטיבל Y"). חלץ ממנה את הפרטים, ואם חסר משהו חיוני
(תאריך, מקום, שמות) שאל את המשתמש שאלה אחת קצרה. אסור להמציא.

מבנה הכיתוב (3 חלקים, בלי האשטגים ובלי הבהרה משפטית):
  1. פתיחה: למה זה שווה עצירה, עובדה אחת מהבריף. חזרה אחרי הפסקה, הופעה חד-פעמית, כרטיסים אחרונים,
     כניסה חינם עד שעה מסוימת, שם גדול באירוע.
  2. הפרטים: יום ותאריך (למשל "ביום שישי הקרוב (9.10)"), מי מופיע, איפה (מקום ועיר). מחיר או שעה אם יש.
  3. הנעה לפעולה, שורה אחת. אם יש אוטומציה להודעות בפרטי: הגיבו ״מילת-קוד״ ונשלח לכם הכל בפרטי.
     אם אין, כתבו לפרטים וכרטיסים בלינק שבביו. מילת הקוד היא שם האמן או העיר, מילה אחת.

על השלט: כותרת = שם האמן / האירוע (2-4 מילים). גוף = היום, התאריך והמקום ("שישי 9.10, אשדוד").
אימוג'י אחד לכל היותר, בסוף. אותם כללי קלישאות כמו תמיד.

דוגמה (בנויה מבריף מדומה):
   בריף: DJ דוגמה, אירוע חוף, אשדוד, שישי 9.10, כרטיסים אחרונים, מילת קוד "אשדוד".
   כותרת: DJ דוגמה באשדוד
   גוף:   שישי 9.10, מצודת-ים
   כיתוב: "אחרי חודשים בחו"ל, DJ דוגמה חוזר לנגן על חוף הים. נותרו כרטיסים אחרונים.
           ביום שישי הקרוב (9.10) במצודת-ים באשדוד, עם אמנים נוספים.
           רוצים פרטים? הגיבו ״אשדוד״ ונשלח לכם הכל בפרטי 🏖️"
"""

BANNED = [
    "אנרגיה מטורפת", "אנרגיה שטרם נראתה", "שטרם נראתה", "לא תאמינו", "חייבים לראות", "הלילה הכי חם",
    "בלתי נשכח", "מטורף", "וואו וואו", "עוד לא ראיתם", "עוד לא ראית", "שובר את האינטרנט", "הכי שווה",
]

_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆❤⬛⬜]")
_HASHTAG = re.compile(r"#\w+")
_DISCLAIMER_START = "הבהרה:"
_DISCLAIMER_MARK = "הבהרה: הסרטונים"


def _emoji_count(text: str) -> int:
    return len(_EMOJI.findall(text))


def _strip_caption(caption: str) -> tuple[str, int]:
    """Caption text without the hashtag line(s) and without the disclaimer, plus the hashtag count."""
    tags = len(_HASHTAG.findall(caption))
    kept = []
    for line in caption.splitlines():
        s = line.strip()
        if s == "-" or s.startswith(_DISCLAIMER_START):
            continue
        if s and not _HASHTAG.sub("", s).strip():      # a line made only of hashtags
            continue
        kept.append(line)
    return "\n".join(kept).strip(), tags


def lint(title: str | None, body: str | None, caption: str | None,
         kind: str = "standard", cta_keyword: str | None = None) -> dict:
    """
    Returns {'problems': [...], 'tips': [...]}. 'problems' must be fixed before rendering;
    'tips' are softer style notes.
    """
    problems, tips = [], []
    title, body, caption = (title or "").strip(), (body or "").strip(), (caption or "").strip()

    for name, val in (("title", title), ("body", body), ("caption", caption)):
        if not val:
            problems.append(f"{name} is required: write it yourself (see get_copy_guide).")
    if problems:
        return {"problems": problems, "tips": tips}

    text_caption, tag_count = _strip_caption(caption)
    all_text = {"title": title, "body": body, "caption": text_caption}

    for name, val in all_text.items():
        hits = [b for b in BANNED if b in val]
        hits = [h for h in hits if not any(h != o and h in o for o in hits)]   # report the longest match only
        if hits:
            problems.append(f"{name} uses a cliché ({', '.join(hits)}). Say what actually happens or who is there.")

    if _emoji_count(title) + _emoji_count(body) > 1:
        problems.append("Too many emoji on the sign: at most one in the title and body together.")
    if _emoji_count(text_caption) > 2:
        problems.append("Too many emoji in the caption: at most two.")
    if re.search(r"([\U0001F300-\U0001FAFF☀-➿])\1", caption):
        problems.append("Repeated emoji (like 🔥🔥): use one, or none.")
    if title.count("!") + body.count("!") > 1 or text_caption.count("!") > 2 or "!!" in caption:
        problems.append("Too many exclamation marks (at most one on the sign, two in the caption).")
    if re.match(r"^(היי|הי|שימו לב|תראו)\b", text_caption):
        problems.append("Do not open the caption with 'היי / שימו לב / תראו'.")

    if len(title.split()) > 5:
        tips.append("Title is long for the sign: 2-4 words works best.")
    if len(body) > 90:
        tips.append("Body is long: one short line with a concrete fact.")
    if kind == "promo":
        extra = lint_promo(title, body, caption, cta_keyword)
        problems += extra["problems"]
        tips += extra["tips"]
    elif tag_count == 0:
        tips.append("Add a final line of 3-5 relevant hashtags.")
    elif tag_count > 8:
        tips.append("Too many hashtags: 3-5 relevant ones.")

    return {"problems": problems, "tips": tips}


_QUOTES = '״"\'“”'
_DATE = re.compile(r"\d{1,2}[./]\d{1,2}")


def lint_promo(title: str, body: str, caption: str, cta_keyword: str | None) -> dict:
    """Extra checks for paid promotion posts: they must carry the facts a viewer needs to act."""
    problems, tips = [], []
    if not (_DATE.search(caption) or _DATE.search(body)):
        problems.append("A promo must say when: include the date (for example 9.10) and the weekday.")
    if cta_keyword:
        kw = cta_keyword.strip()
        if not re.search(f"[{_QUOTES}]{re.escape(kw)}[{_QUOTES}]", caption):
            problems.append(f"The call to action must quote the keyword: הגיבו ״{kw}״ ...")
    else:
        tips.append("No cta_keyword: end with a clear call to action (for example details and tickets via the "
                    "link in the bio).")
    if re.search(r"#\w+", caption):
        tips.append("Promos usually go without hashtags.")
    return {"problems": problems, "tips": tips}
