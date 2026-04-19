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

from recognizer import verify, load_enrollments
from config import ENROLLMENT_DIR

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

SERIAL_PORT = "COM6" 
ser = None
hardware_available = False

try:
    ser = serial.Serial(SERIAL_PORT, 115200, timeout=0.1)
    hardware_available = True
    print(f"✅ Arduino connected on {SERIAL_PORT}")
except Exception as e:
    print(f"⚠️ Arduino NOT detected. Simulation Mode active. (Error: {e})")

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
active_connections = []

@app.websocket("/ws/button")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        active_connections.remove(websocket)


def listen_to_arduino():
    """Background thread to handle incoming Arduino commands."""
    while hardware_available and ser:
        try:
            # Read the signal from the Arduino
            line = ser.readline().decode().strip()
            
            if line == "VERIFY":
                print("🔓 Arduino: Transitioning to Verification")
                for connection in active_connections:
                    asyncio.run(connection.send_text("pressed"))
            
            elif line == "OK LOCKED":
                print("🔒 Arduino: Returning to Portal")
                for connection in active_connections:
                    asyncio.run(connection.send_text("reset_to_portal"))
                    
        except Exception as e:
            print(f"Serial read error: {e}")
            break

# Only start thread if hardware exists
if hardware_available:
    threading.Thread(target=listen_to_arduino, daemon=True).start()

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
        f"Their hobby is {user_info.get('hobby', 'creation')}. "
        f"Today is {day_name}. Generate ONE lighthearted, journal prompt with mental wellness in mind."
    )

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma2:2b", "prompt": prompt_text, "stream": False},
            timeout=10
        )
        return {"prompt": response.json()["response"]}
    except:
        return {"prompt": f"How has your {day_name} been so far?"}

# --- VERIFICATION LOGIC ---
@app.post("/verify")
async def web_verify(
    claimed_name: str = Form(...),
    face_image: UploadFile = File(...),
    voice_audio: UploadFile = File(...)
):
    enrollments = load_enrollments()
    face_path, voice_path = "temp_face.jpg", "temp_voice.wav"
    
    with open(face_path, "wb") as buffer:
        shutil.copyfileobj(face_image.file, buffer)
    with open(voice_path, "wb") as buffer:
        shutil.copyfileobj(voice_audio.file, buffer)

    result = verify(face_path, voice_path, enrollments, claimed_name=claimed_name)

    if result["granted"]:
        # If user is confirmed, tell Arduino to unlock
        await unlock_hardware()

    return result