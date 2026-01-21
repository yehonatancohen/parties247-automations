from bidi.algorithm import get_display
import emoji

def process_hebrew_with_emojis(text: str) -> str:
    """
    Processes a string containing both Hebrew text and emojis.
    Only the Hebrew parts are processed for RTL display, while emojis are preserved.
    """
    # Split the text into parts based on emojis
    parts = []
    last_end = 0
    for match in emoji.get_emoji_regexp().finditer(text):
        # Add the text part before the emoji
        if match.start() > last_end:
            parts.append({'type': 'text', 'content': text[last_end:match.start()]})
        # Add the emoji part
        parts.append({'type': 'emoji', 'content': match.group()})
        last_end = match.end()
    # Add any remaining text part
    if last_end < len(text):
        parts.append({'type': 'text', 'content': text[last_end:]})

    # Process only the text parts
    processed_parts = []
    for part in parts:
        if part['type'] == 'text':
            processed_parts.append(get_display(part['content'], base_dir='R'))
        else:
            processed_parts.append(part['content'])
            
    # Re-join the parts in reverse order for RTL visual rendering
    return ''.join(reversed(processed_parts))

class TextUtils:
    @staticmethod
    def process_hebrew(text: str) -> str:
        """
        Handles RTL issues for Pillow/MoviePy.
        Strategy: Visual (Legacy).
        We force Pillow's Basic layout (by disabling Raqm in graphics.py),
        so we need full Visual text (reversed).
        """
        return process_hebrew_with_emojis(text)