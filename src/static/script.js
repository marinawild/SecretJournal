// --- script.js ---

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const authBtn = document.getElementById('authBtn');
const phraseDisplay = document.getElementById('phrase-display');
const countdownDisplay = document.getElementById('countdown');
const challengeArea = document.getElementById('challenge-area');

authBtn.onclick = async () => {
    const name = document.getElementById('nameInput').value;
    if (!name) return alert("Enter your name first!");

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        video.srcObject = stream;

        const phrase = `Unlock my Secret Journal!`;
        phraseDisplay.innerText = phrase;
        challengeArea.style.display = 'block';

        let timeLeft = 3;
        const timer = setInterval(() => {
            countdownDisplay.innerText = `Recording in ${timeLeft}...`;
            if (timeLeft <= 0) {
                clearInterval(timer);
                performCapture(name, stream);
            }
            timeLeft -= 1;
        }, 1000);
    } catch (err) {
        console.error("Error accessing media:", err);
        alert("Camera and Microphone access is required.");
    }
};

async function performCapture(name, stream) {
    countdownDisplay.innerText = "🔴 SPEAK NOW";
    countdownDisplay.style.color = "red";

    const mediaRecorder = new MediaRecorder(stream);
    const chunks = [];

    mediaRecorder.ondataavailable = e => chunks.push(e.data);

    mediaRecorder.onstop = async () => {
        try {
            // Capture face snapshot from video
            const context = canvas.getContext('2d');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            context.drawImage(video, 0, 0);
            const faceBlob = await new Promise(res => canvas.toBlob(res, 'image/jpeg'));

            stream.getTracks().forEach(track => track.stop());
            video.srcObject = null;

            // Send raw audio as-is — backend ffmpeg handles the format
            const voiceBlob = new Blob(chunks);
            const formData = new FormData();
            formData.append("claimed_name", name);
            formData.append("face_image", faceBlob, "face.jpg");
            formData.append("voice_audio", voiceBlob, "voice.webm");

            document.getElementById('status').innerText = "Verifying Identity...";

            const response = await fetch("/verify", { method: "POST", body: formData });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const result = await response.json();

            if (result.granted) {
                document.getElementById('status').innerText = "✅ UNLOCKED! Redirecting...";
                setTimeout(() => {
                    window.location.href = `/journal?name=${encodeURIComponent(name)}`;
                }, 1500);
            } else {
                challengeArea.style.display = 'none';
                document.getElementById('status').innerText = "❌ DENIED: " + result.reason;
            }

        } catch (err) {
            console.error("Verification error:", err);
            challengeArea.style.display = 'none';
            document.getElementById('status').innerText = "❌ Error during verification. Please try again.";
        }
    };

    mediaRecorder.start();
    setTimeout(() => mediaRecorder.stop(), 4000);
}