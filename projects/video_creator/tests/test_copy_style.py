"""The copy linter: real posts from the account must pass, the generic AI-sounding copy must not."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import copy_style  # noqa: E402
from services.captions import finalize_caption  # noqa: E402

GOOD = [
    # taken from the account's own reels
    ("John Summit בקהל", "מתגנב לקהל ב-EDC Las Vegas",
     "תגידו, זה... זה באמת הוא שם בקהל?! 🤯\n"
     "הדיג'יי הבינלאומי John Summit התגנב לקהל בפסטיבל EDC Las Vegas בתור בליין. "
     "איך הייתם מגיבים אם הייתם רואים אותו?\n#JohnSummit #EDCLasVegas #מסיבות #EDM"),
    ("SOL & SOM חוזר", "10.9, שני ימים", "ב-10.9 זה קורה! פסטיבל SOL & SOM חוזר🤍\n#SOLSOM #מסיבות"),
    ("דרקו בחתונה", "עולה לשיר איתו על הבמה",
     "הייתם מוכנים לשילוב הזה? 🎉\nדיג'יי דרקו הופיע אמש בחתונה, והזמר המפורסם עלה להופיע יחד איתו.\n"
     "#דרקו #מסיבתחתונה #וייבים"),
]


@pytest.mark.parametrize("title,body,caption", GOOD)
def test_real_account_copy_passes(title, body, caption):
    r = copy_style.lint(title, body, caption)
    assert r["problems"] == [], r


def test_the_generated_copy_that_prompted_this_is_rejected():
    r = copy_style.lint("אנרגיה מטורפת! 🔥", "אנרגיה שטרם נראתה. רפאל מרים את האפטר!",
                        "אנרגיה מטורפת כזאת עוד לא ראיתם! 🤯🔥\n#מסיבות")
    assert r["problems"]
    assert any("cliché" in p for p in r["problems"])


@pytest.mark.parametrize("title,body,caption,expect", [
    ("", "b", "c", "title is required"),
    ("t", "", "c", "body is required"),
    ("t", "b", "", "caption is required"),
    ("חייבים לראות", "b", "c #a", "cliché"),
    ("t", "b", "הלילה הכי חם של השנה #a", "cliché"),
    ("t 🔥", "b 🎉", "c #a", "emoji on the sign"),
    ("t", "b", "c 🔥 d 🎉 e 🤯 #a", "emoji in the caption"),
    ("t", "b", "c 🔥🔥 #a", "Repeated emoji"),
    ("t!", "b!", "c #a", "exclamation"),
    ("t", "b", "היי חברים, ערב טוב #a", "היי"),
])
def test_each_rule_fires(title, body, caption, expect):
    problems = copy_style.lint(title, body, caption)["problems"]
    assert any(expect in p for p in problems), problems


def test_disclaimer_and_hashtags_do_not_count_against_the_caption():
    caption = finalize_caption("שאלה אמיתית? 🤔\nעוד משפט עם עובדה.\n#a #b #c #d #e")
    r = copy_style.lint("דרקו בחתונה", "עולה לשיר איתו", caption)
    assert r["problems"] == []                       # the disclaimer's text must not trip the linter


def test_soft_tips_do_not_block():
    r = copy_style.lint("כותרת ארוכה מאוד שיש בה הרבה מילים", "b", "שאלה? #a")
    assert r["problems"] == [] and any("Title is long" in t for t in r["tips"])
    assert any("hashtags" in t for t in copy_style.lint("t", "b", "אין האשטגים כאן")["tips"])


def test_guide_mentions_the_key_rules():
    for needle in ("עובדות קודם", "כותרת", "אימוג", "לא להשתמש בקלישאות"):
        assert needle in copy_style.GUIDE
