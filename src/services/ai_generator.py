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
            return "AI Description Unavailable (Missing API Key)."

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
        3. Tone: Young, high-energy, nightlife, FOMO (ages 16-25).
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
        
        try:
            print("🧠 Asking Gemini for description...")
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
            return "AI returned empty response."
        except Exception as e:
            print(f"⚠️ Gemini error: {e}")
            return "Error generating description with AI."
