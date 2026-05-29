const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const recBtn = document.getElementById('recBtn');
const stopBtn = document.getElementById('stopBtn');
const resultDiv = document.getElementById('result');
const statusDiv = document.getElementById('status');

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

uploadBtn.addEventListener('click', () => {
    const f = fileInput.files[0];
    if (!f) {
        resultDiv.innerText = 'Select a file first.';
        return;
    }
    postFile(f);
});

let mediaRecorder;
let chunks = [];

recBtn.addEventListener('click', async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        resultDiv.innerText = 'Microphone not supported in this browser.';
        return;
    }
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
        mediaRecorder.onstop = async () => {
            const blob = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' });
            chunks = [];
            const file = new File([blob], 'recording.webm', { type: blob.type });
            await postFile(file);
        };
        mediaRecorder.start(1000);
        recBtn.disabled = true;
        stopBtn.disabled = false;
        resultDiv.innerText = 'Recording...';
    } catch (err) {
        resultDiv.innerText = 'Microphone error: ' + err;
    }
});

stopBtn.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        recBtn.disabled = false;
        stopBtn.disabled = true;
    }
});

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
    // matched
    resultDiv.innerHTML = ``;
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
