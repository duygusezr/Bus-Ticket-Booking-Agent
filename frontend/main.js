import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// ============================================================
// SAHNE KURULUMU
// ============================================================
const canvas = document.getElementById('canvas');
const canvasContainer = document.getElementById('canvas-container');

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);

const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
camera.position.set(0, 1.15, 1.3);

if (canvasContainer) {
    const resizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
            const { width, height } = entry.contentRect;
            if (width > 0 && height > 0) {
                camera.aspect = width / height;
                camera.updateProjectionMatrix();
                renderer.setSize(width, height);
            }
        }
    });
    resizeObserver.observe(canvasContainer);
} else {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
}

const directionalLight = new THREE.DirectionalLight(0xffffff, 2.0);
directionalLight.position.set(1, 1, 1).normalize();
scene.add(directionalLight);

const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
scene.add(ambientLight);

// ============================================================
// VRM MODEL YÜKLEME
// ============================================================
let currentVrm = undefined;
const loader = new GLTFLoader();
loader.register((parser) => new VRMLoaderPlugin(parser));

loader.load(
    './models/character.vrm',
    (gltf) => {
        const vrm = gltf.userData.vrm;
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.removeUnnecessaryJoints(gltf.scene);
        scene.add(vrm.scene);
        currentVrm = vrm;
        vrm.scene.rotation.y = 0;

        if (vrm.humanoid) {
            const leftUpperArm = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
            const rightUpperArm = vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
            if (leftUpperArm) leftUpperArm.rotation.z = -1.2;
            if (rightUpperArm) rightUpperArm.rotation.z = 1.2;

            const leftShoulder = vrm.humanoid.getNormalizedBoneNode('leftShoulder');
            const rightShoulder = vrm.humanoid.getNormalizedBoneNode('rightShoulder');
            if (leftShoulder) leftShoulder.rotation.z = -0.1;
            if (rightShoulder) rightShoulder.rotation.z = 0.1;

            cachedBones.head = vrm.humanoid.getNormalizedBoneNode('head');
            cachedBones.neck = vrm.humanoid.getNormalizedBoneNode('neck');
            cachedBones.spine = vrm.humanoid.getNormalizedBoneNode('spine');
            cachedBones.chest = vrm.humanoid.getNormalizedBoneNode('chest');
            cachedBones.upperChest = vrm.humanoid.getNormalizedBoneNode('upperChest');
        }

        if (vrm.lookAt) vrm.lookAt.autoUpdate = false;

        console.log('VRM başarıyla yüklendi!');
        startBlinking();
    },
    (progress) => console.log('Yükleniyor...', (100.0 * (progress.loaded / progress.total)).toFixed(2), '%'),
    (error) => {
        console.error('VRM yükleme hatası:', error);
        document.getElementById('subtitle').textContent = "Model yüklenemedi. 'models/character.vrm' dosyasını koyun.";
    }
);

// ============================================================
// ANA ANİMASYON DÖNGÜSÜ
// ============================================================
const clock = new THREE.Clock();
const fpsCounter = document.getElementById('fps-counter');
let frames = 0, lastTime = performance.now();

function animate() {
    requestAnimationFrame(animate);
    const deltaTime = clock.getDelta();
    const elapsed = clock.getElapsedTime();

    if (currentVrm) {
        currentVrm.update(deltaTime);
        updateBreathing(elapsed);
        updateIdleHeadMovement(elapsed, deltaTime);
        updateLipSync();
        updateActiveHeadMovement(elapsed, deltaTime);
        updateEyeMovement(elapsed, deltaTime);
    }

    renderer.render(scene, camera);

    frames++;
    const time = performance.now();
    if (time >= lastTime + 1000) {
        fpsCounter.innerHTML = `<i class="fa-solid fa-gauge"></i> FPS: ${Math.round((frames * 1000) / (time - lastTime))}`;
        frames = 0;
        lastTime = time;
    }
}
animate();

