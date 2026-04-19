# 📖 The Secret Journal: Biometric Vault & AI Companion

> *A high-security physical and digital journaling ecosystem — where your thoughts are protected by your face, your voice, and a mechanical lock.*

---

## 🔐 Overview

**The Secret Journal** is a multi-modal biometric security system built around a physical 3D-printed vault. Access to the diary inside is granted only after the system confirms your identity using both **facial recognition** and **voice verification** simultaneously. Once you're in, a locally-running AI generates a personalized reflection prompt, crafted specifically around your life, your studies, and your interests.

The system bridges the physical and digital worlds: a button press on the vault triggers a browser animation via WebSocket, and a successful biometric login drives a stepper motor to physically slide the lock open.

---

## ✨ Features

- **Physical-to-Digital Trigger** — A button on the vault sends a serial signal to the server, which fires a "warp" animation in the browser via WebSockets.
- **Multi-Factor Biometric Authentication** — Both factors must independently confirm the same identity for access to be granted:
  - 🎭 **Facial Recognition** via DeepFace (Facenet512 model + RetinaFace detector)
  - 🎙️ **Voice Verification** via Resemblyzer — the user must speak the challenge phrase aloud
- **Automated Hardware Unlock** — On confirmed identity, the server signals an Arduino Nano to drive a stepper motor and physically open the vault.
- **Personalized AI Reflection** — Gemma 2:2b (running locally via Ollama) generates a unique journaling prompt based on the user's name, age, field of study, and hobbies.
- **Immersive UI** — Glassmorphism design, animated mesh gradient backgrounds, magical sound effects, and a 3D book reveal animation.
- **Enrollment System** — A guided CLI captures 3 face photos at different angles, a voice sample, and a personalization questionnaire — all stored locally.

---

## 🛠️ Tech Stack

### Backend & AI

| Tool | Role |
|---|---|
| [FastAPI](https://fastapi.tiangolo.com/) | Web server, REST API, and WebSocket communication |
| [DeepFace](https://github.com/serengil/deepface) | Facial recognition using the Facenet512 model |
| [Resemblyzer](https://github.com/resemble-ai/Resemblyzer) | Voice embedding generation and cosine similarity comparison |
| [Ollama](https://ollama.com/) + Gemma 2:2b | Local LLM for generating personalized journal prompts |
| [PySerial](https://pyserial.readthedocs.io/) | Serial bridge between the Python server and Arduino hardware |
| [OpenCV](https://opencv.org/) | Live camera capture and frame processing |
| [SoundDevice](https://python-sounddevice.readthedocs.io/) + SciPy | Audio recording and WAV file handling |

### Frontend

| Tool | Role |
|---|---|
| HTML5 / CSS3 | Structure and advanced glassmorphism + animation styling |
| Vanilla JavaScript | UI logic, MediaRecorder API for audio/video capture |
| WebSockets (native browser API) | Real-time bidirectional hardware-to-browser communication |

### Hardware & Design

| Component | Role |
|---|---|
| Arduino Nano | Microcontroller — reads button input, drives motor, receives unlock commands |
| Stepper Motor | Mechanical force to slide the locking bolt open/closed |
| LED | Display Red for Denied and Green for Access Granted |
| LCD Display | Displays state of vault - Locked vs. Unlocked |
| UART | Arduino send button unlocking and locking signals to web application
| [Fusion 360](https://www.autodesk.com/products/fusion-360/) | CAD design of the 3D-printed vault enclosure |

---

## 🚀 How It Works

```
[ Physical Button Press ]
        │
        ▼
[ Arduino → Serial "VERIFY" signal ]
        │
        ▼
[ FastAPI Server → WebSocket broadcast → Browser "warp" animation ]
        │
        ▼
[ User enters name → camera + mic activate → speaks challenge phrase ]
        │
        ▼
[ Server runs DeepFace (face) + Resemblyzer (voice) in parallel ]
        │
   ┌────┴────┐
   │  PASS   │  Both biometrics confirmed, names match
   └────┬────┘
        │
        ▼
[ Arduino receives "UNLOCK" → stepper motor opens vault ]
[ Browser plays chime → book animation → journal page ]
[ Gemma 2:2b generates personalized reflection prompt ]
        │
        ▼
[ User locks vault → Arduino sends "OK LOCKED" → browser resets to portal ]
```

---

## 📁 Project Structure

```
secret-journal/
│
├── main_web.py          # FastAPI server — routes, WebSocket hub, Arduino bridge
├── main.py              # Standalone OpenCV desktop app (no web, no Arduino)
├── recognizer.py        # Face + voice verification logic
├── enroll.py            # CLI enrollment wizard (face, voice, questionnaire)
├── config.py            # Thresholds, paths, and audio settings
│
├── static/
│   ├── portal.html      # Entry page — vault door / warp animation
│   ├── index.html       # Biometric verification page
│   ├── journal.html     # AI prompt display page
│   ├── script.js        # Frontend capture, verification, and redirect logic
│   └── styles.css       # Glassmorphism UI, animations, and layout
│
└── enrollments/
    └── <username>/
        ├── face_0.jpg   # 3 face photos (straight, left, right)
        ├── face_1.jpg
        ├── face_2.jpg
        ├── voice_embedding.npy
        └── meta.json    # Name, age, study area, hobby, etc.
```

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running locally
- Arduino IDE (to flash the Nano)
- A webcam and microphone

### 1. Install Python dependencies

```bash
pip install fastapi uvicorn deepface resemblyzer opencv-python sounddevice scipy pyserial tf-keras
```

### 2. Pull the LLM model

```bash
ollama pull gemma2:2b
```

### 3. Configure your serial port

In `main_web.py`, update the serial port to match your system:

```python
# Windows
SERIAL_PORT = "COM6"

# macOS / Linux
SERIAL_PORT = "/dev/ttyUSB0"
```

### 4. Enroll a user

```bash
python enroll.py
```

Follow the prompts to capture face photos, a voice sample, and complete the personalization questionnaire.

### 5. Run the server

```bash
uvicorn main_web:app --reload
```

Then open `http://localhost:8000` in your browser.

---

## 🔧 Configuration

Key parameters are centralized in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `FACE_DISTANCE_THRESHOLD` | `0.40` | Max cosine distance for a face match (lower = stricter) |
| `VOICE_SIM_THRESHOLD` | `0.65` | Min cosine similarity for a voice match (higher = stricter) |
| `ENROLLMENT_AUDIO_SECS` | `8` | Duration of voice sample during enrollment |
| `VERIFY_AUDIO_SECS` | `4` | Duration of voice capture during verification |
| `CHALLENGE_PHRASE` | `"Unlock my Secret Journal."` | The phrase users must speak aloud |

---

## 🖥️ Running Without Hardware

The system runs in **Simulation Mode** automatically if no Arduino is detected on startup. In this mode:

- Press **`S`** on the keyboard (or click the lock icon) on the portal page to trigger the warp animation.
- The `/unlock-hardware` endpoint returns a simulated response instead of writing to serial.
- All biometric verification works identically.

---
