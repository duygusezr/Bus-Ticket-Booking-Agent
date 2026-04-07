/**
 * js/audio.js
 * Web Audio API başlatma, ses çalma (base64 MP3),
 * ses açma/kapama, VAD (Voice Activity Detection) tabanlı STT.
 *
 * VAD Mantığı:
 *  - Mikrofon sürekli açık tutulur (toggle ile).
 *  - Ses seviyesi eşiği (VAD_THRESHOLD) aşılınca kayıt başlar.
 *  - Ses seviyesi eşiğin altında kalırsa ve SILENCE_DURATION_MS
 *    geçerse kayıt durur ve STT'ye gönderilir.
 *  - Ela konuşurken (isSpeaking=true) mikrofon sessizce dinler
 *    ama kayıt başlatmaz (eko koruması).
 */
import { setSpeaking, setListening, setActiveSource, setAnalyser, stopLipSync } from './avatar.js';

// ─── Sabitler ─────────────────────────────────────────────────
const VAD_THRESHOLD        = 18;    // 0-255 arası ses seviyesi eşiği
const SILENCE_DURATION_MS  = 1200; // Bu kadar sessizlik olursa kayıt biter (ms)
const MIN_SPEECH_DURATION_MS = 400; // Çok kısa sesleri (gürültü) atlamak için minimum kayıt süresi (ms)

// ─── Modül durumu ─────────────────────────────────────────────
let audioCtx       = null;
let analyser       = null;
let dataArray      = null;
let isAudioMuted   = false;
let _activeSource  = null;

// VAD durumu
let vadActive           = false;  // Kullanıcı VAD'ı açtı mı?
let isSpeaking          = false;  // Ela şu an konuşuyor mu? (kayıt engellenir)
let micStream           = null;   // Sürekli açık tutulan mikrofon stream'i
let micAnalyser         = null;   // Mikrofona özel analyser (Ela sesinden bağımsız)
let micDataArray        = null;
let vadRafId            = null;   // requestAnimationFrame ID
let isRecording         = false;  // VAD kaydı aktif mi?
let mediaRecorder       = null;
let audioChunks         = [];
let silenceTimer        = null;
let speechStartTime     = null;

// ─── WebAudio başlatma ────────────────────────────────────────

export async function initWebAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.85;
        dataArray = new Uint8Array(analyser.frequencyBinCount);
        setAnalyser(analyser, dataArray);
    }
    if (audioCtx.state === 'suspended') await audioCtx.resume();
}

// ─── Ses durdurma ────────────────────────────────────────────

export function stopAudio() {
    if (_activeSource) {
        try { _activeSource.stop(); } catch (_) {}
        _activeSource = null;
        setActiveSource(null);
    }
    setSpeaking(false);
    stopLipSync();
    isSpeaking = false;
}

// ─── Ela konuşma durumu setter (chat.js'den çağrılır) ─────────

export function setElaSpeaking(val) {
    isSpeaking = val;
}

// ─── Base64 MP3 çalma ────────────────────────────────────────

export async function playBase64Audio(base64Str) {
    if (!audioCtx) await initWebAudio();
    const chatInput = document.getElementById('chat-input');
    if (chatInput?.value.trim().length > 0) return;

    try {
        const res = await fetch(`data:audio/mpeg;base64,${base64Str}`);
        const arrayBuffer = await res.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

        stopAudio();
        isSpeaking = true; // Ela konuşmaya başlıyor → VAD kayıt başlatmaz

        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        _activeSource = source;
        setActiveSource(source);
        setSpeaking(true);

        source.onended = () => {
            if (_activeSource === source) {
                _activeSource = null;
                setActiveSource(null);
                setSpeaking(false);
            }
            isSpeaking = false; // Ela bitti → VAD tekrar dinleyebilir
        };

        source.connect(analyser);
        if (!isAudioMuted) analyser.connect(audioCtx.destination);
        source.start(0);
    } catch (e) {
        isSpeaking = false;
        setSpeaking(false);
        const subtitle = document.getElementById('subtitle');
        if (subtitle) subtitle.textContent = 'Ses çalınamadı.';
    }
}

// ─── Ses açma/kapama ─────────────────────────────────────────

export function toggleMute(audioBtn) {
    isAudioMuted = !isAudioMuted;
    audioBtn.innerHTML = isAudioMuted
        ? '<i class="fa-solid fa-volume-xmark"></i>'
        : '<i class="fa-solid fa-volume-high"></i>';
    if (analyser && audioCtx) {
        if (isAudioMuted) {
            try { analyser.disconnect(audioCtx.destination); } catch (_) {}
        } else {
            try { analyser.connect(audioCtx.destination); } catch (_) {}
        }
    }
}

// ─── VAD: Ses seviyesini ölç ──────────────────────────────────

function getVolume() {
    if (!micAnalyser || !micDataArray) return 0;
    micAnalyser.getByteFrequencyData(micDataArray);
    let sum = 0;
    for (let i = 0; i < micDataArray.length; i++) sum += micDataArray[i];
    return sum / micDataArray.length;
}

// ─── VAD: Kayıt başlat ────────────────────────────────────────

