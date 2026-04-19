# ── access_control.py ────────────────────────────────────────────────────────
"""
Secret Journal Access Control — Face + Voice Recognition
====================================================

State machine:

  IDLE
    │  press E → enroll a new user
    │  press ENTER → begin verification
  GET_NAME   user types their name
  CHALLENGE   display the phrase to speak aloud (3 s countdown)
  RECORDING   capture face frames + voice simultaneously
  VERIFYING   DeepFace + resemblyzer comparison (background thread)
  ACCESS_GRANTED  or  ACCESS_DENIED  (4 s display, then reset to IDLE)
"""

import cv2
import threading
import time
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as wav_write
from enum import Enum, auto

from config import (
    SAMPLE_RATE,
    AUDIO_TMP_PATH,
    VERIFY_AUDIO_SECS,
    CHALLENGE_PHRASE,
    WINDOW_TITLE,
)
from recognizer import load_enrollments, verify
from enroll import enroll


# ── States ────────────────────────────────────────────────────────────────────
class State(Enum):
    IDLE            = auto()
    GET_NAME        = auto()
    CHALLENGE       = auto()
    RECORDING       = auto()
    VERIFYING       = auto()
    ACCESS_GRANTED  = auto()
    ACCESS_DENIED   = auto()


# ── Colours (BGR) ─────────────────────────────────────────────────────────────
WHITE  = (255, 255, 255)
GREEN  = (0,   220,  80)
RED    = (50,   50, 220)
YELLOW = (0,   220, 220)
ORANGE = (0,   160, 255)
GRAY   = (160, 160, 160)
CYAN   = (220, 220,   0)


# ── UI helpers ────────────────────────────────────────────────────────────────
def put(frame, text, y, color=WHITE, scale=0.65, thickness=1, x=30):
    cv2.putText(frame, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color,
                thickness, cv2.LINE_AA)


def progress_bar(frame, pct, color=CYAN):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, h - 10), (w, h), (40, 40, 40), -1)
    cv2.rectangle(frame, (0, h - 10), (int(w * pct), h), color, -1)


def status_label(frame, text):
    h, w = frame.shape[:2]
    cv2.putText(frame, text, (w - 230, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, GRAY, 1, cv2.LINE_AA)


def tint(frame, color_bgr, alpha=0.25):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]),
                  color_bgr, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


# ── Audio ─────────────────────────────────────────────────────────────────────
def record_audio_blocking(duration: int = VERIFY_AUDIO_SECS) -> None:
    rec = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                 channels=1, dtype="float32")
    sd.wait()
    wav_write(AUDIO_TMP_PATH, SAMPLE_RATE, (rec * 32767).astype(np.int16))


