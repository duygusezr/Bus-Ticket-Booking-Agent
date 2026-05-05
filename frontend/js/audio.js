/**
 * js/audio.js
 *
 * VAD sistemi — gelişmiş barge-in destekli.
 *
 * Eşikler:
 *  VAD_THRESHOLD            — Normal dinleme eşiği
 *  BARGE_IN_BASE            — Barge-in minimum eşiği (mutlak alt sınır)
 *  BARGE_IN_SPIKE_DELTA     — Noise floor üzerinde kaç birim yükselmeli
 *  NOISE_FLOOR_SAMPLES      — Noise floor için ortalaması alınacak frame sayısı
 *  SILENCE_DURATION_MS      — Normal sessizlik toleransı
 *  SILENCE_DURATION_NUMERIC — TC/telefon bağlamında uzatılmış tolerans
 *  MIN_SPEECH_MS            — Daha kısa ses → gürültü, atla
 *  POST_SPEECH_COOLDOWN_MS  — Avatar bittikten sonra VAD bekleme süresi
 *  AVATAR_SPEAKING_LINGER_MS   — Ses parçaları arası boşlukta avatarIsSpeaking'i koru
 */
import { setSpeaking, setListening, setActiveSource, setAnalyser, stopLipSync, applyRocketboxViseme, resetVisemeImmediate, textToVisemeIndices, setVisemeMode } from './avatar.js';

// ─── Sabitler ─────────────────────────────────────────────────
const VAD_THRESHOLD            = 40;   // Normal dinleme eşiği (artırıldı)
const BARGE_IN_BASE            = 25;   // Mutlak minimum barge-in eşiği (artırıldı)
const BARGE_IN_SPIKE_DELTA     = 20;   // Noise floor + bu değer = dinamik eşik (artırıldı)
const NOISE_FLOOR_SAMPLES      = 40;   // Kaç frame'in ortalaması noise floor
const SILENCE_DURATION_MS      = 1200;
const SILENCE_DURATION_NUMERIC = 2500;
const MIN_SPEECH_MS            = 200;  // Biraz daha kısa (eski: 250)
const VAD_CONFIRM_FRAMES       = 4;
const POST_SPEECH_COOLDOWN_MS  = 600;  // Biraz kısaltıldı (eski: 800)
const AVATAR_SPEAKING_LINGER_MS   = 300;  // Ses parçaları arası geçişte bekleme

// ─── Modül durumu ─────────────────────────────────────────────
let audioCtx      = null;
let analyser      = null;
let dataArray     = null;
let isAudioMuted  = false;
let _activeSource = null;
let avatarIsSpeaking = false;
let _avatarLingerTimer = null;  // ses parçaları arası geçiş zamanlayıcısı
let _activeAudioCount = 0;   // aynı anda kaç ses parçası oynatılıyor

// Noise floor (AI konuşurken ortam sesi tabanı)
let _noiseFloorSamples = [];
let _noiseFloor        = 0;

// VAD
let vadActive            = false;
let micStream            = null;
let micAnalyser          = null;
let micDataArray         = null;
let vadRafId             = null;
let isRecording          = false;
let mediaRecorder        = null;
let audioChunks          = [];
let silenceTimer         = null;
let speechStartTime      = null;
let aboveThresholdFrames = 0;
let vadCooldownUntil     = 0;

// Geri çağırmalar
let _onTranscript = null;
let _apiBase      = null;
let _getLang      = null;
let _subtitle     = null;
let _micBtn       = null;

// ─── Dile göre subtitle metni ────────────────────────────────

function getSubtitleText(key) {
    const lang = _getLang ? _getLang() : 'tr';
    const texts = {
        listening:  { tr: 'Sizi dinliyorum...', en: 'Listening...' },
        recording:  { tr: 'Dinliyorum...',      en: 'Recording...' },
        processing: { tr: 'Anlıyorum...',       en: 'Processing...' },
        busy:       { tr: 'Ses servisi yoğun, lütfen tekrar konuşun.', en: 'Audio service busy, please try again.' },
        noBackend:  { tr: 'Backend bağlantısı yok.', en: 'No backend connection.' },
    };
    return texts[key]?.[lang] ?? texts[key]?.tr ?? '';
}

