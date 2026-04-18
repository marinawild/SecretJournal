import cv2
import threading
import sounddevice as sd
import time
from scipy.io.wavfile import write
from analyzer import analyze_stress
from gemini_judger import get_verdict

def record_audio(duration=3, fs=44100):
    print("Recording audio... Speak now!")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()  
    write('temp_audio.wav', fs, recording)
    print("Recording complete.")

def start_interrogation():
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("--- System Online ---")
    print("Controls: \n [ENTER] - Start Analysis \n [Q] - Quit")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1) # Mirror view
        cv2.putText(frame, "STATUS: MONITORING", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow('Lie Detector Feed', frame)

        key = cv2.waitKey(1) & 0xFF
        
        # Press 'Enter' to start recording AND frame buffering
        if key == ord('\r'):
            captured_frames = []
            
            # Start audio in background
            audio_thread = threading.Thread(target=record_audio)
            audio_thread.start()
            
            print("Capturing biometrics (3 seconds)...")
            start_time = time.time()
            
            # Capture loop while audio records
            while time.time() - start_time < 3.5:
                ret, loop_frame = cap.read()
                if ret:
                    captured_frames.append(loop_frame)
                    # Visual feedback during recording
                    cv2.circle(loop_frame, (30, 70), 10, (0, 0, 255), -1)
                    cv2.putText(loop_frame, "RECORDING...", (50, 80), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    cv2.imshow('Lie Detector Feed', loop_frame)
                cv2.waitKey(1)

            audio_thread.join()
            
            print("Analyzing buffer with Gemini...")
            metadata = analyze_stress(captured_frames, "temp_audio.wav") 
            verdict = get_verdict(metadata)
            print(f"\nRESULT: {verdict}\n")

        # Press 'Q' to quit
        elif key == ord('q'):
            print("Shutting down...")
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    start_interrogation()