# ── Main loop ─────────────────────────────────────────────────────────────────
def run():
    enrollments = load_enrollments()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: cannot open webcam.")
        return

    state            = State.IDLE
    state_entered_at = time.time()
    typed_name       = ""
    claimed_name     = ""
    challenge_phrase = ""
    captured_frames  = []
    verify_result    = {}
    audio_thread     = None

    print(f"\n{'='*55}")
    print("  SECRET JOURNAL ACCESS CONTROL")
    print("  ENTER = verify    E = enroll new user    Q = quit")
    print(f"{'='*55}\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame   = cv2.flip(frame, 1)
        elapsed = time.time() - state_entered_at

        # ── IDLE ──────────────────────────────────────────────────────────────
        if state == State.IDLE:
            enrolled_names = [r["name"] for r in enrollments]
            put(frame, "SECRET JOURNAL ACCESS CONTROL", 40,  CYAN,   0.8, 2)
            put(frame, "ENTER  — verify identity", 85,  WHITE,  0.58)
            put(frame, "E      — enroll new user",  115, WHITE,  0.58)
            put(frame, "Q      — quit",             145, GRAY,   0.50)
            if enrolled_names:
                put(frame, f"Enrolled: {', '.join(enrolled_names)}", 185, GRAY, 0.46)
            else:
                put(frame, "No enrolled users — press E first.", 185, YELLOW, 0.50)
            status_label(frame, "IDLE")

        # ── GET NAME ──────────────────────────────────────────────────────────
        elif state == State.GET_NAME:
            put(frame, "WHO ARE YOU?",              40,  CYAN,   0.8, 2)
            put(frame, "Type your name, press ENTER.", 85, WHITE, 0.55)
            put(frame, f"> {typed_name}_",          125, YELLOW, 0.70, 2)
            status_label(frame, "IDENTIFY")

        # ── CHALLENGE ─────────────────────────────────────────────────────────
        elif state == State.CHALLENGE:
            countdown = max(0, 3 - int(elapsed))
            put(frame, "SPEAK THIS PHRASE:",        40,  CYAN,   0.72, 2)
            # Word-wrap the phrase across two lines if long
            words = challenge_phrase.split()
            mid   = len(words) // 2
            put(frame, " ".join(words[:mid]),       85,  WHITE,  0.55)
            put(frame, " ".join(words[mid:]),       115, WHITE,  0.55)
            put(frame, f"Recording in {countdown}...", 165, ORANGE, 0.65, 2)
            progress_bar(frame, elapsed / 3.0, ORANGE)
            status_label(frame, "GET READY")

            if elapsed >= 3.0:
                captured_frames = []
                audio_thread = threading.Thread(
                    target=record_audio_blocking, args=(VERIFY_AUDIO_SECS,)
                )
                audio_thread.start()
                state            = State.RECORDING
                state_entered_at = time.time()

        # ── RECORDING ─────────────────────────────────────────────────────────
        elif state == State.RECORDING:
            progress = min(elapsed / VERIFY_AUDIO_SECS, 1.0)
            remaining = max(0, VERIFY_AUDIO_SECS - int(elapsed))
            put(frame, "SPEAK NOW",                 40,  RED,    0.9, 3)
            put(frame, challenge_phrase[:50],        85,  WHITE,  0.50)
            put(frame, f"{remaining}s remaining",   130, ORANGE, 0.65, 2)
            if int(elapsed * 2) % 2 == 0:
                cv2.circle(frame, (30, 170), 10, RED, -1)
            captured_frames.append(frame.copy())
            progress_bar(frame, progress, RED)
            status_label(frame, "RECORDING")

            if elapsed >= VERIFY_AUDIO_SECS + 0.3:
                if audio_thread:
                    audio_thread.join()     # ensure WAV fully written

                # Pick the sharpest frame (highest Laplacian variance = least blur)
                best_frame = max(
                    captured_frames,
                    key=lambda f: cv2.Laplacian(
                        cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F
                    ).var()
                )

                verify_result    = {}
                state            = State.VERIFYING
                state_entered_at = time.time()

                def _run_verify():
                    nonlocal verify_result
                    verify_result = verify(
                        best_frame, AUDIO_TMP_PATH,
                        enrollments, claimed_name=claimed_name
                    )

                threading.Thread(target=_run_verify, daemon=True).start()

        # ── VERIFYING ─────────────────────────────────────────────────────────
        elif state == State.VERIFYING:
            put(frame, "VERIFYING...",              40,  YELLOW, 0.8, 2)
            put(frame, "Comparing face + voice.",   85,  GRAY,   0.52)
            progress_bar(frame, min(elapsed / 4.0, 0.95), YELLOW)
            status_label(frame, "VERIFYING")

            if verify_result:
                print(f"\n  RESULT: {'GRANTED' if verify_result['granted'] else 'DENIED'}")
                print(f"  {verify_result['reason']}\n")
                state = State.ACCESS_GRANTED if verify_result["granted"] \
                        else State.ACCESS_DENIED
                state_entered_at = time.time()

        # ── ACCESS GRANTED ────────────────────────────────────────────────────
        elif state == State.ACCESS_GRANTED:
            tint(frame, (0, 60, 0), 0.30)
            put(frame, "ACCESS GRANTED",            55,  GREEN,  1.1, 3)
            put(frame, f"Welcome, {verify_result.get('name', '')}!", 115, WHITE, 0.65, 2)
            put(frame, f"Face:  dist {verify_result.get('face_distance','?')}",
                165, GRAY, 0.48)
            put(frame, f"Voice: sim  {verify_result.get('voice_similarity','?')}",
                190, GRAY, 0.48)
            progress_bar(frame, min(elapsed / 4.0, 1.0), GREEN)
            status_label(frame, "GRANTED")

            if elapsed > 4.0:
                enrollments      = load_enrollments()   # refresh in case of new enroll
                state            = State.IDLE
                verify_result    = {}
                state_entered_at = time.time()

        # ── ACCESS DENIED ─────────────────────────────────────────────────────
        elif state == State.ACCESS_DENIED:
            tint(frame, (0, 0, 80), 0.30)
            put(frame, "ACCESS DENIED",             55,  RED,    1.1, 3)
            reason = verify_result.get("reason", "Identity could not be verified.")
            # Split reason across lines
            for li, chunk in enumerate([reason[i:i+52] for i in range(0, len(reason), 52)]):
                put(frame, chunk, 115 + li * 28, WHITE, 0.46)
            progress_bar(frame, min(elapsed / 4.0, 1.0), RED)
            status_label(frame, "DENIED")

            if elapsed > 4.0:
                state            = State.IDLE
                verify_result    = {}
                state_entered_at = time.time()

        # ── Render + keys ─────────────────────────────────────────────────────
        cv2.imshow(WINDOW_TITLE, frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == 13:   # Enter
            if state == State.IDLE:
                if not enrollments:
                    print("  No enrolled users. Press E to enroll first.")
                else:
                    typed_name       = ""
                    state            = State.GET_NAME
                    state_entered_at = time.time()

            elif state == State.GET_NAME:
                if typed_name.strip():
                    claimed_name     = typed_name.strip()
                    challenge_phrase = CHALLENGE_PHRASE.format(name=claimed_name)
                    state            = State.CHALLENGE
                    state_entered_at = time.time()
                    print(f"  Claimed identity: {claimed_name}")

        elif key == ord("e") and state == State.IDLE:
            cap.release()
            cv2.destroyAllWindows()
            name = input("\nEnter name to enroll: ").strip()
            if name:
                enroll(name)
            # Reopen camera and reload enrollments
            cap         = cv2.VideoCapture(0)
            enrollments = load_enrollments()

        elif state == State.GET_NAME:
            if key == 8 and typed_name:          # backspace
                typed_name = typed_name[:-1]
            elif 32 <= key <= 126:               # printable ASCII
                typed_name += chr(key)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()