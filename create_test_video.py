from moviepy.editor import ColorClip, AudioClip
import numpy as np

def create_test_video():
    # Create a 5-second black screen clip
    video_clip = ColorClip(size=(1080, 1920), color=(0, 0, 0), duration=5)

    # Create a silent audio track
    silent_audio = AudioClip(lambda t: [0, 0], duration=5, fps=44100)
    video_clip = video_clip.set_audio(silent_audio)

    # Write the video file
    video_clip.write_videofile("auto_content/test_video.mp4", fps=24, codec='libx264', audio_codec='aac')

if __name__ == "__main__":
    create_test_video()