function startVadRecording() {
    if (isRecording || !micStream) return;
    isRecording = true;
    audioChunks = [];
    speechStartTime = Date.now();

    try {
        const options = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? { mimeType: 'audio/webm;codecs=opus' }
            : { mimeType: 'audio/webm' };
        mediaRecorder = new MediaRecorder(micStream, options);
    } catch {
        mediaRecorder = new MediaRecorder(micStream);
    }

    mediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.start(100); // Her 100ms'de chunk gönder
}

// ─── VAD: Kayıt durdur ve STT'ye gönder ──────────────────────

function stopVadRecording(onTranscript, apiBase, lang, subtitle) {
    if (!isRecording || !mediaRecorder) return;
    isRecording = false;

    const elapsed = Date.now() - (speechStartTime || 0);

    mediaRecorder.onstop = async () => {
        if (elapsed < MIN_SPEECH_DURATION_MS) return; // Çok kısa → gürültü, atla

        const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        if (blob.size < 1000) return; // Boş blob

        if (subtitle) subtitle.textContent = 'Anlıyorum...';

        const formData = new FormData();
        formData.append('file', blob, 'recording.webm');
        formData.append('lang', lang());
        try {
            const res = await fetch(`${apiBase}/api/stt`, { method: 'POST', body: formData });
            if (res.ok) {
                const data = await res.json();
                if (data.text?.trim().length > 0) {
                    onTranscript(data.text);
                    if (subtitle) subtitle.textContent = '';
                } else {
                    if (subtitle) subtitle.textContent = '';
                }
            } else if (res.status === 429) {
                if (subtitle) subtitle.textContent = 'Ses servisi yoğun, biraz bekle.';
            } else {
                if (subtitle) subtitle.textContent = '';
            }
        } catch (err) {
            if (subtitle) subtitle.textContent = err.message?.includes('Failed to fetch')
                ? 'Backend bağlantısı yok.'
                : '';
        }
    };

    try {
        if (mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    } catch (_) {}
}

// ─── VAD: Ana döngü ───────────────────────────────────────────

function vadLoop(onTranscript, apiBase, lang, subtitle, micBtn) {
    if (!vadActive) return;

    const volume = getVolume();
    const speakingNow = volume > VAD_THRESHOLD;

    if (speakingNow) {
        // Sessizlik sayacını sıfırla
        if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
        }
        // Ela konuşmuyorsa ve kayıt başlamamışsa başlat
        if (!isSpeaking && !isRecording) {
            if (subtitle) subtitle.textContent = 'Dinliyorum...';
            startVadRecording();
        }
    } else {
        // Sessizlik: kayıt aktifse ve timer yoksa sayacı başlat
        if (isRecording && !silenceTimer) {
            silenceTimer = setTimeout(() => {
                silenceTimer = null;
                if (subtitle) subtitle.textContent = '';
                stopVadRecording(onTranscript, apiBase, lang, subtitle);
            }, SILENCE_DURATION_MS);
        }
    }

    vadRafId = requestAnimationFrame(() =>
        vadLoop(onTranscript, apiBase, lang, subtitle, micBtn)
    );
}

// ─── VAD: Aç/Kapat (Toggle) ───────────────────────────────────

export async function toggleVAD(micBtn, onTranscript, apiBase, lang, subtitle) {
    await initWebAudio();

    if (vadActive) {
        // ── VAD'ı kapat ──
        vadActive = false;
        if (vadRafId) { cancelAnimationFrame(vadRafId); vadRafId = null; }
        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            try { mediaRecorder.stop(); } catch (_) {}
        }
        if (micStream) {
            micStream.getTracks().forEach(t => t.stop());
            micStream = null;
        }
        micAnalyser = null;
        micDataArray = null;
        isRecording = false;
        setListening(false);

        micBtn.classList.remove('vad-active', 'recording');
        micBtn.title = 'Sesi etkinleştir';
        if (subtitle) subtitle.textContent = '';
    } else {
        // ── VAD'ı aç ──
        try {
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000,
                }
            });
        } catch {
            if (subtitle) subtitle.textContent = 'Mikrofon izni gerekli.';
            return;
        }

        // Mikrofona özel analyser (Ela sesinden bağımsız, sadece mic ölçmek için)
        const micSource = audioCtx.createMediaStreamSource(micStream);
        micAnalyser = audioCtx.createAnalyser();
        micAnalyser.fftSize = 512;
        micAnalyser.smoothingTimeConstant = 0.3;
        micDataArray = new Uint8Array(micAnalyser.frequencyBinCount);
        micSource.connect(micAnalyser);
        // Not: micAnalyser destination'a bağlamıyoruz → hoparlörden geri besleme olmaz

        vadActive = true;
        setListening(true);

        micBtn.classList.add('vad-active');
        micBtn.title = 'Dinlemeyi durdur';
        if (subtitle) subtitle.textContent = 'Sizi dinliyorum...';

        vadLoop(onTranscript, apiBase, lang, subtitle, micBtn);
    }
}

// ─── Eski basılı-tut API'si (artık kullanılmıyor, geriye dönük uyumluluk) ──

export function startRecording() {}
export function stopRecording() {}
