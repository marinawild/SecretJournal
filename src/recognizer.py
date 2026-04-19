# ── recognizer.py ─────────────────────────────────────────────────────────────

import os
import json
import numpy as np
import shutil
from pathlib import Path
from deepface import DeepFace
import subprocess
import tempfile
from resemblyzer import VoiceEncoder, preprocess_wav

from config import (
    ENROLLMENT_DIR,
    FACE_DISTANCE_THRESHOLD,
    VOICE_SIM_THRESHOLD,
)

encoder = VoiceEncoder()


# ── ffmpeg availability check (run once at startup) ───────────────────────────
def _check_ffmpeg() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False

FFMPEG_AVAILABLE = _check_ffmpeg()
if not FFMPEG_AVAILABLE:
    print(
        "\n⚠️  WARNING: ffmpeg was NOT found on your PATH.\n"
        "   Voice verification will fail for browser audio.\n"
        "   Fix: download ffmpeg from https://ffmpeg.org/download.html\n"
        "   and add it to your system PATH, then restart the server.\n"
    )


# ── Load enrollments ──────────────────────────────────────────────────────────
def load_enrollments() -> list[dict]:
    if not os.path.isdir(ENROLLMENT_DIR):
        return []

    records = []

    for user_dir in os.listdir(ENROLLMENT_DIR):
        meta_path = os.path.join(ENROLLMENT_DIR, user_dir, "meta.json")
        emb_path  = os.path.join(ENROLLMENT_DIR, user_dir, "voice_embedding.npy")

        if not os.path.isfile(meta_path) or not os.path.isfile(emb_path):
            continue

        with open(meta_path) as f:
            meta = json.load(f)

        records.append({
            "name": meta["name"],
            "face_paths": meta["face_paths"],
            "voice_embedding": np.load(emb_path),
        })

    print(f"  [recognizer] Loaded {len(records)} enrollment(s): "
          f"{[r['name'] for r in records]}")
    return records


# ── Face verification ─────────────────────────────────────────────────────────
def verify_face(live_frame, enrollments: list[dict]) -> dict:

    best = {
        "verified": False,
        "name": None,
        "distance": 1.0,
        "threshold": FACE_DISTANCE_THRESHOLD
    }

    for record in enrollments:
        for face_path in record["face_paths"]:
            if not os.path.isfile(face_path):
                continue

            try:
                result = DeepFace.verify(
                    img1_path=live_frame,
                    img2_path=face_path,
                    model_name="Facenet512",
                    detector_backend="retinaface",
                    enforce_detection=False,
                    silent=True,
                )

                dist = result["distance"]

                if dist < best["distance"]:
                    best["distance"] = dist
                    best["name"] = record["name"]
                    best["verified"] = dist < FACE_DISTANCE_THRESHOLD

            except Exception as e:
                print(f"  [face] Error comparing to {record['name']}: {e}")

    return best


# ── Voice verification ────────────────────────────────────────────────────────
def verify_voice(audio_path: str, enrollments: list[dict],
                 claimed_name: str | None = None) -> dict:

    best = {
        "verified": False,
        "name": None,
        "similarity": 0.0,
        "threshold": VOICE_SIM_THRESHOLD
    }

    if not FFMPEG_AVAILABLE:
        print("  [voice] Skipping — ffmpeg not found. Install ffmpeg and add to PATH.")
        best["error"] = "ffmpeg not installed"
        return best

    clean_wav = None
    try:
        # ── convert any browser audio format → clean 16 kHz mono wav ──
        fd, clean_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        proc = subprocess.run([
            "ffmpeg", "-y",
            "-i", audio_path,
            "-ac", "1",
            "-ar", "16000",
            "-sample_fmt", "s16",
            clean_wav
        ], capture_output=True)

        if proc.returncode != 0:
            print("  [voice] ffmpeg error:")
            print(proc.stderr.decode(errors="replace"))
            return best

        if not os.path.exists(clean_wav) or os.path.getsize(clean_wav) == 0:
            print("  [voice] ffmpeg produced an empty file.")
            return best

        wav = preprocess_wav(Path(clean_wav))
        live_emb = encoder.embed_utterance(wav)

    except Exception as e:
        print(f"  [voice] Failed to embed audio: {e}")
        return best

    finally:
        if clean_wav and os.path.exists(clean_wav):
            try:
                os.remove(clean_wav)
            except Exception:
                pass

    targets = enrollments
    if claimed_name:
        targets = [
            r for r in enrollments
            if r["name"].lower() == claimed_name.lower()
        ]

    for record in targets:
        sim = float(
            np.dot(live_emb, record["voice_embedding"]) /
            (np.linalg.norm(live_emb) * np.linalg.norm(record["voice_embedding"]))
        )

        if sim > best["similarity"]:
            best["similarity"] = sim
            best["name"] = record["name"]
            best["verified"] = sim >= VOICE_SIM_THRESHOLD

    return best


# ── Combined verification ─────────────────────────────────────────────────────
def verify(live_frame, audio_path: str, enrollments: list[dict],
           claimed_name: str | None = None) -> dict:

    face_result = verify_face(live_frame, enrollments)
    voice_result = verify_voice(audio_path, enrollments, claimed_name)

    names_match = (
        face_result["name"] is not None and
        voice_result["name"] is not None and
        face_result["name"].lower() == voice_result["name"].lower()
    )

    granted = (
        face_result["verified"] and
        voice_result["verified"] and
        names_match
    )

    print(f"  [face]  name={face_result['name']} "
          f"dist={face_result['distance']:.3f} "
          f"pass={face_result['verified']}")

    print(f"  [voice] name={voice_result['name']} "
          f"sim={voice_result['similarity']:.3f} "
          f"pass={voice_result['verified']}")

    return {
        "granted": granted,
        "name": face_result["name"] or voice_result["name"],
        "face_verified": face_result["verified"],
        "face_distance": round(face_result["distance"], 3),
        "voice_verified": voice_result["verified"],
        "voice_similarity": round(voice_result["similarity"], 3),
        "names_match": names_match,
        "reason": _build_reason(face_result, voice_result, names_match),
    }


# ── explanation helper ────────────────────────────────────────────────────────
def _build_reason(face: dict, voice: dict, names_match: bool) -> str:
    parts = []

    if face["verified"]:
        parts.append(f"face matched {face['name']} (dist {face['distance']:.3f})")
    else:
        parts.append(f"face rejected (dist {face['distance']:.3f})")

    if voice.get("error"):
        parts.append(f"voice check skipped: {voice['error']}")
    elif voice["verified"]:
        parts.append(f"voice matched {voice['name']} (sim {voice['similarity']:.3f})")
    else:
        parts.append(f"voice rejected (sim {voice['similarity']:.3f})")

    if not names_match and face["name"] and voice["name"]:
        parts.append(f"identity mismatch: face={face['name']} voice={voice['name']}")

    return " | ".join(parts)