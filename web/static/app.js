const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const recBtn = document.getElementById('recBtn');
const stopBtn = document.getElementById('stopBtn');
const resultDiv = document.getElementById('result');
const statusDiv = document.getElementById('status');
const statusMessage = document.getElementById('statusMessage');
const statusToggle = document.getElementById('statusToggle');
const statusDetails = document.getElementById('statusDetails');
const captureHint = document.getElementById('captureHint');
const recBtnLabel = document.getElementById('recBtnLabel');
const waveform = document.querySelector('.waveform');

let mediaRecorder;
let chunks = [];
let stopTimer = null;
let mediaStream = null;
let audioContext = null;
let analyser = null;
let sourceNode = null;
let animationFrameId = null;
let lastFile = null;
let isSubmitting = false;
let isListening = false;
let isProcessing = false;

const HISTORY_KEY = 'shazam_guest_history';
const SAVE_HISTORY_KEY = 'shazam_save_history_enabled';

function getStorageArea(name) {
    try {
        return window[name];
    } catch {
        return null;
    }
}

function readStorage(name, key) {
    const storage = getStorageArea(name);
    if (!storage) return null;
    try {
        return storage.getItem(key);
    } catch {
        return null;
    }
}

function writeStorage(name, key, value) {
    const storage = getStorageArea(name);
    if (!storage) return;
    try {
        storage.setItem(key, value);
    } catch {
        // Browser storage is optional; recognition must still work without it.
    }
}

function removeStorage(name, key) {
    const storage = getStorageArea(name);
    if (!storage) return;
    try {
        storage.removeItem(key);
    } catch {
        // Browser storage is optional; recognition must still work without it.
    }
}

function setThemeFromStorage() {
    const root = document.documentElement;
    const saved = readStorage('localStorage', 'shazam_theme');
    if (saved === 'light' || saved === 'dark') {
        root.setAttribute('data-theme', saved);
    }
}

function isHistoryEnabled() {
    const raw = readStorage('sessionStorage', SAVE_HISTORY_KEY);
    return raw === null ? true : raw === 'true';
}

function setHistoryEnabled(value) {
    writeStorage('sessionStorage', SAVE_HISTORY_KEY, String(value));
}

function loadHistory() {
    try {
        return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]');
    } catch {
        return [];
    }
}

function saveHistory(history) {
    writeStorage('sessionStorage', HISTORY_KEY, JSON.stringify(history));
}

function clearHistory() {
    removeStorage('sessionStorage', HISTORY_KEY);
}

function addToHistory(item) {
    if (!isHistoryEnabled()) return;
    const history = loadHistory();
    history.unshift(item);
    saveHistory(history.slice(0, 50));
}

function buildStreamingLink(title, artist) {
    const q = encodeURIComponent(`${title || ''} ${artist || ''}`.trim());
    return `https://open.spotify.com/search/${q}`;
}

function safeStreamingLink(value, title, artist) {
    try {
        const url = new URL(value);
        if (url.protocol === 'https:') return url.href;
    } catch {
        // Fall back to a safe, generated Spotify search URL.
    }
    return buildStreamingLink(title, artist);
}

function setMicLabel() {
    const label = isProcessing ? 'Identifying…' : (isListening ? 'Listening…' : 'Start Recording');
    if (recBtnLabel) recBtnLabel.textContent = label;
    if (recBtn) {
        recBtn.setAttribute('aria-label', isProcessing ? 'Identifying song' : (isListening ? 'Stop listening' : 'Identify song'));
        recBtn.setAttribute('aria-pressed', String(isListening));
        recBtn.setAttribute('aria-busy', String(isProcessing));
        recBtn.classList.toggle('is-listening', isListening);
        recBtn.classList.toggle('is-processing', isProcessing);
    }
    if (stopBtn) {
        stopBtn.setAttribute('aria-label', isListening ? 'Stop recording' : 'Stop recording');
    }
    if (captureHint) {
        captureHint.textContent = isProcessing
            ? 'Identifying your recording…'
            : (isListening ? 'Listening… stop when you have enough audio.' : 'Tap the microphone to listen for up to 10 seconds.');
    }
}