// ============================================================
// GÖZ KIRPMA
// ============================================================
function startBlinking() {
    const blink = () => {
        if (currentVrm?.expressionManager) {
            currentVrm.expressionManager.setValue('blink', 1.0);
            setTimeout(() => {
                if (currentVrm) currentVrm.expressionManager.setValue('blink', 0.0);
                if (Math.random() > 0.7) {
                    setTimeout(() => {
                        if (!currentVrm) return;
                        currentVrm.expressionManager.setValue('blink', 1.0);
                        setTimeout(() => { if (currentVrm) currentVrm.expressionManager.setValue('blink', 0.0); }, 80);
                    }, 120);
                }
            }, 100);
        }
        setTimeout(blink, 2000 + Math.random() * 4000);
    };
    blink();
}

// ============================================================
// NEFES ALMA HAREKETİ
// ============================================================
function updateBreathing(elapsed) {
    if (!currentVrm?.humanoid) return;

    const breathNorm = (Math.sin(elapsed * 0.35) + 1) / 2;

    const leftShoulder = currentVrm.humanoid.getNormalizedBoneNode('leftShoulder');
    const rightShoulder = currentVrm.humanoid.getNormalizedBoneNode('rightShoulder');
    if (leftShoulder) leftShoulder.rotation.x = -breathNorm * 0.12;
    if (rightShoulder) rightShoulder.rotation.x = -breathNorm * 0.12;

    const leftUpperArm = currentVrm.humanoid.getNormalizedBoneNode('leftUpperArm');
    const rightUpperArm = currentVrm.humanoid.getNormalizedBoneNode('rightUpperArm');
    if (leftUpperArm) leftUpperArm.rotation.z = -1.2 - breathNorm * 0.06;
    if (rightUpperArm) rightUpperArm.rotation.z = 1.2 + breathNorm * 0.06;

    const neck = cachedBones.neck;
    if (neck) neck.rotation.x = -breathNorm * 0.03;
}

// ============================================================
// BOŞ BEKLEME KAFA HAREKETİ (IDLE)
// ============================================================
const idleHead = { x: 0, y: 0, z: 0 };
let idleHeadTarget = { x: 0, y: 0, z: 0 };
let idleHeadTimer = 0;

function updateIdleHeadMovement(elapsed, delta) {
    if (!currentVrm || !cachedBones.head) return;

    if (isSpeaking || isListening) {
        const rs = Math.min(2.0 * delta, 1.0);
        idleHead.x += (0 - idleHead.x) * rs;
        idleHead.y += (0 - idleHead.y) * rs;
        idleHead.z += (0 - idleHead.z) * rs;
        cachedBones.head.rotation.x = idleHead.x;
        cachedBones.head.rotation.y = idleHead.y;
        cachedBones.head.rotation.z = idleHead.z;
        idleHeadTimer = 1.0;
        return;
    }

    idleHeadTimer -= delta;
    if (idleHeadTimer <= 0) {
        const r = Math.random();

        if (r < 0.30) {
            idleHeadTarget.y = 0;
            idleHeadTarget.x = 0;
            idleHeadTarget.z = 0;
            idleHeadTimer = 1.5 + Math.random() * 2;
        } else if (r < 0.48) {
            idleHeadTarget.y = 0.07 + Math.random() * 0.06;
            idleHeadTarget.x = 0;
            idleHeadTarget.z = idleHeadTarget.y * 0.10;
            idleHeadTimer = 3 + Math.random() * 4;
        } else if (r < 0.66) {
            idleHeadTarget.y = -(0.07 + Math.random() * 0.06);
            idleHeadTarget.x = 0;
            idleHeadTarget.z = idleHeadTarget.y * 0.10;
            idleHeadTimer = 3 + Math.random() * 4;
        } else if (r < 0.92) {
            idleHeadTarget.y = (Math.random() - 0.5) * 0.1;
            idleHeadTarget.x = 0.05 + Math.random() * 0.03;
            idleHeadTarget.z = 0;
            idleHeadTimer = 2 + Math.random() * 2;
        } else {
            idleHeadTarget.y = (Math.random() - 0.5) * 0.1;
            idleHeadTarget.x = -(0.03 + Math.random() * 0.03);
            idleHeadTarget.z = 0;
            idleHeadTimer = 1.5 + Math.random() * 2;
        }
    }

    const lerpSpeed = Math.min(2.5 * delta, 1.0);
    idleHead.x += (idleHeadTarget.x - idleHead.x) * lerpSpeed;
    idleHead.y += (idleHeadTarget.y - idleHead.y) * lerpSpeed;
    idleHead.z += (idleHeadTarget.z - idleHead.z) * lerpSpeed;

    cachedBones.head.rotation.x = idleHead.x;
    cachedBones.head.rotation.y = idleHead.y;
    cachedBones.head.rotation.z = idleHead.z;
}

