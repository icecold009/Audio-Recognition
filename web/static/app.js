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
let lastFile = null;

const HISTORY_KEY = 'shazam_guest_history';

function loadHistory() {
    try {
        return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]');
    } catch {
        return [];
    }
}

function saveHistory(history) {
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

function addToHistory(item) {
    const history = loadHistory();
    history.unshift(item);
    saveHistory(history.slice(0, 50));
}

function renderHistory() {
    const history = loadHistory();
    const existing = document.getElementById('history-section');
    if (existing) existing.remove();

    const section = document.createElement('section');
    section.id = 'history-section';
    section.className = 'stack';
    section.style.marginTop = '20px';

    const h2 = document.createElement('h2');
    h2.textContent = 'History';
    section.appendChild(h2);

    if (!history.length) {
        const empty = document.createElement('div');
        empty.textContent = 'No history yet.';
        section.appendChild(empty);
    } else {
        history.forEach((item, index) => {
            const card = document.createElement('div');
            card.className = 'panel';
            card.style.display = 'grid';
            card.style.gap = '6px';
            card.style.marginBottom = '12px';

            const title = document.createElement('div');
            title.textContent = `Song: ${item.title || '(unknown)'}`;

            const artist = document.createElement('div');
            artist.textContent = `Artist: ${item.artist || '(unknown)'}`;

            const album = document.createElement('div');
            album.textContent = `Album: ${item.album || '(unknown)'}`;

            const year = document.createElement('div');
            year.textContent = `Year: ${item.year || '(unknown)'}`;

            const time = document.createElement('div');
            time.textContent = `Recognized: ${new Date(item.timestamp).toLocaleString()}`;

            const delBtn = document.createElement('button');
            delBtn.textContent = 'Remove';
            delBtn.style.width = 'fit-content';
            delBtn.addEventListener('click', () => {
                const updated = loadHistory();
                updated.splice(index, 1);
                saveHistory(updated);
                renderHistory();
            });

            card.appendChild(title);
            card.appendChild(artist);
            card.appendChild(album);
            card.appendChild(year);
            card.appendChild(time);

            if (item.image) {
                const img = document.createElement('img');
                img.src = item.image;
                img.alt = item.title || 'Album art';
                img.style.maxWidth = '120px';
                img.style.borderRadius = '12px';
                card.appendChild(img);
            }

            card.appendChild(delBtn);
            section.appendChild(card);
        });
    }

    document.querySelector('.page').appendChild(section);
}

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
renderHistory();

function renderRetryButton() {
    const retryBtn = document.createElement('button');
    retryBtn.textContent = 'Retry';
    retryBtn.style.marginTop = '10px';
    retryBtn.addEventListener('click', () => {
        if (lastFile) postFile(lastFile);
        else resultDiv.innerText = 'Nothing to retry yet.';
    });
    resultDiv.appendChild(retryBtn);
}

async function postFile(file) {
    lastFile = file;
    const fd = new FormData();
    fd.append('file', file, file.name || 'upload.audio');
    resultDiv.innerText = 'Uploading...';
    try {
        const res = await fetch('/api/match', { method: 'POST', body: fd });
        const data = await res.json();
        renderResult(data);
    } catch (err) {
        resultDiv.innerText = 'Upload error: ' + err;
        renderRetryButton();
    }
}

function renderResult(data) {
    if (!data) {
        resultDiv.innerText = 'No response';
        renderRetryButton();
        return;
    }
    if (data.status === 'no_token') {
        resultDiv.innerText = 'Server: AUDD token not configured.';
        renderRetryButton();
        return;
    }
    if (data.status === 'error') {
        resultDiv.innerText = 'Server error: ' + (data.error || 'unknown');
        renderRetryButton();
        return;
    }
    if (data.status === 'no_match') {
        resultDiv.innerText = 'No match found.';
        renderRetryButton();
        return;
    }

    resultDiv.innerHTML = '';

    const title = document.createElement('div');
    title.textContent = `Song: ${data.title || '(unknown)'}`;

    const artist = document.createElement('div');
    artist.textContent = `Artist: ${data.artist || '(unknown)'}`;

    const album = document.createElement('div');
    album.textContent = `Album: ${data.album || '(unknown)'}`;

    const year = document.createElement('div');
    year.textContent = `Year: ${data.year || '(unknown)'}`;

    resultDiv.appendChild(title);
    resultDiv.appendChild(artist);
    resultDiv.appendChild(album);
    resultDiv.appendChild(year);

    if (data.image) {
        const img = document.createElement('img');
        img.src = data.image;
        img.alt = data.title || 'Album art';
        resultDiv.appendChild(img);
    }

    addToHistory({
        title: data.title || '',
        artist: data.artist || '',
        album: data.album || '',
        year: data.year || '',
        image: data.image || '',
        timestamp: Date.now()
    });

    renderHistory();
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
        renderRetryButton();
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
                renderRetryButton();
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
        renderRetryButton();
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