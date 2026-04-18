import google.generativeai as genai
# Configure your API key
genai.configure(api_key="AIzaSyANggfjrj4bzBhmIYphTpuuiSr_NhQF9W0")

# Primary choice: 3.1 Flash Lite (Fastest in April 2026)
# Fallback: gemini-flash-latest (Auto-updates to stable Gemini 3 models)
MODEL_NAME = 'models/gemini-3.1-flash-lite-preview'

try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception:
    # Fallback to the auto-updating alias if the specific 3.1 string is not found
    model = genai.GenerativeModel('models/gemini-flash-latest') 

def get_verdict(data):
    prompt = f"""
    You are a high-tech Lie Detection AI. 
    Analyze this telemetry:
    - Facial Stress: {data['facial_stress_score']}%
    - Vocal Jitter: {data['vocal_jitter']}
    - Hesitation count: {data['hesitation_moments']}

    If facial stress > 50 or jitter is high, output 'LIE DETECTED' plus say what metrics led to that score. 
    Otherwise, output 'TRUTH DETECTED'.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Interrogation Error: {str(e)}"