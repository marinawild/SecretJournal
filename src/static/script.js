// --- script.js ---

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const authBtn = document.getElementById('authBtn');
const phraseDisplay = document.getElementById('phrase-display');
const countdownDisplay = document.getElementById('countdown');
const challengeArea = document.getElementById('challenge-area');

let recordedChunks = [];
let faceBlob = null;

authBtn.onclick = async () => {
    const name = document.getElementById('nameInput').value;
    if (!name) return alert("Enter your name first!");

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: true
        });

        video.srcObject = stream;
        window.stream = stream;

        const phrase = "Unlock my Secret Journal!";
        phraseDisplay.innerText = phrase;
        challengeArea.style.display = 'block';
        document.getElementById('status').innerText = "";

        let timeLeft = 3;

        const timer = setInterval(() => {
            countdownDisplay.innerText = `Recording in ${timeLeft}...`;

            if (timeLeft <= 0) {
                clearInterval(timer);
                performCapture(name, stream);
            }

            timeLeft--;
        }, 1000);

    } catch (err) {
        console.error("Error accessing media:", err);
        alert("Camera and Microphone access is required.");
    }
};


// -------------------------------
// SAFE FRAME CAPTURE FUNCTION
// -------------------------------
async function captureFaceFrame(video, canvas) {
    const ctx = canvas.getContext('2d');

    // Wait until video has real frame data
    if (video.readyState < video.HAVE_CURRENT_DATA || video.videoWidth === 0) {
        await new Promise(resolve => {
            video.addEventListener('loadeddata', resolve, { once: true });
        });
    }

    // Allow render pipeline to stabilize
    await new Promise(requestAnimationFrame);
    await new Promise(requestAnimationFrame);

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    return await new Promise(resolve =>
        canvas.toBlob(resolve, 'image/jpeg', 0.95)
    );
}


// -------------------------------
// MAIN CAPTURE FLOW
// -------------------------------
async function performCapture(name, stream) {

    countdownDisplay.innerText = "🔴 SPEAK NOW";
    countdownDisplay.style.color = "red";

    recordedChunks = [];
    faceBlob = null;

    const mediaRecorder = new MediaRecorder(stream);

    // Collect audio chunks
    mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunks.push(e.data);
    };

    // WHEN RECORDING STOPS → build voice + send request
    mediaRecorder.onstop = async () => {

        const verifyingAudio = document.getElementById('verifying-sound');
        const successAudio = document.getElementById('success-sound');

        const voiceBlob = new Blob(recordedChunks, { type: 'audio/webm' });

        if (verifyingAudio) {
            verifyingAudio.play().catch(() => {});
        }

        video.style.display = 'none';
        challengeArea.style.display = 'none';
        document.getElementById('status').innerText = "Verifying Identity...";

        const formData = new FormData();
        formData.append("claimed_name", name);
        formData.append("face_image", faceBlob, "face.jpg");
        formData.append("voice_audio", voiceBlob, "voice.webm");

        try {
            const response = await fetch("/verify", {
                method: "POST",
                body: formData
            });

            const result = await response.json();

            if (verifyingAudio) {
                verifyingAudio.pause();
                verifyingAudio.currentTime = 0;
            }

            if (result.granted) {

                if (successAudio) {
                    successAudio.play().catch(() => {});
                }

                document.getElementById('ui-container').style.display = 'none';

                const bookContainer = document.getElementById('book-animation');
                if (bookContainer) {
                    bookContainer.style.display = 'block';
                    const book = bookContainer.querySelector('.simple-book');
                    if (book) book.classList.add('book-morph');
                }

                setTimeout(() => {
                    window.location.href = `/journal?name=${encodeURIComponent(name)}`;
                }, 3000);

            } else {

                video.style.display = 'block';
                video.srcObject = null;

                document.getElementById('status').innerHTML =
                    `<span style="color:#ff4444;">❌ DENIED: ${result.reason}</span><br>` +
                    `<small style="color:white;">Click 'Start Verification' to try again.</small>`;

                stream.getTracks().forEach(t => t.stop());
            }

        } catch (err) {
            console.error("Verification error:", err);
            document.getElementById('status').innerText = "❌ Connection Error";
        }
    };
    mediaRecorder.start();

    setTimeout(async () => {
        try {
            // Snapshot happens while stream is guaranteed to be LIVE
            faceBlob = await captureFaceFrame(video, canvas);
            console.log("Face captured successfully, size:", faceBlob.size);
        } catch (err) {
            console.error("Face capture failed:", err);
        }

        // Stop the audio recorder
        if (mediaRecorder.state === "recording") {
            mediaRecorder.stop();
        }

        // CRITICAL: Wait 300ms before killing the camera tracks
        // This prevents the "Black Frame" race condition
        setTimeout(() => {
            stream.getTracks().forEach(track => {
                console.log("Stopping track:", track.kind);
                track.stop();
            });
        }, 500);

    }, 5000); // 2.5 seconds gives enough time for the audio and stable video
}