# ── recognizer.py ─────────────────────────────────────────────────────────────
"""
Face + voice verification against enrolled identities.
Loads all enrollments at startup and identifies the closest match.
"""

import os
import json
import numpy as np
from pathlib import Path
from deepface import DeepFace
from resemblyzer import VoiceEncoder, preprocess_wav

from config import (
    ENROLLMENT_DIR,
    FACE_DISTANCE_THRESHOLD,
    VOICE_SIM_THRESHOLD,
)

encoder = VoiceEncoder()


# ── Load enrollments ──────────────────────────────────────────────────────────
def load_enrollments() -> list[dict]:
    """
    Scan ENROLLMENT_DIR and return a list of enrollment records:
        { name, face_paths, voice_embedding }
    """
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
            "name":            meta["name"],
            "face_paths":      meta["face_paths"],
            "voice_embedding": np.load(emb_path),
        })

    print(f"  [recognizer] Loaded {len(records)} enrollment(s): "
          f"{[r['name'] for r in records]}")
    return records


# ── Face verification ─────────────────────────────────────────────────────────
def verify_face(live_frame, enrollments: list[dict]) -> dict:
    """
    Compare live_frame against every enrolled face.
    Returns the best match result dict:
        { verified, name, distance, threshold }
    """
    best = {"verified": False, "name": None,
            "distance": 1.0,   "threshold": FACE_DISTANCE_THRESHOLD}

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
                    best["name"]     = record["name"]
                    best["verified"] = dist < FACE_DISTANCE_THRESHOLD
            except Exception as e:
                print(f"  [face] Error comparing to {record['name']}: {e}")
                continue

    return best


# ── Voice verification ────────────────────────────────────────────────────────
def verify_voice(audio_path: str, enrollments: list[dict],
                 claimed_name: str | None = None) -> dict:
    """
    Compare voice in audio_path against enrolled voice embeddings.
    If claimed_name is given, only compares against that user (faster).
    Returns:
        { verified, name, similarity, threshold }
    """
    best = {"verified": False, "name": None,
            "similarity": 0.0, "threshold": VOICE_SIM_THRESHOLD}

    try:
        wav        = preprocess_wav(Path(audio_path))
        live_emb   = encoder.embed_utterance(wav)
    except Exception as e:
        print(f"  [voice] Failed to embed audio: {e}")
        return best

    targets = enrollments
    if claimed_name:
        targets = [r for r in enrollments
                   if r["name"].lower() == claimed_name.lower()]

    for record in targets:
        sim = float(np.dot(live_emb, record["voice_embedding"]))
        if sim > best["similarity"]:
            best["similarity"] = sim
            best["name"]       = record["name"]
            best["verified"]   = sim >= VOICE_SIM_THRESHOLD

    return best


# ── Combined verification ─────────────────────────────────────────────────────
def verify(live_frame, audio_path: str, enrollments: list[dict],
           claimed_name: str | None = None) -> dict:
    """
    Run both face and voice checks. Both must pass for access.
    Returns a unified result dict.
    """
    face_result  = verify_face(live_frame, enrollments)
    voice_result = verify_voice(audio_path, enrollments, claimed_name)

    # Require both factors to agree on the same identity
    names_match  = (face_result["name"] is not None and
                    voice_result["name"] is not None and
                    face_result["name"].lower() == voice_result["name"].lower())

    granted = face_result["verified"] and voice_result["verified"] and names_match

    print(f"  [face]  name={face_result['name']}  "
          f"dist={face_result['distance']:.3f}  "
          f"pass={face_result['verified']}")
    print(f"  [voice] name={voice_result['name']}  "
          f"sim={voice_result['similarity']:.3f}  "
          f"pass={voice_result['verified']}")

    return {
        "granted":          granted,
        "name":             face_result["name"] or voice_result["name"],
        "face_verified":    face_result["verified"],
        "face_distance":    round(face_result["distance"],   3),
        "voice_verified":   voice_result["verified"],
        "voice_similarity": round(voice_result["similarity"], 3),
        "names_match":      names_match,
        "reason":           _build_reason(face_result, voice_result, names_match),
    }


def _build_reason(face: dict, voice: dict, names_match: bool) -> str:
    parts = []
    if face["verified"]:
        parts.append(f"face matched {face['name']} (dist {face['distance']:.3f})")
    else:
        parts.append(f"face rejected (dist {face['distance']:.3f} > {face['threshold']})")

    if voice["verified"]:
        parts.append(f"voice matched {voice['name']} (sim {voice['similarity']:.3f})")
    else:
        parts.append(f"voice rejected (sim {voice['similarity']:.3f} < {voice['threshold']})")

    if not names_match and face["name"] and voice["name"]:
        parts.append(f"identity mismatch: face={face['name']} voice={voice['name']}")

    return " | ".join(parts)