function setSubmittingState(loading) {
    isSubmitting = loading;
    isProcessing = loading;
    uploadBtn.disabled = loading || isListening;
    recBtn.disabled = loading || (mediaRecorder && mediaRecorder.state !== 'inactive');
    stopBtn.disabled = !loading && (!mediaRecorder || mediaRecorder.state === 'inactive');
    resultDiv.setAttribute('aria-busy', String(loading));
    setMicLabel();
}

function setListeningState(active) {
    isListening = active;
    if (active) {
        recBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        recBtn.disabled = false;
        stopBtn.disabled = true;
    }
    if (waveform) {
        waveform.classList.toggle('is-active', active);
        waveform.setAttribute('aria-label', active ? 'Live microphone waveform' : 'Idle waveform visualizer');
    }
    setMicLabel();
}

function ensureVisualizerNode(stream) {
    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        sourceNode = audioContext.createMediaStreamSource(stream);
        sourceNode.connect(analyser);
    } catch {
        audioContext = null;
        analyser = null;
        sourceNode = null;
    }
}

function stopVisualizer() {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
    if (sourceNode) {
        try { sourceNode.disconnect(); } catch { }
    }
    if (analyser) {
        try { analyser.disconnect(); } catch { }
    }
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close().catch(() => { });
    }
    audioContext = null;
    analyser = null;
    sourceNode = null;
}

function stopMediaStream() {
    const stream = mediaStream;
    mediaStream = null;
    if (!stream) return;
    try {
        stream.getTracks().forEach(track => track.stop());
    } catch {
        // Cleanup is best effort when a browser stream is already unavailable.
    }
}

function startVisualizerLoop() {
    const bars = Array.from(document.querySelectorAll('[data-wave-bar]'));
    if (!bars.length || !analyser) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
        animationFrameId = requestAnimationFrame(draw);
        analyser.getByteFrequencyData(dataArray);

        for (let i = 0; i < bars.length; i++) {
            const value = dataArray[Math.floor((i / bars.length) * bufferLength)] || 0;
            const height = Math.max(6, Math.round((value / 255) * 64));
            bars[i].style.height = `${height}px`;
            bars[i].style.opacity = String(0.35 + (value / 255) * 0.65);
        }
    };

    draw();
}

function showDetailModal(item) {
    const existing = document.getElementById('detail-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'detail-modal';
    overlay.className = 'detail-modal-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'detail-modal-title');
    overlay.tabIndex = -1;

    const previousFocus = document.activeElement;
    const closeModal = () => {
        overlay.remove();
        if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
    };

    const modal = document.createElement('div');
    modal.className = 'panel detail-modal';

    const closeBtn = document.createElement('button');
    closeBtn.className = 'detail-close';
    closeBtn.type = 'button';
    closeBtn.textContent = 'Close';
    closeBtn.addEventListener('click', closeModal);

    const header = document.createElement('div');
    header.className = 'detail-modal-header';
    const heading = document.createElement('h2');
    heading.id = 'detail-modal-title';
    heading.textContent = 'Song Details';
    header.appendChild(heading);
    header.appendChild(closeBtn);

    const fields = document.createElement('div');
    fields.className = 'detail-fields';
    const appendField = (label, value) => {
        const field = document.createElement('div');
        field.className = 'detail-field';
        const fieldLabel = document.createElement('span');
        fieldLabel.className = 'detail-field-label';
        fieldLabel.textContent = label;
        const fieldValue = document.createElement('span');
        fieldValue.className = 'detail-field-value';
        fieldValue.textContent = value;
        field.appendChild(fieldLabel);
        field.appendChild(fieldValue);
        fields.appendChild(field);
    };

    const link = document.createElement('a');
    link.className = 'button-link';
    link.href = safeStreamingLink(item.streaming_url, item.title, item.artist);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'Open in Spotify';

    if (item.image) {
        const img = document.createElement('img');
        img.src = item.image;
        img.alt = item.title || 'Album art';
        img.className = 'detail-art';
        modal.appendChild(img);
    }

    appendField('Title', item.title || '(unknown)');
    appendField('Artist', item.artist || '(unknown)');
    appendField('Album', item.album || '(unknown)');
    appendField('Genre', item.genre || '(not available)');
    appendField('Release date', item.release_date || '(not available)');

    modal.prepend(header);
    modal.appendChild(fields);
    modal.appendChild(link);

    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
    });
    overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });

    document.body.appendChild(overlay);
    closeBtn.focus();
}

