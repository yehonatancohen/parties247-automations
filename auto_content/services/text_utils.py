from bidi.algorithm import get_display

class TextUtils:
    @staticmethod
    def process_hebrew(text: str) -> str:
        """Handles RTL issues for Pillow/MoviePy"""
        # arabic_reshaper is removed as it can interfere with emojis and is not strictly needed for Hebrew.
        # We enforce base_dir='R' to ensure consistent RTL positioning for punctuation and emojis.
        return get_display(text, base_dir='R')