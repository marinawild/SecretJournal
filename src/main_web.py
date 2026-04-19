import os
import json
import shutil
import datetime
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import requests
import serial
import threading
import asyncio
import uuid
import time

from recognizer import verify, load_enrollments
from config import ENROLLMENT_DIR

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

SERIAL_PORT = "COM7" 
ser = None
hardware_available = False

# Holds a reference to the FastAPI event loop so the background
# thread can safely schedule coroutines onto it.
main_event_loop: asyncio.AbstractEventLoop | None = None

try:
    ser = serial.Serial(SERIAL_PORT, 115200, timeout=0.1)
    hardware_available = True
    print(f"✅ Arduino connected on {SERIAL_PORT}")
except Exception as e:
    print(f"⚠️ Arduino NOT detected. Simulation Mode active. (Error: {e})")


@app.on_event("startup")
async def capture_event_loop():
    """Capture the running event loop at startup so the Arduino thread can use it."""
    global main_event_loop
    main_event_loop = asyncio.get_running_loop()
    if hardware_available:
        threading.Thread(target=listen_to_arduino, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
async def portal():
    """Serves the Vault Entry page (Lock Icon/Simulation)."""
    with open("static/portal.html") as f:
        return f.read()

@app.get("/verify-page", response_class=HTMLResponse)
async def index_page():
    """Serves the Biometric page (Video/Name input)."""
    with open("static/index.html") as f: 
        return f.read()

@app.get("/journal", response_class=HTMLResponse)
async def journal_page():
    with open("static/journal.html") as f:
        return f.read()


# --- WEBSOCKET & ARDUINO LISTENER ---
active_connections: list[WebSocket] = []

@app.websocket("/ws/button")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


async def broadcast(message: str):
    """Send a message to all connected WebSocket clients, removing dead ones."""
    dead = []
    for ws in active_connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        active_connections.remove(ws)


def listen_to_arduino():
    """
    Background thread that reads serial data from the Arduino.

    Uses asyncio.run_coroutine_threadsafe() to safely schedule
    WebSocket sends onto the FastAPI event loop — the only correct
    way to call async code from a non-async thread.
    """
    while hardware_available and ser:
        try:
            line = ser.readline().decode().strip()
            if not line:
                continue

            if line == "VERIFY":
                print("🔓 Arduino: Transitioning to Verification")
                if main_event_loop:
                    asyncio.run_coroutine_threadsafe(
                        broadcast("pressed"), main_event_loop
                    )

            elif line == "OK LOCKED":
                print("🔒 Arduino: Returning to Portal")
                if main_event_loop:
                    asyncio.run_coroutine_threadsafe(
                        broadcast("reset_to_portal"), main_event_loop
                    )

        except Exception as e:
            print(f"Serial read error: {e}")
            break


# --- HARDWARE UNLOCK ---
@app.post("/unlock-hardware")
async def unlock_hardware():
    if hardware_available and ser:
        ser.write(b'UNLOCK\n')
        return {"status": "Hardware Unlocked"}
    return {"status": "Simulation: Hardware unlock triggered"}


# --- AI GENERATION ---
@app.get("/generate-prompt")
async def generate_prompt(name: str = "User"):
    day_name = datetime.datetime.now().strftime("%A")
    user_slug = name.lower().replace(" ", "_")
    meta_path = os.path.join(ENROLLMENT_DIR, user_slug, "meta.json")
    
    user_info = {"name": name}
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            user_info = json.load(f)
    
    prompt_text = (
        f"The user is {user_info['name']}, a {user_info.get('age', 'student')} "
        f"studying {user_info.get('study_area', 'their passion')}. "
        f"They enjoy {user_info.get('hobby', 'creative activities')} "
        f"and like {user_info.get('food', 'comfort food')}."

        f"\nToday is {day_name}."

        "\nGenerate ONE lighthearted, meaningful journal prompt for a mental wellness journal. "
        "The prompt should feel personal and relevant when possible, "
        "but you do NOT need to mention all or any of the user details explicitly. "
        "Only use personal details if they naturally fit the prompt."

        "\nThe prompt should be reflective, warm, and suitable for daily journaling."
    )

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma2:2b", "prompt": prompt_text, "stream": False},
            timeout=10
        )
        return {"prompt": response.json()["response"]}
    except Exception:
        return {"prompt": f"How has your {day_name} been so far?"}


# --- VERIFICATION LOGIC ---
import time # Ensure this is imported at the top

@app.post("/verify")
async def web_verify(
    claimed_name: str = Form(...),
    face_image: UploadFile = File(...),
    voice_audio: UploadFile = File(...)
):
    enrollments = load_enrollments()
    uid = uuid.uuid4().hex
    face_path = f"temp_face_{uid}.jpg"
    voice_path = f"temp_voice_{uid}.wav"
    
    with open(face_path, "wb") as buffer:
        shutil.copyfileobj(face_image.file, buffer)
    with open(voice_path, "wb") as buffer:
        shutil.copyfileobj(voice_audio.file, buffer)

    result = verify(face_path, voice_path, enrollments, claimed_name=claimed_name)

    # --- THE FIX: Delayed Deletion ---
    def delayed_delete(files):
        time.sleep(5) # Keep file for 5 seconds for debugging/DeepFace stability
        for f in files:
            if os.path.exists(f):
                os.remove(f)

    threading.Thread(target=delayed_delete, args=([face_path, voice_path],), daemon=True).start()

    if hardware_available and ser:
        if result["granted"]:
            ser.write(b"UNLOCK\n")
        else:
            ser.write(b"REJECT\n")

    return result