function renderSettings() {
    const existing = document.getElementById('settings-section');
    if (existing) existing.remove();

    const section = document.createElement('section');
    section.id = 'settings-section';
    section.className = 'panel settings-panel';

    const heading = document.createElement('h2');
    heading.textContent = 'Privacy';

    const label = document.createElement('label');
    label.className = 'toggle-row';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'toggle-input';
    checkbox.checked = isHistoryEnabled();

    const text = document.createElement('span');
    text.className = 'toggle-copy';
    text.textContent = 'Save history in this session';

    checkbox.addEventListener('change', () => {
        setHistoryEnabled(checkbox.checked);
        if (!checkbox.checked) {
            clearHistory();
        }
        renderHistory();
    });

    label.appendChild(checkbox);
    label.appendChild(text);

    const note = document.createElement('div');
    note.className = 'settings-note';
    note.textContent = 'When off, recognized songs will not be stored in session history.';

    section.appendChild(heading);
    section.appendChild(label);
    section.appendChild(note);

    document.querySelector('.app-wrap').appendChild(section);
}

function renderHistory() {
    const history = loadHistory();
    const existing = document.getElementById('history-section');
    if (existing) existing.remove();

    const section = document.createElement('section');
    section.id = 'history-section';
    section.className = 'history-section';

    const h2 = document.createElement('h2');
    h2.className = 'section-heading';
    h2.textContent = 'History';
    section.appendChild(h2);

    if (!isHistoryEnabled()) {
        const disabled = document.createElement('div');
        disabled.textContent = 'History is turned off for this session.';
        section.appendChild(disabled);
    } else if (!history.length) {
        const empty = document.createElement('div');
        empty.textContent = 'No history yet.';
        section.appendChild(empty);
    } else {
        history.forEach((item, index) => {
            const card = document.createElement('div');
            card.className = 'history-card';

            const title = document.createElement('div');
            title.className = 'history-title';
            title.textContent = `Song: ${item.title || '(unknown)'}`;

            const artist = document.createElement('div');
            artist.className = 'history-artist';
            artist.textContent = `Artist: ${item.artist || '(unknown)'}`;

            const album = document.createElement('div');
            album.className = 'history-artist';
            album.textContent = `Album: ${item.album || '(unknown)'}`;

            const time = document.createElement('time');
            time.className = 'history-time';
            const timestamp = new Date(item.timestamp);
            if (!Number.isNaN(timestamp.getTime())) time.dateTime = timestamp.toISOString();
            time.textContent = `Recognized: ${new Date(item.timestamp).toLocaleString()}`;

            const actions = document.createElement('div');
            actions.className = 'history-actions';

            const copy = document.createElement('div');
            copy.className = 'history-copy';
            copy.appendChild(title);
            copy.appendChild(artist);
            copy.appendChild(album);
            copy.appendChild(time);

            const viewBtn = document.createElement('button');
            viewBtn.type = 'button';
            viewBtn.className = 'button-secondary';
            viewBtn.textContent = 'View Details';
            viewBtn.addEventListener('click', () => showDetailModal(item));

            const delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.className = 'button-secondary';
            delBtn.textContent = 'Remove';
            delBtn.addEventListener('click', () => {
                const updated = loadHistory();
                updated.splice(index, 1);
                saveHistory(updated);
                renderHistory();
            });

            actions.appendChild(viewBtn);
            actions.appendChild(delBtn);

            if (item.image) {
                const img = document.createElement('img');
                img.src = item.image;
                img.alt = item.title || 'Album art';
                img.className = 'history-art';
                card.appendChild(img);
            } else {
                const placeholder = document.createElement('div');
                placeholder.className = 'history-art history-art-placeholder';
                placeholder.setAttribute('aria-hidden', 'true');
                placeholder.textContent = '♪';
                card.appendChild(placeholder);
            }

            card.appendChild(copy);
            card.appendChild(actions);
            section.appendChild(card);
        });
    }

    document.querySelector('.app-wrap').appendChild(section);
}

