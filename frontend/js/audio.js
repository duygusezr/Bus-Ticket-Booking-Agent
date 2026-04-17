/**
 * js/audio.js
 *
 * VAD sistemi — barge-in destekli:
 *  - Mikrofon sürekli açık (toggle ile aç/kapat).
 *  - Ela konuşurken sen de konuşabilirsin → Ela hemen durur, seni dinler.
 *  - İlk kelimeni kaçırmamak için kayıt barge-in anında başlar.
 *  - Eko koruması: Ela'nın sesinin hoparlörden mikrofona geri dönmemesi için
 *    echoCancellation + ayrı micAnalyser (destination'a bağlanmıyor).
 *
 * Eşikler:
 *  BARGE_IN_THRESHOLD  — Ela konuşurken bu değeri aşarsan seni kesiyor (düşük)
 *  VAD_THRESHOLD       — Normal sessizlikte kayıt başlatma eşiği (biraz daha yüksek)
 *  SILENCE_DURATION_MS — Bu kadar sessizlik → kayıt biter, STT'ye gider
 *  MIN_SPEECH_MS       — Daha kısa ses → gürültü, atlanır
 */
import { setSpeaking, setListening, setActiveSource, setAnalyser, stopLipSync } from './avatar.js';

// ─── Sabitler ─────────────────────────────────────────────────
const VAD_THRESHOLD       = 25;   // Normal dinleme eşiği (yükseltildi: 15 → 25)
const BARGE_IN_THRESHOLD  = 18;   // Avatar konuşurken barge-in eşiği (yükseltildi: 12 → 18)
const SILENCE_DURATION_MS = 1200; // Sessizlik süresi → kayıt biter (uzatıldı: 1000 → 1200ms)
const MIN_SPEECH_MS       = 250;  // Kısa kelimeler kaybolmasın (600 → 250ms)
const VAD_CONFIRM_FRAMES  = 1;    // Kayıt hemen başlasın — MIN_SPEECH_MS gürültüyü zaten filtreler
const POST_SPEECH_COOLDOWN_MS = 800; // Avatar bittikten sonra VAD'nin bekleyeceği süre (ms)

// ─── Modül durumu ─────────────────────────────────────────────
let audioCtx      = null;
let analyser      = null;   // Ela sesi için (lip-sync)
let dataArray     = null;
let isAudioMuted  = false;
let _activeSource = null;

let elaIsSpeaking = false;  // Ela şu an hoparlörden konuşuyor mu?

// VAD
let vadActive      = false;
let micStream      = null;
let micAnalyser    = null;
let micDataArray   = null;
let vadRafId       = null;
let isRecording    = false;
let mediaRecorder  = null;
let audioChunks    = [];
let silenceTimer   = null;
let speechStartTime = null;
let aboveThresholdFrames = 0;  // Kaç frame boyunca eşiği aştık — anlık spike'ları filtreler
let vadCooldownUntil = 0;      // Bu timestamp'e kadar VAD kayıt başlatmıyor (avatar sonrası cooldown)

// Geri çağırmalar (vadLoop'a parametre yerine modül düzeyinde saklanır)
let _onTranscript = null;
let _apiBase      = null;
let _getLang      = null;
let _subtitle     = null;
let _micBtn       = null;

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

// ─── Ses seviyesi ölçümü ──────────────────────────────────────

function getMicVolume() {
    if (!micAnalyser || !micDataArray) return 0;
    micAnalyser.getByteFrequencyData(micDataArray);
    // Konuşma frekans bandına odaklan (300 Hz - 3400 Hz arası)
    const binCount = micDataArray.length;
    const sampleRate = audioCtx.sampleRate;
    const binHz = sampleRate / (micAnalyser.fftSize);
    const lowBin  = Math.floor(300  / binHz);
    const highBin = Math.min(Math.floor(3400 / binHz), binCount - 1);
    let sum = 0;
    for (let i = lowBin; i <= highBin; i++) sum += micDataArray[i];
    return sum / (highBin - lowBin + 1);
}

// ─── Ela'yı durdur (barge-in) ────────────────────────────────

function stopEla() {
    if (_activeSource) {
        try { _activeSource.stop(); } catch (_) {}
        _activeSource = null;
        setActiveSource(null);
    }
    setSpeaking(false);
    stopLipSync();
    elaIsSpeaking = false;
}

