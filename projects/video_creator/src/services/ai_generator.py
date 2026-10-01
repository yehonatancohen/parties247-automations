import google.generativeai as genai
from config import Config

class AIGenerator:
    def __init__(self):
        # Initialize Gemini
        self.gemini_available = False
        if Config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                self.model = genai.GenerativeModel('gemini-2.5-flash')
                self.gemini_available = True
                print("✨ Gemini AI engine initialized.")
            except Exception as e:
                print(f"⚠️ Failed to initialize Gemini: {e}")
        else:
            print("⚠️ No GEMINI_API_KEY found in config.")

    def generate_description(self, user_prompt: str, video_info: dict) -> str:
        if not self.gemini_available:
            raise RuntimeError("Gemini unavailable (missing GEMINI_API_KEY).")

        # Construct context
        context = f"""
        VIDEO METADATA:
        - Title: {video_info.get('title', 'N/A')}
        - URL: {video_info.get('url', 'N/A')}
        - Uploader: {video_info.get('uploader', 'N/A')}
        - Tags: {', '.join(video_info.get('tags', []))}
        - Original Description: {video_info.get('description', 'N/A')[:1000]}
        
        USER'S TEXT FOR VIDEO:
        {user_prompt}
        """
        
        prompt = f"""
        You are the official caption-generator for 'Parties247'. 
        Your goal is to create a viral Hebrew caption based ONLY on the provided info.

        STRICT RULES:
        1. DO NOT invent facts. DO NOT mention DJs, artists, cities, or events (like "David Guetta") unless they are explicitly in the metadata or user text below.
        2. DO NOT try to "research" the link. Use only the text provided.
        3. Voice: a friend from the scene telling you what he just saw. Concrete, conversational Hebrew, short.
           State who/where/what happened ONLY if it is in the info below. At most 2 emoji, at most 1 exclamation
           mark. NEVER use hype cliches such as: אנרגיה מטורפת, לא תאמינו, חייבים לראות, הלילה הכי חם, מטורף.
        4. Sections: Exactly four sections separated by a single line containing only "-".

        STRUCTURE:
        Section 1: HOOK (One sharp line in spoken Hebrew + 1-2 emojis)
        -
        Section 2: EXPLANATION (0-3 short sentences describing the video content based on the text below. If unknown, leave empty.)
        -
        Section Section 3: DISCLAIMER (EXACTLY this sentence: הבהרה: הסרטונים בעמוד Parties 24/7 נאספים ממקורות שונים, ולא תמיד ידוע לנו מי צילם או מי בעל הזכויות. אם אתה/את הצלם/ת או בעל/ת הזכויות—שלח/י לנו הודעה עם פרטי קרדיט ונוסיף. אם תרצו להסיר תוכן, נטפל בזה בהקדם.)
        -
        Section 4: HASHTAGS (5 relevant hashtags on one line)

        INFO TO USE:
        {context}
        """
        
        # Errors propagate on purpose: callers fall back to the user's own text, and
        # an error string must never be mistaken for a publishable caption.
        print("🧠 Asking Gemini for description...")
        response = self.model.generate_content(prompt)
        if not (response and response.text and response.text.strip()):
            raise RuntimeError("Gemini returned an empty response.")
        return response.text.strip()

    def generate_copy(self, video_info: dict) -> dict:
        """Fallback when the caller supplies no title/body: returns {'title', 'body'} in Hebrew."""
        import json
        if not self.gemini_available:
            raise RuntimeError("Gemini unavailable (missing GEMINI_API_KEY).")

        prompt = f"""
        You write the on-screen text for a nightlife video for 'Parties247' (Israel).
        Use ONLY the metadata below. Do not invent artists, venues, dates or cities.
        Return JSON only: {{"title": "...", "body": "..."}}
        - title: Hebrew, 2-4 words, factual (a name or what happened), no slogans, no hype words, at most 1 emoji.
        - body: Hebrew, max 12 words, one short concrete fact. If the metadata has no concrete fact, say what is
          visible in generic terms (e.g. the crowd, the stage) and never name people or places.

        METADATA:
        - Title: {video_info.get('title', 'N/A')}
        - Uploader: {video_info.get('uploader', 'N/A')}
        - Tags: {', '.join(video_info.get('tags', []) or [])}
        - Description: {str(video_info.get('description', 'N/A'))[:600]}
        """
        response = self.model.generate_content(
            prompt, generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        title, body = str(data.get("title", "")).strip(), str(data.get("body", "")).strip()
        if not title:
            raise RuntimeError("Gemini returned no title.")
        return {"title": title, "body": body}