async function refreshStatus() {
    try {
        const res = await fetch('/api/status');
        const s = await res.json();
        const backends = [
            ['RapidAPI / Shazam', s.rapidapi_configured],
            ['AcoustID', s.acoustid_configured],
            ['AudD', s.audd_configured],
            ['Local fingerprint index', s.local_index_configured]
        ];
        const configuredBackends = backends.filter(([, configured]) => configured).map(([name]) => name);
        const quotaMode = s.quota_mode || 'unknown';
        const quotaLabel = s.production_grade_quotas_enabled ? 'Production quota' : `Development quota (${quotaMode})`;

        statusDiv.dataset.state = configuredBackends.length ? 'ready' : 'idle';
        statusMessage.textContent = configuredBackends.length
            ? `${configuredBackends.length} recognition backend${configuredBackends.length === 1 ? '' : 's'} ready`
            : 'Development mode · add a recognition backend to identify audio';

        statusDetails.replaceChildren();
        const details = [
            ['Backends', configuredBackends.length ? configuredBackends.join(', ') : 'None configured'],
            ['Audio tools', `FFmpeg ${s.ffmpeg_on_path ? 'ready' : 'missing'} · fpcalc ${s.fpcalc_on_path ? 'ready' : 'missing'}`],
            ['Quota', `${quotaLabel} · ${s.daily_limit}/day · ${s.monthly_limit}/month`],
            ['Audio limits', `${s.min_audio_seconds}s–${s.max_audio_seconds}s · ${Math.round(s.max_upload_bytes / (1024 * 1024))} MiB upload`]
        ];
        details.forEach(([label, value]) => {
            const row = document.createElement('div');
            row.className = 'status-detail-row';
            const name = document.createElement('span');
            name.textContent = label;
            const detail = document.createElement('strong');
            detail.textContent = value;
            row.appendChild(name);
            row.appendChild(detail);
            statusDetails.appendChild(row);
        });
    } catch (err) {
        statusDiv.dataset.state = 'error';
        statusMessage.textContent = 'Runtime status unavailable';
        statusDetails.replaceChildren();
    }
}

function renderResultMessage(title, copy, tone = 'info', icon = 'i', code = '') {
    resultDiv.replaceChildren();
    resultDiv.dataset.state = tone;

    const message = document.createElement('div');
    message.className = 'result-message';
    message.dataset.tone = tone;

    const resultIcon = document.createElement('span');
    resultIcon.className = 'result-icon';
    resultIcon.setAttribute('aria-hidden', 'true');
    resultIcon.textContent = icon;

    const content = document.createElement('div');
    content.className = 'result-content';
    const titleNode = document.createElement('div');
    titleNode.className = 'result-title';
    titleNode.textContent = title;
    const copyNode = document.createElement('div');
    copyNode.className = 'result-copy';
    copyNode.textContent = copy;
    content.appendChild(titleNode);
    content.appendChild(copyNode);
    if (code) {
        const codeNode = document.createElement('div');
        codeNode.className = 'result-code';
        codeNode.textContent = code;
        content.appendChild(codeNode);
    }

    message.appendChild(resultIcon);
    message.appendChild(content);
    resultDiv.appendChild(message);
}

