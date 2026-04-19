import os
import json
import shutil
import datetime
#import google.generativeai as genai
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import requests

from recognizer import verify, load_enrollments
from config import ENROLLMENT_DIR

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html") as f:
        return f.read()

@app.get("/journal", response_class=HTMLResponse)
async def journal_page():
    with open("static/journal.html") as f:
        return f.read()

def get_season():
    """Helper to determine the current season."""
    month = datetime.datetime.now().month
    if 3 <= month <= 5: return "Spring"
    if 6 <= month <= 8: return "Summer"
    if 9 <= month <= 11: return "Autumn"
    return "Winter"

@app.get("/generate-prompt")
async def generate_prompt(name: str = "User"):
    day_name = datetime.datetime.now().strftime("%A")
    
    user_slug = name.lower().replace(" ", "_")
    meta_path = os.path.join(ENROLLMENT_DIR, user_slug, "meta.json")
    
    user_info = {"name": name}
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            user_info = json.load(f)
    
    #Build the prompt for Gemma
    prompt_text = (
        f"The user is {user_info['name']}, a {user_info.get('age', 'student')} "
        f"studying {user_info.get('study_area', 'their passion')}. "
        f"Their hobby is {user_info.get('hobby', 'creation')}. "
        f"Today is {day_name}. Generate ONE lighthearted, creative, mindset or mental health centered, journal prompt for them."
    )

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gemma2:2b",
                "prompt": prompt_text,
                "stream": False
            }
        )
        return {"prompt": response.json()["response"]}
    except Exception as e:
        return {"prompt": f"Gemma is resting. How was your {day_name}?"}

@app.post("/verify")
async def web_verify(
    claimed_name: str = Form(...),
    face_image: UploadFile = File(...),
    voice_audio: UploadFile = File(...)
):
    enrollments = load_enrollments()
    
    face_path = "temp_face.jpg"
    voice_path = "temp_voice.wav"
    
    with open(face_path, "wb") as buffer:
        shutil.copyfileobj(face_image.file, buffer)
    with open(voice_path, "wb") as buffer:
        shutil.copyfileobj(voice_audio.file, buffer)

    result = verify(face_path, voice_path, enrollments, claimed_name=claimed_name)

    if result["granted"]:
        print(f"IDENTITY CONFIRMED: Unlocking for {result['name']}...")
        # Optional: Add serial trigger for physical hardware here

    return result