// ============================================================
// SES ve LIP-SYNC
// ============================================================
let audioCtx, analyser, dataArray;
let isAudioMuted = false, activeSource = null, isSpeaking = false;

const cachedBones = { head: null, neck: null, spine: null, chest: null, upperChest: null };

async function initWebAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.85;
        dataArray = new Uint8Array(analyser.frequencyBinCount);
    }
    if (audioCtx.state === 'suspended') await audioCtx.resume();
}

function updateLipSync() {
    if (!analyser || !currentVrm?.expressionManager || !dataArray) return;

    if (!activeSource) {
        ['aa', 'ih', 'ee', 'oh', 'ou'].forEach(key => {
            const cur = currentVrm.expressionManager.getValue(key) || 0;
            currentVrm.expressionManager.setValue(key, cur > 0.01 ? cur * 0.85 : 0);
        });
        return;
    }

    analyser.getByteFrequencyData(dataArray);

    let low = 0, mid = 0, high = 0, vhigh = 0;
    for (let i = 1; i < 4; i++) low += dataArray[i];
    for (let i = 4; i < 10; i++) mid += dataArray[i];
    for (let i = 10; i < 20; i++) high += dataArray[i];
    for (let i = 20; i < 35; i++) vhigh += dataArray[i];

    const t = 0.04;
    const cl = (v, m) => v < t ? 0 : Math.min(v, m);
    const lm = (key, target) => {
        const cur = currentVrm.expressionManager.getValue(key) || 0;
        currentVrm.expressionManager.setValue(key, cur + (target - cur) * 0.35);
    };

    lm('aa', cl(mid / (6 * 255) * 0.6, 0.45));
    lm('ih', cl(high / (10 * 255) * 0.35, 0.3));
    lm('ee', cl(vhigh / (15 * 255) * 0.3, 0.25));
    lm('oh', cl(low / (3 * 255) * 0.4, 0.35));
    lm('ou', cl(low / (3 * 255) * 0.2, 0.22));
}

// ============================================================
// KONUŞMA VE DİNLEME KAFA HAREKETİ
// ============================================================
const headActiveOffset = { x: 0, y: 0, z: 0 };

function updateActiveHeadMovement(elapsed, delta) {
    if (!currentVrm || !cachedBones.head) return;

    const speakX = isSpeaking ? Math.sin(elapsed * 2.2) * 0.012 : 0;
    const speakZ = isSpeaking ? Math.cos(elapsed * 1.8) * 0.006 : 0;
    const listenX = isListening ? Math.sin(elapsed * 1.5) * 0.012 : 0;
    const listenZ = isListening ? Math.cos(elapsed * 1.1) * 0.008 : 0;

    const hs = Math.min(3.0 * delta, 1.0);
    headActiveOffset.x += (speakX + listenX - headActiveOffset.x) * hs;
    headActiveOffset.y += (0 - headActiveOffset.y) * hs;
    headActiveOffset.z += (speakZ + listenZ - headActiveOffset.z) * hs;

    cachedBones.head.rotation.x = idleHead.x + headActiveOffset.x;
    cachedBones.head.rotation.y = idleHead.y + headActiveOffset.y;
    cachedBones.head.rotation.z = idleHead.z + headActiveOffset.z;
}

// ============================================================
// GÖZ HAREKETİ
// ============================================================
const eyeTarget = { yaw: 0, pitch: 0 };
const eyeCurrent = { yaw: 0, pitch: 0 };

