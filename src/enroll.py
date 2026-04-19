# ── enrollment.py ─────────────────────────────────────────────────────────────
"""
One-time enrollment for a new user with Personalization Questionnaire.
Run directly:  python enroll.py

Captures:
  - 3 face photos (different angles)
  - 1 voice sample (user speaks the challenge phrase)
  - Personal details (Age, Gender, Hobby, Study Area, etc.)

Saves to:  enrollments/<name>/
"""

import os
import json
import time
import numpy as np
import cv2
import sounddevice as sd
from scipy.io.wavfile import write as wav_write
from resemblyzer import VoiceEncoder, preprocess_wav
from pathlib import Path

from config import (
    ENROLLMENT_DIR,
    AUDIO_TMP_PATH,
    SAMPLE_RATE,
    ENROLLMENT_AUDIO_SECS,
    CHALLENGE_PHRASE,
    WINDOW_TITLE,
)

encoder = VoiceEncoder()

def _record_audio(duration: int) -> None:
    print(f"  [audio] Recording {duration}s — speak now...")
    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    wav_write(AUDIO_TMP_PATH, SAMPLE_RATE,
              (recording * 32767).astype(np.int16))
    print("  [audio] Done.")

def _embed_voice(audio_path: str) -> np.ndarray:
    wav = preprocess_wav(Path(audio_path))
    return encoder.embed_utterance(wav)

def enroll(name: str) -> bool:
    """
    Interactive enrollment with a personalized questionnaire.
    """
    user_dir = os.path.join(ENROLLMENT_DIR, name.lower().replace(" ", "_"))
    os.makedirs(user_dir, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: cannot open webcam.")
        return False

    print(f"\n{'='*55}")
    print(f"  ENROLLING: {name}")
    print(f"  Capture: 3 Photos -> 1 Voice Sample -> Personalization")
    print(f"{'='*55}")

    # ── Phase 1: Face capture ─────────────────────────────────────────────────
    face_paths = []
    instructions = [
        "Look straight at the camera",
        "Turn slightly LEFT",
        "Turn slightly RIGHT",
    ]

    for shot_idx, instruction in enumerate(instructions):
        print(f"\n  Face {shot_idx + 1}/3: {instruction}")
        print("  Press SPACE to capture.")

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            display = frame.copy()

            cv2.putText(display, f"ENROLLMENT — {name}",
                        (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 220), 2)
            cv2.putText(display, instruction,
                        (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.putText(display, f"Shot {shot_idx+1}/3 — press SPACE",
                        (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)
            cv2.imshow(WINDOW_TITLE, display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                path = os.path.join(user_dir, f"face_{shot_idx}.jpg")
                cv2.imwrite(path, frame)
                face_paths.append(path)
                print(f"  Saved {path}")

                flash = frame.copy()
                cv2.rectangle(flash, (0, 0), (flash.shape[1], flash.shape[0]),
                              (0, 220, 0), 8)
                cv2.imshow(WINDOW_TITLE, flash)
                cv2.waitKey(300)
                break
            elif key == ord("q"):
                cap.release()
                cv2.destroyAllWindows()
                return False

    # ── Phase 2: Voice enrollment ─────────────────────────────────────────────
    phrase = CHALLENGE_PHRASE.format(name=name)
    print(f"\n  Voice enrollment.")
    print(f"  When prompted, say: \"{phrase}\"")
    print("  Press SPACE to start recording.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        display = frame.copy()
        cv2.putText(display, "VOICE ENROLLMENT",
                    (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 220), 2)
        cv2.putText(display, f'Say: "{phrase}"',
                    (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(display, "Press SPACE to record",
                    (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)
        cv2.imshow(WINDOW_TITLE, display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            import threading
            stop_flag = {"done": False}

            def _show_recording():
                start = time.time()
                while not stop_flag["done"]:
                    r, f = cap.read()
                    if r:
                        f = cv2.flip(f, 1)
                        remaining = max(0, ENROLLMENT_AUDIO_SECS - int(time.time() - start))
                        cv2.putText(f, f"RECORDING... {remaining}s",
                                    (20, 50), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.8, (0, 0, 220), 2)
                        if int(time.time() * 2) % 2 == 0:
                            cv2.circle(f, (30, 90), 10, (0, 0, 220), -1)
                        cv2.imshow(WINDOW_TITLE, f)
                    cv2.waitKey(1)

            display_thread = threading.Thread(target=_show_recording, daemon=True)
            display_thread.start()
            _record_audio(ENROLLMENT_AUDIO_SECS)
            stop_flag["done"] = True
            display_thread.join()
            break
        elif key == ord("q"):
            cap.release()
            cv2.destroyAllWindows()
            return False

    # ── Phase 3: Personalization Questionnaire ────────────────────────────────
    cap.release()
    cv2.destroyAllWindows()

    print(f"\n{'─'*20} PERSONALIZATION {'─'*20}")
    print(f"  Please answer a few questions to help Gemini personalize your prompts:")
    
    # Collecting the data points you requested
    user_data = {
        "name":           name,
        "age":            input("  Age: ").strip(),
        "gender":         input("  Gender: ").strip(),
        "favorite_color": input("  Favorite Color: ").strip(),
        "favorite_food":  input("  Favorite Food: ").strip(),
        "favorite_sport": input("  Favorite Sport: ").strip(),
        "study_area":     input("  Area of Study/Major: ").strip(),
        "hobby":          input("  Primary Hobby: ").strip(),
    }

    # ── Finalizing Data ───────────────────────────────────────────────────────
    print("\n  Computing voice embedding...")
    embedding = _embed_voice(AUDIO_TMP_PATH)
    emb_path  = os.path.join(user_dir, "voice_embedding.npy")
    np.save(emb_path, embedding)

    # Combine Questionnaire and System Metadata
    meta = {
        **user_data,
        "face_paths": face_paths,
        "voice_path": emb_path,
    }
    
    with open(os.path.join(user_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n  Enrollment complete for '{name}'.")
    print(f"  Stored in: {user_dir}\n")
    return True

if __name__ == "__main__":
    name = input("Enter the name to enroll: ").strip()
    if not name:
        print("Name cannot be empty.")
    else:
        enroll(name)