// ─── Numeric context tespiti ──────────────────────────────────

function _isNumericContext() {
    const historyList = document.getElementById('history-list');
    if (!historyList) return false;
    const items = historyList.querySelectorAll('.history-item.ai .content');
    if (!items.length) return false;
    const lastMsg = items[items.length - 1].textContent.toLowerCase();
    const keywords = [
        'kimlik', 't.c.', 'tc', 'telefon', 'numara',
        'identity', 'national id', 'id number', 'phone number', 'digit',
    ];
    return keywords.some(kw => lastMsg.includes(kw));
}

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
    const binCount  = micDataArray.length;
    const sampleRate = audioCtx.sampleRate;
    const binHz     = sampleRate / micAnalyser.fftSize;
    const lowBin    = Math.floor(300  / binHz);
    const highBin   = Math.min(Math.floor(3400 / binHz), binCount - 1);
    let sum = 0;
    for (let i = lowBin; i <= highBin; i++) sum += micDataArray[i];
    return sum / (highBin - lowBin + 1);
}

// ─── Noise floor güncelle (AI konuşurken) ─────────────────────
// AI hoparlörden konuşurken mikrofona sızan sesi ölç.
// Kullanıcının sesi bu tabandan belirgin şekilde yüksek olmalı.

function _updateNoiseFloor(volume) {
    _noiseFloorSamples.push(volume);
    if (_noiseFloorSamples.length > NOISE_FLOOR_SAMPLES) _noiseFloorSamples.shift();
    _noiseFloor = _noiseFloorSamples.reduce((a, b) => a + b, 0) / _noiseFloorSamples.length;
}

function _resetNoiseFloor() {
    _noiseFloorSamples = [];
    _noiseFloor = 0;
}

// Dinamik barge-in eşiği: noise floor + spike delta, en az BARGE_IN_BASE
function _bargeInThreshold() {
    return Math.max(BARGE_IN_BASE, _noiseFloor + BARGE_IN_SPIKE_DELTA);
}

// ─── Avatar'ı durdur (barge-in) ───────────────────────────────

function stopAvatar() {
    if (_activeSource) {
        try { _activeSource.stop(); } catch (_) {}
        _activeSource = null;
        setActiveSource(null);
    }
    setSpeaking(false);
    stopLipSync();
    _clearVisemeTimers();
    resetVisemeImmediate();
    setVisemeMode(false);
    _activeAudioCount = 0;
    avatarIsSpeaking = false;
    if (_avatarLingerTimer) { clearTimeout(_avatarLingerTimer); _avatarLingerTimer = null; }
    _resetNoiseFloor();
}

export function stopAudio() { stopAvatar(); }

// ─── AI konuşma durumunu güvenli şekilde kapat ────────────────
// Ses parçaları arası geçişte hemen false yapmaz; kısa süre bekler.

function _scheduleAvatarEnd() {
    if (_avatarLingerTimer) { clearTimeout(_avatarLingerTimer); }
    _avatarLingerTimer = setTimeout(() => {
        _avatarLingerTimer = null;
        if (_activeAudioCount === 0) {
            avatarIsSpeaking = false;
            _resetNoiseFloor();
            vadCooldownUntil = Date.now() + POST_SPEECH_COOLDOWN_MS;
            aboveThresholdFrames = 0;
            if (_subtitle && vadActive) _subtitle.textContent = getSubtitleText('listening');
        }
    }, AVATAR_SPEAKING_LINGER_MS);
}

// ─── VAD kaydını başlat ───────────────────────────────────────

function startVadRecording() {
    if (isRecording || !micStream) return;
    isRecording = true;
    audioChunks = [];
    speechStartTime = Date.now();

    try {
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus' : 'audio/webm';
        mediaRecorder = new MediaRecorder(micStream, { mimeType });
    } catch {
        mediaRecorder = new MediaRecorder(micStream);
    }

    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.start(80);

    if (_micBtn) _micBtn.classList.add('recording');
    if (_subtitle) _subtitle.textContent = getSubtitleText('recording');
}