function updateEyeMovement(elapsed, delta) {
    if (!currentVrm?.lookAt) return;

    if (isSpeaking) {
        eyeTarget.yaw = Math.sin(elapsed * 0.5) * 0.008;
        eyeTarget.pitch = Math.cos(elapsed * 0.4) * 0.005;
    } else {
        eyeTarget.yaw = Math.sin(elapsed * 0.18) * 0.03;
        eyeTarget.pitch = Math.cos(elapsed * 0.13) * 0.02;
    }

    const es = Math.min(1.5 * delta, 1.0);
    eyeCurrent.yaw += (eyeTarget.yaw - eyeCurrent.yaw) * es;
    eyeCurrent.pitch += (eyeTarget.pitch - eyeCurrent.pitch) * es;

    try {
        if (typeof currentVrm.lookAt.yaw !== 'undefined') {
            currentVrm.lookAt.yaw = eyeCurrent.yaw;
            currentVrm.lookAt.pitch = eyeCurrent.pitch;
        } else if (currentVrm.lookAt.applier) {
            currentVrm.lookAt.applier.applyYawPitch(eyeCurrent.yaw, eyeCurrent.pitch);
        }
    } catch (e) { /* VRM versiyonu uyumsuzsa sessizce geç */ }
}

// ============================================================
// METİN TEMİZLEYİCİ
// ============================================================
function processActTokens(text) {
    if (!text) return "";
    return text.trim();
}

// ============================================================
// SES DURDURMA
// ============================================================
function stopAudio() {
    if (activeSource) { try { activeSource.stop(); } catch (e) { } activeSource = null; }
    isSpeaking = false;
    if (currentVrm?.expressionManager) {
        ['aa', 'ih', 'ee', 'oh', 'ou'].forEach(key => currentVrm.expressionManager.setValue(key, 0));
    }
}

let isListening = false;

// ============================================================
// UI ELEMENTLERİ
// ============================================================
const subtitle = document.getElementById('subtitle');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const micBtn = document.getElementById('mic-btn');
const audioBtn = document.getElementById('audio-btn');
const langTrBtn = document.getElementById('lang-tr');
const langEnBtn = document.getElementById('lang-en');
const historySidebar = document.getElementById('history-sidebar');
const historyList = document.getElementById('history-list');
const toggleSidebarBtn = document.getElementById('toggle-sidebar');
const closeSidebarBtn = document.getElementById('close-sidebar');


// ============================================================
// BACKEND URL KONFİGÜRASYONU
//
// Üretim URL'ini kaynak koduna gömmemek için önce window.__APP_CONFIG__
// nesnesine bakılır. Bu nesne index.html içinde deploy sırasında enjekte
// edilebilir:
//
//   <script>
//     window.__APP_CONFIG__ = {
//       apiBase: "https://your-backend.up.railway.app",
//       wsBase:  "wss://your-backend.up.railway.app"
//     };
//   </script>
//
// Yapılandırma yoksa localhost'a fallback (geliştirme modu).
// ============================================================
const _cfg = window.__APP_CONFIG__ || {};
const IS_LOCAL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE = _cfg.apiBase || (IS_LOCAL ? 'http://localhost:8001' : '');
const WS_BASE  = _cfg.wsBase  || (IS_LOCAL ? 'ws://localhost:8001'  : '');
if (!API_BASE) {
    console.warn('[CONFIG] API_BASE tanımlı değil. window.__APP_CONFIG__.apiBase ayarlayın.');
}
console.log(`[CONFIG] API: ${API_BASE} | WS: ${WS_BASE}`);

// ============================================================
// WEBSOCKET BAĞLANTISI
// ============================================================
let chatSocket = null;
let currentFullResponse = "";
let wsReconnectTimer = null;
let isReconnecting = false;