// ─── Ses durdurma (dışarıdan çağrılır) ───────────────────────

export function stopAudio() {
    stopEla();
}

// ─── VAD kaydını başlat ───────────────────────────────────────

function startVadRecording() {
    if (isRecording || !micStream) return;
    isRecording = true;
    audioChunks = [];
    speechStartTime = Date.now();

    try {
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : 'audio/webm';
        mediaRecorder = new MediaRecorder(micStream, { mimeType });
    } catch {
        mediaRecorder = new MediaRecorder(micStream);
    }

    mediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.start(80); // 80ms chunk → düşük gecikme

    if (_micBtn) _micBtn.classList.add('recording');
    if (_subtitle) _subtitle.textContent = 'Dinliyorum...';
}

// ─── VAD kaydını durdur ve STT'ye gönder ─────────────────────

function stopVadRecording() {
    if (!isRecording || !mediaRecorder) return;
    isRecording = false;

    const elapsed = Date.now() - (speechStartTime || 0);
    if (_micBtn) _micBtn.classList.remove('recording');

    mediaRecorder.onstop = async () => {
        if (elapsed < MIN_SPEECH_MS) {
            // Çok kısa → gürültü
            if (_subtitle) _subtitle.textContent = 'Sizi dinliyorum...';
            return;
        }

        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const blob = new Blob(audioChunks, { type: mimeType });
        if (blob.size < 200) {
            if (_subtitle) _subtitle.textContent = 'Sizi dinliyorum...';
            return;
        }

        if (_subtitle) _subtitle.textContent = 'Anlıyorum...';

        const formData = new FormData();
        formData.append('file', blob, 'recording.webm');
        formData.append('lang', _getLang());

        try {
            const res = await fetch(`${_apiBase}/api/stt`, { method: 'POST', body: formData });
            if (res.ok) {
                const data = await res.json();
                const text = data.text?.trim();
                if (text && text.length > 0) {
                    if (_subtitle) _subtitle.textContent = '';
                    _onTranscript(text);
                } else {
                    if (_subtitle) _subtitle.textContent = 'Sizi dinliyorum...';
                }
            } else if (res.status === 429) {
                if (_subtitle) _subtitle.textContent = 'Ses servisi yoğun, lütfen tekrar konuşun.';
                setTimeout(() => {
                    if (_subtitle) _subtitle.textContent = 'Sizi dinliyorum...';
                }, 2000);
            } else {
                if (_subtitle) _subtitle.textContent = 'Sizi dinliyorum...';
            }
        } catch (err) {
            if (_subtitle) _subtitle.textContent = err.message?.includes('Failed to fetch')
                ? 'Backend bağlantısı yok.'
                : 'Sizi dinliyorum...';
        }
    };

    try {
        if (mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    } catch (_) {}
}

// ─── VAD ana döngüsü ──────────────────────────────────────────

function vadLoop() {
    if (!vadActive) return;

    const volume = getMicVolume();
    const threshold = elaIsSpeaking ? BARGE_IN_THRESHOLD : VAD_THRESHOLD;
    const userIsTalking = volume > threshold;

    if (userIsTalking) {
        aboveThresholdFrames++;

        // Sessizlik sayacını iptal et
        if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
        }

        // Barge-in: eşik 1 frame'de aşılırsa hemen durdur (kullanıcının ilk hecesi kaybolmasın)
        if (elaIsSpeaking && aboveThresholdFrames >= 1) {
            stopEla();
            if (!isRecording) startVadRecording();
        } else if (!elaIsSpeaking && aboveThresholdFrames >= VAD_CONFIRM_FRAMES && !isRecording) {
            // Normal dinleme: VAD_CONFIRM_FRAMES kadar sürekli ses gelirse başlat
            // → Kapı çarpılması, öksürme, kısa gürültüler tetiklemiyor
            // → Avatar yeni bitmisse cooldown süresinde kayda başlatma
            if (Date.now() > vadCooldownUntil) {
                startVadRecording();
            }
        }
    } else {
        // Ses eşiğin altında — sayacı sıfırla
        aboveThresholdFrames = 0;

        // Sessizlik
        if (isRecording && !silenceTimer) {
            silenceTimer = setTimeout(() => {
                silenceTimer = null;
                stopVadRecording();
            }, SILENCE_DURATION_MS);
        }
    }

    vadRafId = requestAnimationFrame(vadLoop);
}