// ─── VAD kaydını durdur ve STT'ye gönder ─────────────────────

function stopVadRecording() {
    if (!isRecording || !mediaRecorder) return;
    isRecording = false;

    const elapsed = Date.now() - (speechStartTime || 0);
    if (_micBtn) _micBtn.classList.remove('recording');

    mediaRecorder.onstop = async () => {
        if (elapsed < MIN_SPEECH_MS) {
            if (_subtitle) _subtitle.textContent = getSubtitleText('listening');
            return;
        }

        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const blob = new Blob(audioChunks, { type: mimeType });
        if (blob.size < 200) {
            if (_subtitle) _subtitle.textContent = getSubtitleText('listening');
            return;
        }

        if (_subtitle) _subtitle.textContent = getSubtitleText('processing');

        const formData = new FormData();
        formData.append('file', blob, 'recording.webm');
        formData.append('lang', _getLang());
        const historyList = document.getElementById('history-list');
        const aiItems = historyList?.querySelectorAll('.history-item.ai .content');
        const lastAssistant = aiItems?.length ? aiItems[aiItems.length - 1].textContent : '';
        formData.append('last_assistant', lastAssistant.slice(0, 300));

        try {
            const res = await fetch(`${_apiBase}/api/stt`, { method: 'POST', body: formData });
            if (res.ok) {
                const data = await res.json();
                const text = data.text?.trim();
                const display = (data.display_text?.trim()) || text;
                if (text && text.length > 0) {
                    if (_subtitle) _subtitle.textContent = '';
                    _onTranscript(text, display);
                } else {
                    if (_subtitle) _subtitle.textContent = getSubtitleText('listening');
                }
            } else if (res.status === 429) {
                if (_subtitle) _subtitle.textContent = getSubtitleText('busy');
                setTimeout(() => { if (_subtitle) _subtitle.textContent = getSubtitleText('listening'); }, 2000);
            } else {
                if (_subtitle) _subtitle.textContent = getSubtitleText('listening');
            }
        } catch (err) {
            if (_subtitle) _subtitle.textContent = err.message?.includes('Failed to fetch')
                ? getSubtitleText('noBackend')
                : getSubtitleText('listening');
        }
    };

    try { if (mediaRecorder.state !== 'inactive') mediaRecorder.stop(); } catch (_) {}
}

// ─── VAD ana döngüsü ──────────────────────────────────────────

function vadLoop() {
    if (!vadActive) return;

    const volume    = getMicVolume();
    const silenceDuration = _isNumericContext()
        ? SILENCE_DURATION_NUMERIC
        : SILENCE_DURATION_MS;

    if (avatarIsSpeaking) {
        // ── AI konuşuyor: noise floor takibi + dinamik barge-in ──
        _updateNoiseFloor(volume);

        const threshold  = _bargeInThreshold();
        const userTalking = volume > threshold;

        if (userTalking) {
            aboveThresholdFrames++;
            if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }

            if (aboveThresholdFrames >= 5) {
                // Barge-in: AI'yı durdur, kullanıcıyı kaydet
                stopAvatar();
                vadCooldownUntil = 0; // barge-in sonrası cooldown yok
                if (!isRecording) startVadRecording();
            }
        } else {
            // Kullanıcı konuşmuyor ama AI konuşuyor — kayıt varsa sessizlik sayacı
            if (isRecording && !silenceTimer) {
                silenceTimer = setTimeout(() => {
                    silenceTimer = null;
                    stopVadRecording();
                }, silenceDuration);
            }
        }
    } else {
        // ── Normal mod: kullanıcı konuşuyor mu? ──────────────────
        const userTalking = volume > VAD_THRESHOLD;

        if (userTalking) {
            aboveThresholdFrames++;
            if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }

            if (aboveThresholdFrames >= VAD_CONFIRM_FRAMES && !isRecording) {
                if (Date.now() > vadCooldownUntil) {
                    startVadRecording();
                }
            }
        } else {
            aboveThresholdFrames = 0;
            if (isRecording && !silenceTimer) {
                silenceTimer = setTimeout(() => {
                    silenceTimer = null;
                    stopVadRecording();
                }, silenceDuration);
            }
        }
    }

    vadRafId = requestAnimationFrame(vadLoop);
}

