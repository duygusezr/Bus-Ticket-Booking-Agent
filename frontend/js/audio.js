/**
 * js/audio.js
 * Web Audio API başlatma, ses çalma (base64 MP3),
 * ses açma/kapama, mikrofon kaydı (STT).
 */
import { setSpeaking, setListening, setActiveSource, setAnalyser, stopLipSync } from './avatar.js';

let audioCtx = null;
let analyser = null;
let dataArray = null;
let isAudioMuted = false;
let _activeSource = null;

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
}

// ─── Base64 MP3 çalma ────────────────────────────────────────

export async function playBase64Audio(base64Str) {
    if (!audioCtx) await initWebAudio();
    // Kullanıcı yazıyorsa veya dinliyorsa çalma
    const chatInput = document.getElementById('chat-input');
    if (chatInput?.value.trim().length > 0) return;

    try {
        const res = await fetch(`data:audio/mpeg;base64,${base64Str}`);
        const arrayBuffer = await res.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

        stopAudio();

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
        };

        source.connect(analyser);
        if (!isAudioMuted) analyser.connect(audioCtx.destination);
        source.start(0);
    } catch (e) {
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

// ─── Mikrofon (STT) ───────────────────────────────────────────

let mediaRecorder = null;
let audioChunks = [];

export function startRecording(onTranscript, apiBase, lang, subtitle) {
    stopAudio();
    initWebAudio().then(() => {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                audioChunks = [];
                mediaRecorder.ondataavailable = e => {
                    if (e.data.size > 0) audioChunks.push(e.data);
                };
                mediaRecorder.onstop = async () => {
                    if (subtitle) subtitle.textContent = 'Ses işleniyor...';
                    const blob = new Blob(audioChunks, { type: 'audio/webm' });
                    if (blob.size === 0) {
                        if (subtitle) subtitle.textContent = 'Ses kaydedilemedi.';
                        return;
                    }
                    const formData = new FormData();
                    formData.append('file', blob, 'recording.webm');
                    formData.append('lang', lang());
                    try {
                        const res = await fetch(`${apiBase}/api/stt`, { method: 'POST', body: formData });
                        if (res.ok) {
                            const data = await res.json();
                            if (data.text?.trim().length > 0) {
                                onTranscript(data.text);
                            } else {
                                if (subtitle) subtitle.textContent = 'Sesi anlayamadım.';
                            }
                        } else if (res.status === 429) {
                            if (subtitle) subtitle.textContent = 'Ses servisi yoğun, 2 saniye bekleyip tekrar dene.';
                        } else {
                            if (subtitle) subtitle.textContent = 'Ses anlaşılamadı, tekrar deneyin.';
                        }
                    } catch (err) {
                        if (subtitle) subtitle.textContent = err.message?.includes('Failed to fetch')
                            ? 'Backend bağlantısı yok.'
                            : 'Ses işlenemedi.';
                    }
                    stream.getTracks().forEach(t => t.stop());
                };
                mediaRecorder.start();
                setListening(true);
            })
            .catch(() => {
                if (subtitle) subtitle.textContent = 'Lütfen mikrofon izni verin.';
            });
    });
}

export function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    setListening(false);
}