function initWebSocket() {
    if (chatSocket && (chatSocket.readyState === WebSocket.OPEN || chatSocket.readyState === WebSocket.CONNECTING)) return;

    isReconnecting = false;
    chatSocket = new WebSocket(`${WS_BASE}/ws/chat`);

    chatSocket.onopen = () => {
        console.log("WebSocket bağlantısı başarılı.");
        if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
    };

    let currentAiBubble = null;

    chatSocket.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'text') {
            currentFullResponse += data.content;
            const clean = currentFullResponse.trim();
            if (clean) {
                if (subtitle) subtitle.textContent = "";
                if (!currentAiBubble) {
                    currentAiBubble = document.createElement('div');
                    currentAiBubble.className = 'history-item ai';
                    currentAiBubble.innerHTML = `
                        <div class="bubble">
                            <img src="./ela_avatar.png" alt="bot" class="avatar-icon">
                            <div class="content"></div>
                        </div>
                    `;
                    historyList.appendChild(currentAiBubble);
                }
                currentAiBubble.querySelector('.content').textContent = clean;
                historyList.scrollTop = historyList.scrollHeight;
            }
        }
        else if (data.type === 'audio') {
            await playBase64Audio(data.content);
        }
        else if (data.type === 'emotion') {
            // Emotion logic removed
        }
        else if (data.type === 'done') {
            isSending = false;
            chatHistory.push({ role: 'assistant', content: currentFullResponse });
            if (!currentAiBubble && currentFullResponse.trim() !== '') {
                addToHistoryPanel('ai', currentFullResponse);
            }
            currentAiBubble = null;
            currentFullResponse = "";
        }
        else if (data.type === 'error') {
            isSending = false;
            if (subtitle) subtitle.textContent = "Hata: " + data.content;
            addToHistoryPanel('ai', "Hata: " + data.content);
        }
    };

    chatSocket.onclose = (event) => {
        if (event.code === 1000) return;
        if (isReconnecting) return;
        isReconnecting = true;
        console.warn(`WebSocket kapandı (code: ${event.code}). 3sn sonra yeniden bağlanılıyor...`);
        wsReconnectTimer = setTimeout(initWebSocket, 3000);
    };

    chatSocket.onerror = (err) => {
        console.error("WebSocket hatası:", err);
    };
}

initWebSocket();

// Sidebar Toggle (Sol)
toggleSidebarBtn.onclick = () => { historySidebar.classList.add('open'); };
closeSidebarBtn.onclick = () => { historySidebar.classList.remove('open'); };




// ============================================================
// GEÇMİŞE MESAJ EKLE
// ============================================================
function addToHistoryPanel(role, text) {
    const item = document.createElement('div');
    item.className = `history-item ${role === 'user' ? 'user' : 'ai'}`;
    const displayRes = processActTokens(text);

    if (role === 'user') {
        item.innerHTML = `<div class="content">${displayRes}</div>`;
    } else {
        item.innerHTML = `
            <div class="bubble">
                <img src="./ela_avatar.png" alt="bot" class="avatar-icon">
                <div class="content">${displayRes}</div>
            </div>
        `;
    }

    historyList.appendChild(item);
    historyList.scrollTop = historyList.scrollHeight;
}

// ============================================================
// DİL DESTEĞİ
// ============================================================
let currentLang = 'tr';
const translations = {
    tr: { subtitle: "Otobüs bileti Randevu AI Asistanı", placeholder: "Bir mesaj yazın...", welcome: "Merhaba, ben Ela. Size en uygun otobüs biletini bulmam için nereden nereye ve hangi tarihte seyahat edeceğinizi söyler misiniz?", thinking: "Düşünüyor..." },
    en: { subtitle: "Bus Ticket Booking AI Assistant", placeholder: "Type a message...", welcome: "Hello, I'm Ela. Could you tell me where you are traveling from, your destination, and your travel dates so I can find the best bus ticket for you?", thinking: "Thinking..." }
};

function setLanguage(lang) {
    currentLang = lang;
    chatInput.placeholder = translations[lang].placeholder;

    const aiSubtitle = document.getElementById('ai-subtitle');
    if (aiSubtitle) aiSubtitle.textContent = translations[lang].subtitle;

    const welcomeMsg = document.getElementById('welcome-msg');
    if (welcomeMsg && (welcomeMsg.textContent === translations.tr.welcome || welcomeMsg.textContent === translations.en.welcome)) {
        welcomeMsg.textContent = translations[lang].welcome;
    }
    langTrBtn.classList.toggle('active', lang === 'tr');
    langEnBtn.classList.toggle('active', lang === 'en');
}

langTrBtn.addEventListener('click', () => setLanguage('tr'));
langEnBtn.addEventListener('click', () => setLanguage('en'));

