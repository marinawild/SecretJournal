# ── config.py ────────────────────────────────────────────────────────────────

import os

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR          = os.path.dirname(os.path.abspath(__file__))
ENROLLMENT_DIR    = os.path.join(BASE_DIR, "enrollments")   # one folder per user
AUDIO_TMP_PATH    = os.path.join(BASE_DIR, "temp_audio.wav")

# ── Audio ─────────────────────────────────────────────────────────────────────
SAMPLE_RATE            = 16000   # 16 kHz
ENROLLMENT_AUDIO_SECS  = 6      
VERIFY_AUDIO_SECS      = 4       

# ── Recognition thresholds ────────────────────────────────────────────────────
# Face: DeepFace cosine distance — LOWER = more similar.
FACE_DISTANCE_THRESHOLD  = 0.30

# Voice: resemblyzer cosine similarity — HIGHER = more similar (0.0–1.0).
VOICE_SIM_THRESHOLD      = 0.65

# Both must pass for access to be granted (multi-factor).

CHALLENGE_PHRASE = "Unlock my secret journal."

# ── Display ───────────────────────────────────────────────────────────────────
WINDOW_TITLE = "Biometric Access Control"