// ─── Base64 MP3 çalma ────────────────────────────────────────

export async function playBase64Audio(base64Str) {
    if (!audioCtx) await initWebAudio();

    // Yazı yazılıyorsa ses çalma
    const chatInput = document.getElementById('chat-input');
    if (chatInput?.value.trim().length > 0) return;

    try {
        const res = await fetch(`data:audio/mpeg;base64,${base64Str}`);
        const arrayBuffer = await res.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

        stopEla(); // Önceki sesi durdur

        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        _activeSource = source;
        setActiveSource(source);
        setSpeaking(true);
        elaIsSpeaking = true;

        source.onended = () => {
            if (_activeSource === source) {
                _activeSource = null;
                setActiveSource(null);
                setSpeaking(false);
            }
            elaIsSpeaking = false;
            // Avatar bitti → cooldown başlat, ortam sesleri hemen tetiklemesin
            vadCooldownUntil = Date.now() + POST_SPEECH_COOLDOWN_MS;
            aboveThresholdFrames = 0;
            // Ela bitti → subtitle'ı sıfırla
            if (_subtitle && vadActive) _subtitle.textContent = 'Sizi dinliyorum...';
        };

        source.connect(analyser);
        if (!isAudioMuted) analyser.connect(audioCtx.destination);
        source.start(0);
    } catch (e) {
        elaIsSpeaking = false;
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

// ─── VAD Toggle ───────────────────────────────────────────────

export async function toggleVAD(micBtn, onTranscript, apiBase, getLang, subtitle) {
    await initWebAudio();

    // Geri çağırmaları kaydet
    _onTranscript = onTranscript;
    _apiBase      = apiBase;
    _getLang      = getLang;
    _subtitle     = subtitle;
    _micBtn       = micBtn;

    if (vadActive) {
        // ── Kapat ──
        vadActive = false;
        if (vadRafId)    { cancelAnimationFrame(vadRafId); vadRafId = null; }
        if (silenceTimer){ clearTimeout(silenceTimer); silenceTimer = null; }
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
        elaIsSpeaking = false;
        aboveThresholdFrames = 0;
        setListening(false);

        micBtn.classList.remove('vad-active', 'recording');
        micBtn.title = 'Sesi etkinleştir';
        if (subtitle) subtitle.textContent = '';
    } else {
        // ── Aç ──
        try {
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,   // Tarayıcı seviyesi eko iptal
                    noiseSuppression: true,   // Arka plan gürültüsü azaltma
                    autoGainControl: true,    // Otomatik kazanç → ses seviyesini normalize eder
                    sampleRate: 16000,
                    channelCount: 1,
                }
            });
        } catch {
            if (subtitle) subtitle.textContent = 'Mikrofon izni gerekli.';
            return;
        }

        // Mikrofona özel ayrı analyser — Ela'nın analyser'ına bağlanmıyor
        // → Ela'nın hoparlör sesi bu analyser'a karışmaz
        const micSource = audioCtx.createMediaStreamSource(micStream);
        micAnalyser = audioCtx.createAnalyser();
        micAnalyser.fftSize = 1024; // Daha yüksek çözünürlük → frekans bandı daha hassas
        micAnalyser.smoothingTimeConstant = 0.2; // Hızlı tepki
        micDataArray = new Uint8Array(micAnalyser.frequencyBinCount);
        micSource.connect(micAnalyser);
        // ÖNEMLİ: micAnalyser → destination'a BAĞLANMIYOR
        // Yani mikrofon sesi hoparlörden çıkmıyor → geri besleme yok

        vadActive = true;
        setListening(true);

        micBtn.classList.add('vad-active');
        micBtn.title = 'Dinlemeyi durdur';
        if (subtitle) subtitle.textContent = 'Sizi dinliyorum...';

        vadLoop();
    }
}

// ─── Geriye dönük uyumluluk ──────────────────────────────────
export function startRecording() {}
export function stopRecording() {}