function renderRetryButton() {
    const retryBtn = document.createElement('button');
    retryBtn.className = 'button-secondary retry-button';
    retryBtn.type = 'button';
    retryBtn.textContent = 'Retry';
    retryBtn.disabled = isSubmitting;
    retryBtn.addEventListener('click', () => {
        if (lastFile) postFile(lastFile);
        else renderResultMessage('Nothing to retry yet', 'Choose an audio clip to begin.', 'info', 'i');
    });
    resultDiv.appendChild(retryBtn);
}

async function postFile(file) {
    if (isSubmitting) return;

    lastFile = file;
    setSubmittingState(true);

    const fd = new FormData();
    fd.append('file', file, file.name || 'upload.audio');
    renderResultMessage('Preparing your audio…', 'Validating a bounded clip and checking the configured recognition backends.', 'info', '…');

    try {
        const res = await fetch('/api/match', { method: 'POST', body: fd });
        const data = await res.json();
        renderResult(data);
        await refreshStatus();
    } catch (err) {
        renderResultMessage('Upload failed', 'The audio could not reach the recognition service. Check your connection and try again.', 'error', '!');
        renderRetryButton();
    } finally {
        setSubmittingState(false);
    }
}

function renderResult(data) {
    if (!data) {
        renderResultMessage('No response received', 'The recognition service returned no usable response.', 'error', '!');
        renderRetryButton();
        return;
    }
    if (data.status === 'rate_limited') {
        renderResultMessage('Please wait before trying again', data.error || 'Too many requests. Please wait and try again.', 'error', '⏱');
        return;
    }
    if (data.status === 'not_configured') {
        renderResultMessage('Recognition is not configured yet', data.error || 'Add a recognition provider or local fingerprint index to identify audio.', 'info', 'i');
        renderRetryButton();
        return;
    }
    if (data.status === 'invalid_audio') {
        renderResultMessage('That audio clip could not be used', data.error || 'Audio was rejected. Choose a supported clip and try again.', 'error', '!', data.error_code || 'invalid_audio');
        renderRetryButton();
        return;
    }
    if (data.status === 'error') {
        renderResultMessage('Recognition hit a problem', data.error || 'The server could not complete recognition.', 'error', '!');
        renderRetryButton();
        return;
    }
    if (data.status === 'no_match') {
        renderResultMessage('No match found', 'Try a clearer clip with less background noise, or move closer to the source.', 'info', '♪');
        renderRetryButton();
        return;
    }

    resultDiv.replaceChildren();
    resultDiv.dataset.state = 'matched';

    const card = document.createElement('article');
    card.className = 'match-card';

    const main = document.createElement('div');
    main.className = 'match-card-main';

    let artwork;
    if (data.image) {
        artwork = document.createElement('img');
        artwork.src = data.image;
        artwork.alt = data.title || 'Album art';
        artwork.className = 'match-art';
        artwork.loading = 'lazy';
        artwork.referrerPolicy = 'no-referrer';
    } else {
        artwork = document.createElement('div');
        artwork.className = 'match-art match-art-placeholder';
        artwork.setAttribute('role', 'img');
        artwork.setAttribute('aria-label', 'Album art unavailable');
        artwork.textContent = '♪';
    }

    const copy = document.createElement('div');
    copy.className = 'match-copy';
    const matchLabel = document.createElement('div');
    matchLabel.className = 'match-label';
    matchLabel.textContent = 'Match found';
    const title = document.createElement('h3');
    title.className = 'match-title';
    title.textContent = data.title || '(unknown)';
    const artist = document.createElement('div');
    artist.className = 'match-artist';
    artist.textContent = data.artist || '(unknown)';
    const album = document.createElement('div');
    album.className = 'match-album';
    album.textContent = data.album || '(unknown)';
    copy.appendChild(matchLabel);
    copy.appendChild(title);
    copy.appendChild(artist);
    copy.appendChild(album);

    main.appendChild(artwork);
    main.appendChild(copy);

    const detailBtn = document.createElement('button');
    detailBtn.className = 'button-secondary';
    detailBtn.type = 'button';
    detailBtn.textContent = 'View details';

    const streamingLink = document.createElement('a');
    streamingLink.className = 'button-link';
    streamingLink.href = safeStreamingLink(data.streaming_url, data.title, data.artist);
    streamingLink.target = '_blank';
    streamingLink.rel = 'noopener noreferrer';
    streamingLink.textContent = 'Open in Spotify';

    const actions = document.createElement('div');
    actions.className = 'match-actions';

    const item = {
        title: data.title || '',
        artist: data.artist || '',
        album: data.album || '',
        genre: data.genre || '',
        release_date: data.release_date || '',
        image: data.image || '',
        streaming_url: safeStreamingLink(data.streaming_url, data.title, data.artist),
        timestamp: Date.now()
    };

    detailBtn.addEventListener('click', () => showDetailModal(item));
    actions.appendChild(detailBtn);
    actions.appendChild(streamingLink);
    card.appendChild(main);
    card.appendChild(actions);
    resultDiv.appendChild(card);

    addToHistory(item);
    renderHistory();
}

