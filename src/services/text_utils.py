from bidi.algorithm import get_display

class TextUtils:
    @staticmethod
    def process_hebrew(text: str) -> str:
        """
        Handles RTL issues for Pillow/MoviePy.
        Strategy: Visual (Legacy).
        We force Pillow's Basic layout (by disabling Raqm in graphics.py),
        so we need full Visual text (reversed).
        """
        return get_display(text, base_dir='R')