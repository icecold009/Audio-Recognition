const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const recBtn = document.getElementById('recBtn');
const stopBtn = document.getElementById('stopBtn');
const resultDiv = document.getElementById('result');
const statusDiv = document.getElementById('status');

let mediaRecorder;
let chunks = [];
let stopTimer = null;
let mediaStream = null;

async function refreshStatus() {
    try {
        const res = await fetch('/api/status');
        const s = await res.json();
        statusDiv.innerHTML = `AcoustID: ${s.acoustid_configured ? 'configured' : 'not configured'}; ` +
            `fpcalc on PATH: ${s.fpcalc_on_path ? 'yes' : 'no'}; ` +
            `FP_CALC_PATH exists: ${s.fpcalc_path_exists ? 'yes' : 'no'}; ` +
            `ffmpeg on PATH: ${s.ffmpeg_on_path ? 'yes' : 'no'}; ` +
            `AudD token: ${s.audd_configured ? 'configured' : 'not configured'}`;
    } catch (err) {
        statusDiv.innerText = 'Failed to fetch status: ' + err;
    }
}

refreshStatus();

async function postFile(file) {
    const fd = new FormData();
    fd.append('file', file, file.name || 'upload.audio');
    resultDiv.innerText = 'Uploading...';
    try {
        const res = await fetch('/api/match', { method: 'POST', body: fd });
        const data = await res.json();
        renderResult(data);
    } catch (err) {
        resultDiv.innerText = 'Upload error: ' + err;
    }
}

function renderResult(data) {
    if (!data) {
        resultDiv.innerText = 'No response';
        return;
    }
    if (data.status === 'no_token') {
        resultDiv.innerText = 'Server: AUDD token not configured.';
        return;
    }
    if (data.status === 'error') {
        resultDiv.innerText = 'Server error: ' + (data.error || 'unknown');
        return;
    }
    if (data.status === 'no_match') {
        resultDiv.innerText = 'No match found.';
        return;
    }

    resultDiv.innerHTML = '';
    const title = document.createElement('div');
    title.textContent = `Song: ${data.title || '(unknown)'}`;

    const artist = document.createElement('div');
    artist.textContent = `Artist: ${data.artist || '(unknown)'}`;

    const album = document.createElement('div');
    album.textContent = `Album: ${data.album || '(unknown)'}`;

    resultDiv.appendChild(title);
    resultDiv.appendChild(artist);
    resultDiv.appendChild(album);

    if (data.image) {
        const img = document.createElement('img');
        img.src = data.image;
        resultDiv.appendChild(img);
    }
}

uploadBtn.addEventListener('click', () => {
    const f = fileInput.files[0];
    if (!f) {
        resultDiv.innerText = 'Select a file first.';
        return;
    }
    postFile(f);
});

recBtn.addEventListener('click', async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        resultDiv.innerText = 'Microphone not supported in this browser.';
        return;
    }

    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        chunks = [];
        mediaRecorder = new MediaRecorder(mediaStream);

        mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) chunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            if (stopTimer) {
                clearTimeout(stopTimer);
                stopTimer = null;
            }

            if (mediaStream) {
                mediaStream.getTracks().forEach(track => track.stop());
                mediaStream = null;
            }

            const blob = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' });
            chunks = [];

            if (blob.size === 0) {
                resultDiv.innerText = 'No audio recorded.';
                return;
            }

            const file = new File([blob], 'recording.webm', { type: blob.type });
            await postFile(file);
        };

        mediaRecorder.start(1000);
        recBtn.disabled = true;
        stopBtn.disabled = false;
        resultDiv.innerText = 'Recording... (auto-stops after 10 seconds)';

        stopTimer = setTimeout(() => {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
            recBtn.disabled = false;
            stopBtn.disabled = true;
            resultDiv.innerText = 'Recording stopped automatically after 10 seconds.';
        }, 10000);
    } catch (err) {
        resultDiv.innerText = 'Microphone error: ' + err;
        recBtn.disabled = false;
        stopBtn.disabled = true;
    }
});

stopBtn.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        recBtn.disabled = false;
        stopBtn.disabled = true;
    }
});