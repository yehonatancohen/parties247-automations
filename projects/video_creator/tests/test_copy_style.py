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
    # an anticipation question with one emoji, and a body that explains the unfamiliar name
    ("להיט חדש בדרך?😮", "הצמד Club de Combat סגר את הסט עם MFG, טראק שעוד לא שוחרר",
     "איך סוגרים סט? עם טראק שעוד לא יצא 👀\n"
     "הצמד Club de Combat סגר את הסט שלו ב-Factory Town עם טראק שעדיין לא שוחרר: MFG.\n"
     "#ClubDeCombat #Bonafique #FactoryTown #EDM #מסיבות"),
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


# ---------------------------------------------------------------- promo mode

PROMO_OK = ("DJ דוגמה באשדוד", "שישי 9.10, מצודת-ים",
            "אחרי חודשים בחו\"ל, DJ דוגמה חוזר לנגן על חוף הים. נותרו כרטיסים אחרונים.\n"
            "ביום שישי הקרוב (9.10) במצודת-ים באשדוד, עם אמנים נוספים.\n"
            "רוצים פרטים? הגיבו ״אשדוד״ ונחזור אליכם 🏖️")


def test_promo_example_passes():
    r = copy_style.lint(*PROMO_OK, kind="promo", cta_keyword="אשדוד")
    assert r["problems"] == [] and r["tips"] == [], r


def test_promo_needs_a_date_and_the_keyword():
    t, b, c = PROMO_OK
    no_date = c.replace("(9.10) ", "")
    assert any("when" in p for p in copy_style.lint(t, "בים", no_date, "promo", "אשדוד")["problems"])
    no_kw = c.replace("הגיבו ״אשדוד״", "כתבו לנו")
    assert any("keyword" in p for p in copy_style.lint(t, b, no_kw, "promo", "אשדוד")["problems"])


def test_promo_still_rejects_cliches_and_standard_mode_is_unchanged():
    t, b, c = PROMO_OK
    bad = c.replace("חוזר לנגן", "מגיע לאירוע מטורף")
    assert any("cliché" in p for p in copy_style.lint(t, b, bad, "promo", "אשדוד")["problems"])
    # a plain post without a date is fine in standard mode
    assert copy_style.lint("t", "b", "שאלה? #a")["problems"] == []


def test_promo_has_no_disclaimer_and_standard_does():
    from services.captions import DISCLAIMER
    assert finalize_caption("טקסט", promo=True) == "טקסט"
    assert DISCLAIMER in finalize_caption("טקסט")


def test_promo_without_keyword_only_gets_a_tip():
    t, b, c = PROMO_OK
    r = copy_style.lint(t, b, c.replace("הגיבו ״אשדוד״ ונחזור אליכם", "פרטים בביו"), "promo", None)
    assert r["problems"] == [] and any("call to action" in x for x in r["tips"])


def test_promo_length_and_dm_promise_tips():
    t, b, c = PROMO_OK
    assert not any("chars" in x for x in copy_style.lint(t, b, c, "promo", "אשדוד")["tips"])
    short = copy_style.lint(t, b, "9.10 הגיבו ״אשדוד״", "promo", "אשדוד")
    assert any("only" in x for x in short["tips"])
    long_ = copy_style.lint(t, b, c + " " + "מילה " * 80, "promo", "אשדוד")
    assert any("Tighten" in x for x in long_["tips"])
    promised = copy_style.lint(t, b, c.replace("ונחזור אליכם", "ונשלח לכם הכל בפרטי"), "promo", "אשדוד")
    assert any("no DM automation" in x for x in promised["tips"])
    assert promised["problems"] == []              # a tip, not a blocker


def test_promo_guide_carries_the_measured_findings():
    for needle in ("24 פוסטים", "חציון", "מילת הקוד", "בדיקה עצמית"):
        assert needle in copy_style.PROMO_GUIDE


def test_raqm_text_is_pinned_right_to_left():
    """With Raqm the text is not reordered, so a line opening with a Latin name needs a leading RLM."""
    from services.text_utils import RLM, TextUtils
    assert TextUtils.process_hebrew("MFG, יחד עם Bonafique", reorder_content=False).startswith(RLM)
    out = TextUtils.process_hebrew("להיט חדש בדרך?😮", reorder_content=False)
    assert out == "😮" + RLM + "להיט חדש בדרך?"
    # the legacy (no Raqm) path reorders the characters itself and must stay untouched
    assert RLM not in TextUtils.process_hebrew("דרקו בחתונה", reorder_content=True)
