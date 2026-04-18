from deepface import DeepFace
import numpy as np
import librosa

def analyze_stress(frames, audio_path):
    # --- Multi-Frame Facial Analysis ---
    stress_scores = []
    
    # We only analyze a subset of frames to keep it fast (e.g., every 5th frame)
    for i, frame in enumerate(frames):
        if i % 5 == 0: 
            try:
                # analyze() returns a list of detected faces
                objs = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
                # Weighted stress: Fear and Surprise often indicate hesitation
                score = objs[0]['emotion']['fear'] + objs[0]['emotion']['surprise']
                stress_scores.append(score)
            except:
                continue
    
    # Calculate average stress or 0 if no faces were detected
    avg_facial_stress = np.mean(stress_scores) if stress_scores else 0

    # --- Audio Analysis (Remains the same) ---
    y, sr = librosa.load(audio_path)
    pitches, _ = librosa.piptrack(y=y, sr=sr)
    pitch_jitter = np.std(pitches[pitches > 0])

    return {
        "facial_stress_score": round(float(avg_facial_stress), 2),
        "vocal_jitter": round(float(pitch_jitter), 2),
        "hesitation_moments": len(librosa.effects.split(y, top_db=30))
    }