// Viseme zamanlayıcıları
let _visemeTimers = [];

function _clearVisemeTimers() {
    for (const t of _visemeTimers) clearTimeout(t);
    _visemeTimers = [];
}

// Ünlü index seti (AA_VI 10-14)
const VOWEL_VI = new Set([10, 11, 12, 13, 14]);

/**
 * AudioBuffer genliği + metin fonemlerini birleştirerek gerçek zamanlamalı
 * viseme programı oluşturur.
 *
 * Yöntem:
 *   1. AudioBuffer'dan 20ms'lik frame'lerde RMS genliği ölç
 *   2. Sessiz frame'lerde ağız kapat (viseme 0)
 *   3. Sesli frame'lerde metin fonemlerini eşit dağıt
 *   4. Sadece değişim olduğunda timer ekle — minimum setTimeout sayısı
 */
function _scheduleAudioDrivenVisemes(audioBuffer, text, source) {
    _clearVisemeTimers();
    const phonemes = textToVisemeIndices(text);
    if (!phonemes.length) { setVisemeMode(false); return; }
    setVisemeMode(true);

    const data       = audioBuffer.getChannelData(0);
    const sr         = audioBuffer.sampleRate;
    const frameMs    = 20;                            // 20ms analiz penceresi
    const frameSamp  = Math.floor(sr * frameMs / 1000);
    const numFrames  = Math.ceil(data.length / frameSamp);

    // --- RMS hesapla ---
    const rms = new Float32Array(numFrames);
    let maxRms = 0;
    for (let f = 0; f < numFrames; f++) {
        const start = f * frameSamp;
        const end   = Math.min(start + frameSamp, data.length);
        let sum = 0;
        for (let j = start; j < end; j++) sum += data[j] * data[j];
        rms[f] = Math.sqrt(sum / (end - start));
        if (rms[f] > maxRms) maxRms = rms[f];
    }

    // Sessizlik eşiği: maksimum genliğin %8'i
    const threshold   = maxRms * 0.08;
    const totalSpeech = rms.reduce((n, v) => n + (v > threshold ? 1 : 0), 0);
    if (!totalSpeech) { setVisemeMode(false); return; }

    let speechCount  = 0;
    let lastVI       = -1;
    let wasSilent    = true;

    for (let f = 0; f < numFrames; f++) {
        const tMs    = f * frameMs;
        const silent = rms[f] <= threshold;

        if (silent) {
            if (!wasSilent) {
                // Sesten sessiğe geçiş → ağzı kapat
                const capturedT = tMs;
                _visemeTimers.push(setTimeout(() => {
                    if (_activeSource === source) applyRocketboxViseme(0);
                }, capturedT));
                lastVI = 0;
            }
        } else {
            // Sesli bölge → fonem ata
            const pi = Math.min(
                Math.floor(speechCount * phonemes.length / totalSpeech),
                phonemes.length - 1
            );
            const vi = phonemes[pi];
            if (vi !== lastVI) {
                const capturedVI = vi, capturedT = tMs;
                _visemeTimers.push(setTimeout(() => {
                    if (_activeSource === source) applyRocketboxViseme(capturedVI);
                }, capturedT));
                lastVI = vi;
            }
            speechCount++;
        }
        wasSilent = silent;
    }

    // Bitiminde kapat
    _visemeTimers.push(setTimeout(() => {
        if (_activeSource === source) resetVisemeImmediate();
    }, audioBuffer.duration * 1000 - 30));
}

// ─── Base64 MP3 çalma ────────────────────────────────────────