refreshStatus();
setThemeFromStorage();
renderSettings();
renderHistory();
setMicLabel();

if (statusToggle) {
    statusToggle.addEventListener('click', () => {
        const expanded = statusToggle.getAttribute('aria-expanded') === 'true';
        statusToggle.setAttribute('aria-expanded', String(!expanded));
        statusDetails.hidden = expanded;
        statusToggle.textContent = expanded ? 'View details' : 'Hide details';
    });
}

uploadBtn.addEventListener('click', () => {
    const f = fileInput.files[0];
    if (!f) {
        renderResultMessage('Select an audio file first', 'Choose a supported clip below, then try the upload again.', 'info', '↑');
        return;
    }
    postFile(f);
});

recBtn.addEventListener('click', async () => {
    if (isSubmitting || isListening) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        renderResultMessage('Microphone unavailable', 'This browser does not expose microphone capture. Use an audio file instead.', 'error', '!');
        renderRetryButton();
        return;
    }

    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        chunks = [];
        mediaRecorder = new MediaRecorder(mediaStream);

        ensureVisualizerNode(mediaStream);
        startVisualizerLoop();

        mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) chunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            if (stopTimer) {
                clearTimeout(stopTimer);
                stopTimer = null;
            }

            stopMediaStream();

            stopVisualizer();
            setListeningState(false);
            isProcessing = true;
            setMicLabel();

            const blob = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' });
            chunks = [];

            if (blob.size === 0) {
                renderResultMessage('No audio was recorded', 'Try again and keep the microphone permission active while listening.', 'error', '!');
                renderRetryButton();
                recBtn.disabled = false;
                stopBtn.disabled = true;
                isProcessing = false;
                setMicLabel();
                return;
            }

            const file = new File([blob], 'recording.webm', { type: blob.type });
            recBtn.disabled = true;
            stopBtn.disabled = true;
            await postFile(file);
            isProcessing = false;
            setMicLabel();
        };

        mediaRecorder.start(1000);
        setListeningState(true);
        renderResultMessage('Listening…', 'The waveform is live. Stop when you have enough audio, or wait for the 10-second limit.', 'info', '◉');

        stopTimer = setTimeout(() => {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
            recBtn.disabled = false;
            stopBtn.disabled = true;
            if (captureHint) captureHint.textContent = 'Recording stopped automatically after 10 seconds.';
        }, 10000);
    } catch (err) {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            try { mediaRecorder.stop(); } catch { }
        }
        mediaRecorder = null;
        stopMediaStream();
        stopVisualizer();
        setListeningState(false);
        renderResultMessage('Microphone access failed', 'Allow microphone access or choose an audio file instead.', 'error', '!');
        renderRetryButton();
        recBtn.disabled = false;
        stopBtn.disabled = true;
    }
});

stopBtn.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        recBtn.disabled = true;
        stopBtn.disabled = true;
    }
});