// ============================================================
// SES AÇ/KAPAT
// ============================================================
audioBtn.addEventListener('click', async () => {
    await initWebAudio();
    isAudioMuted = !isAudioMuted;
    audioBtn.innerHTML = isAudioMuted ? '<i class="fa-solid fa-volume-xmark"></i>' : '<i class="fa-solid fa-volume-high"></i>';
    if (analyser && audioCtx) {
        if (isAudioMuted) { try { analyser.disconnect(audioCtx.destination); } catch (e) { } }
        else { try { analyser.connect(audioCtx.destination); } catch (e) { } }
    }
});

// ============================================================
// MİKROFON (BASILI TUT - KONUŞ)
// ============================================================
let mediaRecorder, audioChunks = [];

micBtn.addEventListener('mousedown', async () => {
    stopAudio();
    await initWebAudio();
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        audioChunks = [];
        mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };

        mediaRecorder.onstop = async () => {
            subtitle.textContent = "Ses işleniyor...";
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            if (audioBlob.size === 0) { subtitle.textContent = "Ses kaydedilemedi."; return; }

            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.webm');
            formData.append('lang', currentLang);

            try {
                const res = await fetch(`${API_BASE}/api/stt`, { method: 'POST', body: formData });
                if (res.ok) {
                    const data = await res.json();
                    if (data.text && data.text.trim().length > 0) {
                        chatInput.value = data.text;
                        sendMessage();
                    } else {
                        subtitle.textContent = "Sesi anlayamadım.";
                    }
                } else if (res.status === 429) {
                    subtitle.textContent = "Ses servisi yoğun, 2 saniye bekleyip tekrar dene.";
                } else {
                    subtitle.textContent = "Ses anlaşılamadı, tekrar deneyin.";
                }
            } catch (err) {
                subtitle.textContent = err.message?.includes("Failed to fetch") ? "Backend bağlantısı yok." : "Ses işlenemedi.";
            }
            stream.getTracks().forEach(t => t.stop());
        };

        mediaRecorder.start();
        micBtn.classList.add('recording');
        subtitle.textContent = "Dinliyorum...";
        isListening = true;
    } catch (err) {
        subtitle.textContent = "Lütfen mikrofon izni verin.";
    }
});

micBtn.addEventListener('mouseup', () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    micBtn.classList.remove('recording');
    isListening = false;
});

// ============================================================
// MESAJ GÖNDERME
// ============================================================
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', e => {
    if (e.key === 'Enter') { e.preventDefault(); sendMessage(); }
});
chatInput.addEventListener('input', () => { if (chatInput.value.trim().length > 0) stopAudio(); });

const chatHistory = [];
let isSending = false;

async function sendMessage() {
    if (isSending) return;
    const text = chatInput.value.trim();
    if (!text) return;

    isSending = true;
    stopAudio();
    await initWebAudio();
    chatHistory.push({ role: 'user', content: text });
    addToHistoryPanel('user', text);
    chatInput.value = '';

    subtitle.textContent = translations[currentLang].thinking;
    currentFullResponse = "";

    const payload = JSON.stringify({
        text: text,
        lang: currentLang,
        history: chatHistory.slice(0, -1).slice(-10)
    });

    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(payload);
    } else {
        subtitle.textContent = "Bağlanıyor...";
        initWebSocket();
        const waitAndSend = setInterval(() => {
            if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                clearInterval(waitAndSend);
                chatSocket.send(payload);
            }
        }, 200);
        setTimeout(() => {
            clearInterval(waitAndSend);
            if (subtitle.textContent === "Bağlanıyor...") subtitle.textContent = "Bağlantı sağlanamadı.";
        }, 5000);
    }
}

// ============================================================
// SES ÇALMA (BASE64 MP3)
// ============================================================
async function playBase64Audio(base64Str) {
    if (!audioCtx) await initWebAudio();
    if (isListening || chatInput.value.trim().length > 0) return;

    try {
        const res = await fetch(`data:audio/mpeg;base64,${base64Str}`);
        const arrayBuffer = await res.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

        stopAudio();

        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        activeSource = source;
        isSpeaking = true;

        source.onended = () => {
            if (activeSource === source) { activeSource = null; isSpeaking = false; }
        };

        source.connect(analyser);
        if (!isAudioMuted) analyser.connect(audioCtx.destination);
        source.start(0);
    } catch (e) {
        isSpeaking = false;
        subtitle.textContent = "Ses çalınamadı.";
    }
}