export async function playBase64Audio(base64Str, words = [], spokenText = '') {
    if (!audioCtx) await initWebAudio();

    const chatInput = document.getElementById('chat-input');
    if (chatInput?.value.trim().length > 0) return;

    try {
        const res         = await fetch(`data:audio/mpeg;base64,${base64Str}`);
        const arrayBuffer = await res.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

        // Önceki ses parçasını durdur (yeni gelen öncelikli)
        if (_activeSource) {
            try { _activeSource.stop(); } catch (_) {}
            _activeSource = null;
            setActiveSource(null);
        }

        // Linger timer varsa iptal et — hâlâ konuşuyoruz
        if (_avatarLingerTimer) { clearTimeout(_avatarLingerTimer); _avatarLingerTimer = null; }

        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        _activeSource = source;
        setActiveSource(source);
        setSpeaking(true);

        // Sayaç artır
        _activeAudioCount++;
        avatarIsSpeaking = true;

        source.onended = () => {
            _activeAudioCount = Math.max(0, _activeAudioCount - 1);
            if (_activeSource === source) {
                _activeSource = null;
                setActiveSource(null);
                setSpeaking(false);
            }
            _clearVisemeTimers();
            resetVisemeImmediate();
            setVisemeMode(false);
            _scheduleAvatarEnd();
        };

        source.connect(analyser);
        if (!isAudioMuted) analyser.connect(audioCtx.destination);
        source.start(0);
        // Backend'den kelime gelirse onu, yoksa spokenText üzerinden text-driven modunu çalıştır
        if (words && words.length) {
            // WordBoundary modu (backend yükseltilmişse)
            setVisemeMode(true);
            for (const [offsetMs, durationMs, wtext] of words) {
                const phonemes = textToVisemeIndices(wtext);
                const stepMs  = Math.max(35, durationMs / (phonemes.length || 1));
                phonemes.forEach((vi, i) => {
                    _visemeTimers.push(setTimeout(() => {
                        if (_activeSource === source) applyRocketboxViseme(vi);
                    }, offsetMs + i * stepMs));
                });
                _visemeTimers.push(setTimeout(() => {
                    if (_activeSource === source) applyRocketboxViseme(0, 0);
                }, offsetMs + durationMs));
            }
        } else if (spokenText) {
            _scheduleAudioDrivenVisemes(audioBuffer, spokenText, source);
        }
    } catch (e) {
        _activeAudioCount = Math.max(0, _activeAudioCount - 1);
        avatarIsSpeaking = _activeAudioCount > 0;
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

    _onTranscript = onTranscript;
    _apiBase      = apiBase;
    _getLang      = getLang;
    _subtitle     = subtitle;
    _micBtn       = micBtn;

    if (vadActive) {
        vadActive = false;
        if (vadRafId)     { cancelAnimationFrame(vadRafId); vadRafId = null; }
        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
        if (_avatarLingerTimer) { clearTimeout(_avatarLingerTimer); _avatarLingerTimer = null; }
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            try { mediaRecorder.stop(); } catch (_) {}
        }
        if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
        micAnalyser          = null;
        micDataArray         = null;
        isRecording          = false;
        avatarIsSpeaking        = false;
        _activeAudioCount    = 0;
        aboveThresholdFrames = 0;
        _resetNoiseFloor();
        setListening(false);

        micBtn.classList.remove('vad-active', 'recording');
        micBtn.title = 'Sesi etkinleştir';
        if (subtitle) subtitle.textContent = '';
    } else {
        try {
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl:  true,
                    sampleRate:       16000,
                    channelCount:     1,
                }
            });
        } catch {
            if (subtitle) subtitle.textContent = 'Mikrofon izni gerekli.';
            return;
        }

        const micSource = audioCtx.createMediaStreamSource(micStream);
        micAnalyser = audioCtx.createAnalyser();
        micAnalyser.fftSize = 1024;
        micAnalyser.smoothingTimeConstant = 0.2;
        micDataArray = new Uint8Array(micAnalyser.frequencyBinCount);
        micSource.connect(micAnalyser);
        // micAnalyser → destination'a BAĞLANMIYOR → geri besleme yok

        vadActive = true;
        setListening(true);

        micBtn.classList.add('vad-active');
        micBtn.title = 'Dinlemeyi durdur';
        if (subtitle) subtitle.textContent = getSubtitleText('listening');

        vadLoop();
    }
}

// ─── Geriye dönük uyumluluk ──────────────────────────────────
export function startRecording() {}
export function stopRecording() {}
