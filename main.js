import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// ============================================================
// SAHNE KURULUMU
// Canvas, renderer, kamera ve ışıklar burada ayarlanır
// ============================================================
const canvas = document.getElementById('canvas');
const canvasContainer = document.getElementById('canvas-container');

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);

const scene = new THREE.Scene();

// Kamera ayarları
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

// Yönlü ışık (güneş gibi tek yönden gelen ışık)
const directionalLight = new THREE.DirectionalLight(0xffffff, 2.0);
directionalLight.position.set(1, 1, 1).normalize();
scene.add(directionalLight);

// Ortam ışığı (her taraftan eşit dağılan yumuşak ışık)
const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
scene.add(ambientLight);

// ============================================================
// VRM MODEL YÜKLEME
// ./models/character.vrm dosyasını yükler
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
            // Kolları aşağı indir (T-Pose engellemek için)
            // rotation.z değerini artırırsan kollar daha fazla aşağı iner
            const leftUpperArm = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
            const rightUpperArm = vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
            if (leftUpperArm) leftUpperArm.rotation.z = -1.2;
            if (rightUpperArm) rightUpperArm.rotation.z = 1.2;

            // Omuzları hafif içe al
            const leftShoulder = vrm.humanoid.getNormalizedBoneNode('leftShoulder');
            const rightShoulder = vrm.humanoid.getNormalizedBoneNode('rightShoulder');
            if (leftShoulder) leftShoulder.rotation.z = -0.1;
            if (rightShoulder) rightShoulder.rotation.z = 0.1;

            // Kemikleri önbelleğe al — her karede tekrar aramak yerine direkt kullanmak için
            cachedBones.head = vrm.humanoid.getNormalizedBoneNode('head');
            cachedBones.neck = vrm.humanoid.getNormalizedBoneNode('neck');
            cachedBones.spine = vrm.humanoid.getNormalizedBoneNode('spine');
            cachedBones.chest = vrm.humanoid.getNormalizedBoneNode('chest');
            cachedBones.upperChest = vrm.humanoid.getNormalizedBoneNode('upperChest');
        }

        // lookAt otomatik güncellemesini kapat
        // Biz göz hareketini manuel kontrol edeceğiz (updateEyeMovement fonksiyonu)
        if (vrm.lookAt) vrm.lookAt.autoUpdate = false;

        console.log('VRM başarıyla yüklendi!');
        startBlinking(); // Göz kırpmayı başlat
    },
    (progress) => console.log('Yükleniyor...', (100.0 * (progress.loaded / progress.total)).toFixed(2), '%'),
    (error) => {
        console.error('VRM yükleme hatası:', error);
        document.getElementById('subtitle').textContent = "Model yüklenemedi. 'models/character.vrm' dosyasını koyun.";
    }
);

// ============================================================
// ANA ANİMASYON DÖNGÜSÜ
// Her kare (frame) burada çizilir — saniyede ~60 kez çalışır
// ============================================================
const clock = new THREE.Clock();
const fpsCounter = document.getElementById('fps-counter');
let frames = 0, lastTime = performance.now();

function animate() {
    requestAnimationFrame(animate);
    const deltaTime = clock.getDelta();     // Son kareden bu yana geçen süre (saniye)
    const elapsed = clock.getElapsedTime(); // Uygulama başladığından beri toplam süre (saniye)

    if (currentVrm) {
        currentVrm.update(deltaTime);                   // VRM fizik güncellemesi (saç, kıyafet sallanması vb.)
        updateBreathing(elapsed);                        // Nefes alma hareketi
        updateIdleHeadMovement(elapsed, deltaTime);      // Boşta kafa hareketi
        updateLipSync();                                 // Konuşurken ağız hareketi
        updateExpressions(deltaTime);                    // Yüz ifadesi geçişleri
        updateHeadBehavior(elapsed, deltaTime);          // Duyguya göre kafa açısı
        updateEyeMovement(elapsed, deltaTime);           // Göz hareketi
    }

    renderer.render(scene, camera);

    // FPS sayacı
    frames++;
    const time = performance.now();
    if (time >= lastTime + 1000) {
        fpsCounter.innerHTML = `<i class="fa-solid fa-gauge"></i> FPS: ${Math.round((frames * 1000) / (time - lastTime))}`;
        frames = 0;
        lastTime = time;
    }
}
animate();

// window.addEventListener('resize', handleCanvasResize); // ResizeObserver handles this now

// ============================================================
// GÖZ KIRPMA
// Rastgele aralıklarla göz kırpar, %30 ihtimalle çift kırpar
// ============================================================
function startBlinking() {
    const blink = () => {
        if (currentVrm?.expressionManager) {
            currentVrm.expressionManager.setValue('blink', 1.0); // Gözleri kapat
            setTimeout(() => {
                if (currentVrm) currentVrm.expressionManager.setValue('blink', 0.0); // Gözleri aç

                // %30 ihtimalle çift göz kırpma
                if (Math.random() > 0.7) {
                    setTimeout(() => {
                        if (!currentVrm) return;
                        currentVrm.expressionManager.setValue('blink', 1.0);
                        setTimeout(() => { if (currentVrm) currentVrm.expressionManager.setValue('blink', 0.0); }, 80);
                    }, 120);
                }
            }, 100); // Gözler 100ms kapalı kalır — artırırsan daha yavaş kırpar
        }
        // Bir sonraki kırpma: 2-6 saniye arası rastgele
        // İlk sayıyı artırırsan daha seyrek kırpar
        setTimeout(blink, 2000 + Math.random() * 4000);
    };
    blink();
}

// ============================================================
// NEFES ALMA HAREKETİ
// Göğüs ve omurga hafifçe yukarı-aşağı hareket eder
// ============================================================

function updateBreathing(elapsed) {
    if (!currentVrm?.humanoid) return;

    // Nefes dalgası: 0.0 (nefes verme) → 1.0 (nefes alma) arası
    // 0.35 = nefes hızı — azaltırsan daha yavaş nefes alır (örn. 0.25 = çok yavaş)
    const breathNorm = (Math.sin(elapsed * 0.35) + 1) / 2;

    // --- Omuzları yukarı kaldır ---
    // rotation.x = omuzun öne/arkaya hareketi — NEGATİF değer omuzları YUKARI kaldırır
    // -0.12 = omuz kalkma miktarı — artırırsan (örn. -0.20) daha belirgin olur
    const leftShoulder = currentVrm.humanoid.getNormalizedBoneNode('leftShoulder');
    const rightShoulder = currentVrm.humanoid.getNormalizedBoneNode('rightShoulder');
    if (leftShoulder) leftShoulder.rotation.x = -breathNorm * 0.12;
    if (rightShoulder) rightShoulder.rotation.x = -breathNorm * 0.12;

    // --- Üst kollar nefesle hafifçe dışa açılır ---
    // Temel değer -1.2 / 1.2 (kolların aşağı duruşu), nefeste 0.06 ekstra açılır
    // 0.06 = kol açılma miktarı
    const leftUpperArm = currentVrm.humanoid.getNormalizedBoneNode('leftUpperArm');
    const rightUpperArm = currentVrm.humanoid.getNormalizedBoneNode('rightUpperArm');
    if (leftUpperArm) leftUpperArm.rotation.z = -1.2 - breathNorm * 0.06;
    if (rightUpperArm) rightUpperArm.rotation.z = 1.2 + breathNorm * 0.06;

    // --- Boyun hafifçe geriye gider (baş hafif kalkar) ---
    // Nefes alınca baş hafif yukarı kalkar — doğal nefes hareketi
    // 0.03 = boyun hareket miktarı — çok artırma, baş çok geriye gider
    const neck = cachedBones.neck;
    if (neck) neck.rotation.x = -breathNorm * 0.03;
}

// ============================================================
// BOŞ BEKLEME KAFA HAREKETİ (IDLE)
// Karakter beklerken başı hafifçe hareket eder — cansız durmaz
// ============================================================

// Mevcut kafa açıları (yumuşak geçiş için)
const idleHead = { x: 0, y: 0, z: 0 };

// Bir sonraki hareket için hedef açılar
let idleHeadTarget = { x: 0, y: 0, z: 0 };

// Hedef değişim zamanlayıcısı
let idleHeadTimer = 0;

function updateIdleHeadMovement(elapsed, delta) {
    if (!currentVrm || !cachedBones.head) return;

    // Konuşurken veya dinlerken idle hareketi durdur — kafa düz öne bakar
    if (isSpeaking || isListening) {
        // Mevcut pozisyonu sıfıra doğru yumuşakça çek (ani sıfırlama olmasın)
        const rs = Math.min(2.0 * delta, 1.0);
        idleHead.x += (0 - idleHead.x) * rs;
        idleHead.y += (0 - idleHead.y) * rs;
        idleHead.z += (0 - idleHead.z) * rs;
        cachedBones.head.rotation.x = idleHead.x;
        cachedBones.head.rotation.y = idleHead.y;
        cachedBones.head.rotation.z = idleHead.z;
        idleHeadTimer = 1.0; // Konuşma bitince hemen yeni harekete geçmesin, 1sn beklesin
        return;
    }

    idleHeadTimer -= delta;
    if (idleHeadTimer <= 0) {
        const r = Math.random();

        if (r < 0.30) {
            // %30 — Düz öne bak, hafif mikro titreme yok
            idleHeadTarget.y = 0;
            idleHeadTarget.x = 0;
            idleHeadTarget.z = 0;
            idleHeadTimer = 1.5 + Math.random() * 2; // Kısa bekle, sıkıcı olmaz

        } else if (r < 0.48) {
            // %18 — Sağa bak (hafif)
            idleHeadTarget.y = 0.07 + Math.random() * 0.06;   // Max ~7.5 derece (eskiden ~17)
            idleHeadTarget.x = 0;
            idleHeadTarget.z = idleHeadTarget.y * 0.10;
            idleHeadTimer = 3 + Math.random() * 4;             // Daha uzun bekle

        } else if (r < 0.66) {
            // %18 — Sola bak (hafif)
            idleHeadTarget.y = -(0.07 + Math.random() * 0.06);
            idleHeadTarget.x = 0;
            idleHeadTarget.z = idleHeadTarget.y * 0.10;
            idleHeadTimer = 3 + Math.random() * 4;

        } else if (r < 0.92) {
            // %12 — Hafif aşağı bak (dingin/düşünceli)
            idleHeadTarget.y = (Math.random() - 0.5) * 0.1;
            idleHeadTarget.x = 0.05 + Math.random() * 0.03; // x pozitif = aşağı bakar
            idleHeadTarget.z = 0;
            idleHeadTimer = 2 + Math.random() * 2;

        } else {
            // %8 — Hafif yukarı bak (meraklı/uyanık)
            idleHeadTarget.y = (Math.random() - 0.5) * 0.1;
            idleHeadTarget.x = -(0.03 + Math.random() * 0.03); // x negatif = yukarı bakar
            idleHeadTarget.z = 0;
            idleHeadTimer = 1.5 + Math.random() * 2;
        }
    }

    // Geçiş hızı: 2.5 — yeterince hızlı ki hareket görünsün, yeterince yavaş ki doğal olsun
    // Azaltırsan (1.0) çok yavaş kayar — hareket bitmeden yeni hareket başlar
    // Artırırsan (5.0) robot gibi ani döner
    const lerpSpeed = Math.min(2.5 * delta, 1.0);
    idleHead.x += (idleHeadTarget.x - idleHead.x) * lerpSpeed;
    idleHead.y += (idleHeadTarget.y - idleHead.y) * lerpSpeed;
    idleHead.z += (idleHeadTarget.z - idleHead.z) * lerpSpeed;

    // NOT: updateHeadBehavior fonksiyonu bu değerlerin üstüne duygu bazlı offset ekler
    cachedBones.head.rotation.x = idleHead.x;
    cachedBones.head.rotation.y = idleHead.y;
    cachedBones.head.rotation.z = idleHead.z;
}

// ============================================================
// SES ve LIP-SYNC
// Web Audio API ile ses frekansını analiz ederek ağız morph'larını kontrol eder
// ============================================================
let audioCtx, analyser, dataArray;
let isAudioMuted = false, activeSource = null, isSpeaking = false;

// Kemik referansları — her karede aramak yerine bir kez al
const cachedBones = { head: null, neck: null, spine: null, chest: null, upperChest: null };

async function initWebAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 512;                 // Frekans çözünürlüğü — 2'nin katı olmalı
        analyser.smoothingTimeConstant = 0.85;  // Yumuşatma: 0=ham, 1=çok yumuşak
        dataArray = new Uint8Array(analyser.frequencyBinCount);
    }
    if (audioCtx.state === 'suspended') await audioCtx.resume();
}

function updateLipSync() {
    if (!analyser || !currentVrm?.expressionManager || !dataArray) return;

    // Ses çalmıyorsa ağzı yumuşakça kapat
    if (!activeSource) {
        ['aa', 'ih', 'ee', 'oh', 'ou'].forEach(key => {
            const cur = currentVrm.expressionManager.getValue(key) || 0;
            // 0.85 = kapanma hızı — küçültürsen daha hızlı kapanır
            currentVrm.expressionManager.setValue(key, cur > 0.01 ? cur * 0.85 : 0);
        });
        return;
    }

    analyser.getByteFrequencyData(dataArray);

    // Frekans bantlarını topla
    // Düşük frekans (ou, oh) = yuvarlak ünlüler
    // Orta frekans (aa) = açık ünlüler
    // Yüksek frekans (ee, ih) = tiz ünlüler
    let low = 0, mid = 0, high = 0, vhigh = 0;
    for (let i = 1; i < 4; i++) low += dataArray[i];
    for (let i = 4; i < 10; i++) mid += dataArray[i];
    for (let i = 10; i < 20; i++) high += dataArray[i];
    for (let i = 20; i < 35; i++) vhigh += dataArray[i];

    // 0.04 = gürültü eşiği — altındaki değerleri sıfırla (dudak titremesini engeller)
    const t = 0.04;
    const cl = (v, m) => v < t ? 0 : Math.min(v, m);

    // Yumuşak geçiş (lerp): 0.35 = ağız açılma hızı — artırırsan daha hızlı tepki verir
    const lm = (key, target) => {
        const cur = currentVrm.expressionManager.getValue(key) || 0;
        currentVrm.expressionManager.setValue(key, cur + (target - cur) * 0.35);
    };

    // Son sayı = maksimum açılma miktarı — artırırsan ağız daha fazla açılır
    lm('aa', cl(mid / (6 * 255) * 0.6, 0.45));   // Geniş açık ağız
    lm('ih', cl(high / (10 * 255) * 0.35, 0.3));  // Küçük açık, dişler görünür
    lm('ee', cl(vhigh / (15 * 255) * 0.3, 0.25)); // Gülümseme şekli
    lm('oh', cl(low / (3 * 255) * 0.4, 0.35));    // Yuvarlak orta açıklık
    lm('ou', cl(low / (3 * 255) * 0.2, 0.22));    // Küçük yuvarlak
}

// ============================================================
// DUYGU SİSTEMİ
// Her duygunun hedef değeri 0-1 arasında, yumuşak geçişle uygulanır
// ============================================================
const expressionTargets = {
    happy: 0,       // Mutlu
    angry: 0,       // Kızgın
    sad: 0,         // Üzgün
    relaxed: 0,     // Sakin/Rahat
    surprised: 0,   // Şaşkın
    neutral: 1,     // Nötr (başlangıçta aktif)
    think: 0,       // Düşünüyor
    awkward: 0,     // Mahcup/Utangaç
    curious: 0,     // Meraklı
    question: 0     // Soru soruyor
};
const currentExpressions = { ...expressionTargets }; // Mevcut yumuşatılmış değerler

function updateExpressions(delta) {
    if (!currentVrm?.expressionManager) return;

    // 2.0 = duygu geçiş hızı — artırırsan ifade değişimi daha hızlı olur
    const lerpSpeed = 2.0;

    for (const key in expressionTargets) {
        // Hedef değere doğru yumuşak geçiş
        currentExpressions[key] += (expressionTargets[key] - currentExpressions[key]) * Math.min(lerpSpeed * delta, 1.0);
        const val = currentExpressions[key];

        // Son sayı = maksimum ifade yoğunluğu — 1.0 = tam yoğunluk, 0.5 = yarı yoğunluk
        if (key === 'happy') {
            currentVrm.expressionManager.setValue('happy', val * 0.5);
            currentVrm.expressionManager.setValue('joy', val * 0.5);        // VRM 0.x uyumluluğu
        } else if (key === 'angry') {
            currentVrm.expressionManager.setValue('angry', val * 0.4);
        } else if (key === 'sad') {
            currentVrm.expressionManager.setValue('sad', val * 0.45);
            currentVrm.expressionManager.setValue('sorrow', val * 0.45);    // VRM 0.x uyumluluğu
        } else if (key === 'surprised') {
            currentVrm.expressionManager.setValue('surprised', val * 0.45);
        } else if (key === 'relaxed') {
            currentVrm.expressionManager.setValue('relaxed', val * 0.4);
        } else if (key === 'think') {
            currentVrm.expressionManager.setValue('relaxed', val * 0.3);    // Düşünürken hafif sakin bakış
        } else if (key === 'awkward') {
            currentVrm.expressionManager.setValue('sad', val * 0.2);        // Mahcupken hafif üzgün
        } else if (key === 'curious' || key === 'question') {
            currentVrm.expressionManager.setValue('surprised', val * 0.2);  // Meraklıyken hafif şaşkın
        }
    }
}

// ============================================================
// DUYGUYA GÖRE KAFA HAREKETİ
// Idle hareketi üzerine duygu bazlı ekstra kafa açısı eklenir
// ============================================================
const headEmotionOffset = { x: 0, y: 0, z: 0 }; // Duygu bazlı ek açılar

function updateHeadBehavior(elapsed, delta) {
    if (!currentVrm || !cachedBones.head) return;

    const hv = currentExpressions.happy;
    const sv = currentExpressions.sad;
    const av = currentExpressions.angry;
    const srv = currentExpressions.surprised;
    const tv = currentExpressions.think;
    const cv = currentExpressions.curious || currentExpressions.question;

    // Duyguya göre kafa açısı hedefleri
    // Sayıları artırırsan daha belirgin hareket olur
    const targetZ = hv * 0.06 - sv * 0.05 + tv * 0.08;    // Mutlu: sağa eğil | Üzgün: sola | Düşünür: sağa
    const targetX = av * 0.08 - srv * 0.05 - cv * 0.04;    // Kızgın: öne | Şaşkın: geri | Meraklı: öne
    const targetY = tv * 0.15;                              // Düşünürken yana bak

    // Konuşurken küçük ritimli kafa sallama
    // İlk sayı = hız, ikinci sayı = genlik (amplitüd)
    const speakX = isSpeaking ? Math.sin(elapsed * 2.2) * 0.012 : 0;
    const speakZ = isSpeaking ? Math.cos(elapsed * 1.8) * 0.006 : 0;

    // Dinlerken onaylama benzeri hafif baş sallama
    const listenX = isListening ? Math.sin(elapsed * 1.5) * 0.012 : 0;
    const listenZ = isListening ? Math.cos(elapsed * 1.1) * 0.008 : 0;

    // Duygu offsetlerini yumuşak geçişle güncelle
    const hs = Math.min(3.0 * delta, 1.0);
    headEmotionOffset.x += (targetX + speakX + listenX - headEmotionOffset.x) * hs;
    headEmotionOffset.y += (targetY - headEmotionOffset.y) * hs;
    headEmotionOffset.z += (targetZ + speakZ + listenZ - headEmotionOffset.z) * hs;

    // Idle hareketi + duygu offsetini birleştirerek kafa kemiğine uygula
    cachedBones.head.rotation.x = idleHead.x + headEmotionOffset.x;
    cachedBones.head.rotation.y = idleHead.y + headEmotionOffset.y;
    cachedBones.head.rotation.z = idleHead.z + headEmotionOffset.z;
}

// ============================================================
// GÖZ HAREKETİ
// lookAt.lookAt() metodu yerine yaw/pitch ile kontrol
// lookAt.lookAt() bazı modellerde gözleri abartılı büyütüyordu
// ============================================================
const eyeTarget = { yaw: 0, pitch: 0 };    // Hedef göz açısı
const eyeCurrent = { yaw: 0, pitch: 0 };   // Mevcut göz açısı (yumuşatılmış)

function updateEyeMovement(elapsed, delta) {
    if (!currentVrm?.lookAt) return;

    if (isSpeaking) {
        // Konuşurken kameraya bak — çok küçük mikro titreme
        // Sayıları artırırsan gözler daha fazla hareket eder
        eyeTarget.yaw = Math.sin(elapsed * 0.5) * 0.008;
        eyeTarget.pitch = Math.cos(elapsed * 0.4) * 0.005;
    } else {
        // Boştayken yavaş ve doğal göz dolaşması
        // 0.18 ve 0.13 = göz hareket hızı — artırırsan daha hızlı dolaşır
        // 0.03 ve 0.02 = göz hareket genliği — artırırsan daha fazla yana kayar
        eyeTarget.yaw = Math.sin(elapsed * 0.18) * 0.03;
        eyeTarget.pitch = Math.cos(elapsed * 0.13) * 0.02;
    }

    // Göz geçiş hızı: 1.5 — artırırsan gözler daha hızlı hedefe gider
    const es = Math.min(1.5 * delta, 1.0);
    eyeCurrent.yaw += (eyeTarget.yaw - eyeCurrent.yaw) * es;
    eyeCurrent.pitch += (eyeTarget.pitch - eyeCurrent.pitch) * es;

    // VRM versiyonuna göre göz açısını uygula
    try {
        if (typeof currentVrm.lookAt.yaw !== 'undefined') {
            // VRM 1.0 — doğrudan yaw/pitch ata
            currentVrm.lookAt.yaw = eyeCurrent.yaw;
            currentVrm.lookAt.pitch = eyeCurrent.pitch;
        } else if (currentVrm.lookAt.applier) {
            // Bazı VRM versiyonları — applier üzerinden uygula
            currentVrm.lookAt.applier.applyYawPitch(eyeCurrent.yaw, eyeCurrent.pitch);
        }
    } catch (e) { /* VRM versiyonu uyumsuzsa sessizce geç */ }
}

// ============================================================
// DUYGU AYARLAMA
// Tüm duyguları sıfırlar ve belirtilen duyguyu 1.0 yapar
// ============================================================
function setEmotion(emotion) {
    for (const key in expressionTargets) expressionTargets[key] = 0;
    if (expressionTargets.hasOwnProperty(emotion)) expressionTargets[emotion] = 1.0;
    else expressionTargets.neutral = 1.0;

    console.log(`[EMOTION] setEmotion çağrıldı → ${emotion}`, JSON.stringify(expressionTargets));

    // UI Güncelle
    if (emotionBadge) emotionBadge.textContent = emotionNamesTr[emotion] || 'Nötr';
    updateEmotionChart();
}

// ============================================================
// ACT TOKEN İŞLEYİCİ
// LLM yanıtında <|ACT:...|> formatında gelen duygu tokenlarını işler
// ============================================================
function processActTokens(text) {
    if (!text) return "";
    const actRegex = /<\|ACT:(.*?)\|>/gs; // 's' flagı ile multiline match
    let match, lastEmotion = null;
    while ((match = actRegex.exec(text)) !== null) {
        try {
            const inner = match[1].trim();
            // JSON format: "emotion":{"name":"happy",...}
            const nameMatch = inner.match(/"name"\s*:\s*"(\w+)"/);
            if (nameMatch) {
                lastEmotion = nameMatch[1].toLowerCase();
            } else {
                // Basit format: happy
                const simple = inner.trim().toLowerCase();
                if (simple.match(/^\w+$/)) lastEmotion = simple;
            }
        } catch (e) { console.warn("ACT parse hatası:", e); }
    }
    if (lastEmotion) {
        console.log(`[EMOTION] Frontend ACT → ${lastEmotion}`);
        setEmotion(lastEmotion);
    }
    return text.replace(/<\|ACT:.*?\|>/gs, '').replace(/<\|DELAY:.*?\|>/g, '').trim();
}

// ============================================================
// YEREL DUYGU ANALİZİ (KEYWORD BAZLI)
// API yanıtı gelmeden önce metni hızlıca analiz eder
// ============================================================
let emotionTimeout;
function handleEmotionsLocal(text) {
    if (text.includes('<|ACT:')) return; // ACT tokenı varsa keyword analizini atla
    const lt = text.toLowerCase();
    if (emotionTimeout) clearTimeout(emotionTimeout);

    const happyW = ['😊', '😄', '🥰', 'mutlu', 'harika', 'sevindim', 'güzel', 'iyi', 'evet', 'teşekkür', 'memnun', 'sevdim', 'tatlı', 'komik', 'şaka', 'lol', 'hahaha', 'seviyorum', 'bravo', 'süper'];
    const sadW = ['😔', '😢', '😭', 'üzgün', 'malesef', 'kötü', 'hayır', 'üzüldüm', 'maalesef', 'sorun', 'yalnız', 'hüzün', 'kaybettim', 'özledim', 'ayrılık'];
    const angryW = ['😠', '😡', 'kızgın', 'sinir', 'dur', 'yeter', 'öfke', 'nefret', 'berbat', 'saçma', 'aptal', 'bıktım', 'olmaz'];
    const surprisedW = ['😲', '😮', 'inanılmaz', 'nasıl', 'gerçekten', 'wow', 'vaov', 'şaşırtıcı', 'bekle', 'hayret', 'beklemiyordum'];
    const relaxedW = ['😌', 'rahat', 'sakin', 'uyku', 'dinlen', 'huzur', 'tamam', 'peki', 'olur', 'anladım'];

    let detected = 'neutral';
    if (happyW.some(w => lt.includes(w))) detected = 'happy';
    else if (sadW.some(w => lt.includes(w))) detected = 'sad';
    else if (angryW.some(w => lt.includes(w))) detected = 'angry';
    else if (surprisedW.some(w => lt.includes(w))) detected = 'surprised';
    else if (relaxedW.some(w => lt.includes(w))) detected = 'relaxed';

    setEmotion(detected);
    // 9 saniye sonra nötre dön — artırırsan ifade daha uzun süre kalır
    emotionTimeout = setTimeout(() => setEmotion('neutral'), 9000);
}

// AI DUYGU ANALİZİ (ESKİ - KALDIRILDI)
// Artık duygu analizi ana chat response (ACT token) içinde yapılıyor.

// ============================================================
// SES DURDURMA
// Aktif sesi durdurur ve ağzı kapatır
// ============================================================
function stopAudio() {
    audioQueue = [];       // Kuyruğu temizle
    isPlayingQueue = false;
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

const emotionSidebar = document.getElementById('emotion-sidebar');
const toggleEmotionBtn = document.getElementById('toggle-emotion-sidebar');
const closeEmotionBtn = document.getElementById('close-emotion-sidebar');
const emotionBadge = document.getElementById('current-emotion-badge');

// ============================================================
// WEBSOCKET BAĞLANTISI (/ws/chat)
// ============================================================
let chatSocket = null;
let currentFullResponse = "";
let wsReconnectTimer = null;
let isReconnecting = false;

function initWebSocket() {
    // Zaten bağlı veya bağlanıyor ise tekrar açma
    if (chatSocket && (chatSocket.readyState === WebSocket.OPEN || chatSocket.readyState === WebSocket.CONNECTING)) return;

    isReconnecting = false;
    chatSocket = new WebSocket('ws://localhost:8001/ws/chat');

    chatSocket.onopen = () => {
        console.log("WebSocket bağlantısı başarılı.");
        if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
    };

    let currentAiBubble = null;

    chatSocket.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'text') {
            currentFullResponse += data.content;
            const clean = currentFullResponse
                .replace(/<\|ACT:.*?\|>/gs, '')
                .replace(/<\|ACT:.*$/gs, '')
                .trim();
            if (clean) {
                if (subtitle) subtitle.textContent = ""; // Clear loading status
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
            setEmotion(data.content);
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
            setEmotion('sad');
        }
    };

    chatSocket.onclose = (event) => {
        // Kasıtlı kapatma (code 1000) ise yeniden bağlanma
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

// Uygulama başladığında WebSocket'i başlat
initWebSocket();

// Sidebar Toggle (Sol)
toggleSidebarBtn.addEventListener('click', () => historySidebar.classList.add('open'));
closeSidebarBtn.addEventListener('click', () => historySidebar.classList.remove('remove', historySidebar.classList.contains('open') ? historySidebar.classList.remove('open') : null));
// Düzeltme: toggleSidebarBtn ve closeSidebarBtn basit click listener'ları
toggleSidebarBtn.onclick = () => { historySidebar.classList.add('open'); emotionSidebar.classList.remove('open'); };
closeSidebarBtn.onclick = () => { historySidebar.classList.remove('open'); };

// Sidebar Toggle (Sağ)
toggleEmotionBtn.onclick = () => { emotionSidebar.classList.add('open'); historySidebar.classList.remove('open'); initEmotionChart(); };
closeEmotionBtn.onclick = () => { emotionSidebar.classList.remove('open'); };

// DUYGU GRAFİĞİ (Chart.js)
let emotionChart = null;
function initEmotionChart() {
    if (emotionChart) return;
    const ctx = document.getElementById('emotionChart').getContext('2d');

    // Radar grafiği "AI Duygu Analizi" için daha estetik durur
    emotionChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Mutlu', 'Kızgın', 'Üzgün', 'Sakin', 'Şaşkın', 'Düşünceli', 'Meraklı'],
            datasets: [{
                label: 'Duygu Yoğunluğu',
                data: [0, 0, 0, 1, 0, 0, 0],
                backgroundColor: 'rgba(255, 192, 203, 0.2)',
                borderColor: 'rgba(255, 192, 203, 0.8)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(255, 192, 203, 1)',
                tension: 0.4
            }]
        },
        options: {
            scales: {
                r: {
                    min: 0, max: 1,
                    ticks: { display: false },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                    pointLabels: { color: 'rgba(255, 255, 255, 0.5)', font: { size: 10 } }
                }
            },
            plugins: { legend: { display: false } },
            responsive: true,
            maintainAspectRatio: true
        }
    });
}

function updateEmotionChart() {
    if (!emotionChart) return;

    // expressionTargets üzerindeki değerleri eşle
    const data = [
        expressionTargets.happy,
        expressionTargets.angry,
        expressionTargets.sad,
        expressionTargets.relaxed,
        expressionTargets.surprised,
        expressionTargets.think,
        expressionTargets.curious || expressionTargets.question
    ];

    emotionChart.data.datasets[0].data = data;
    emotionChart.update('none'); // Animasyonsuz anlık güncelleme
}

const emotionNamesTr = {
    happy: 'Mutlu', angry: 'Kızgın', sad: 'Üzgün', relaxed: 'Sakin',
    surprised: 'Şaşkın', neutral: 'Nötr', think: 'Düşünüyor',
    awkward: 'Mahcup', curious: 'Meraklı', question: 'Soru Soruyor'
};

// Geçmişe mesaj ekle
function addToHistoryPanel(role, text) {
    const item = document.createElement('div');
    item.className = `history-item ${role === 'user' ? 'user' : 'ai'}`;

    // Temiz metin (ACT tokenlarından arındırılmış)
    const displayRes = processActTokens(text);

    if (role === 'user') {
        item.innerHTML = `
            <div class="content">${displayRes}</div>
        `;
    } else {
        item.innerHTML = `
            <div class="bubble">
                <img src="./ela_avatar.png" alt="bot" class="avatar-icon">
                <div class="content">${displayRes}</div>
            </div>
        `;
    }

    historyList.appendChild(item); // Mesajları alttan ekle
    historyList.scrollTop = historyList.scrollHeight;
}

let currentLang = 'tr';
const translations = {
    tr: { subtitle: "Otobüs bileti Randevu AI Asistanı", placeholder: "Bir mesaj yazın...", welcome: "Merhaba, ben Ela. Size en uygun otobüs biletini bulmam için nereden nereye ve hangi tarihte seyahat edeceğinizi söyler misiniz?", thinking: "Düşünüyor..." },
    en: { subtitle: "Bus Ticket Booking AI Assistant", placeholder: "Type a message...", welcome: "Hello, I'm Ela. Could you tell me where you are traveling from, your destination, and your travel dates so I can find the best bus ticket for you?", thinking: "Thinking..." }
};

function setLanguage(lang) {
    currentLang = lang;
    chatInput.placeholder = translations[lang].placeholder;
    
    // Alt başlık çevirisi
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

// Ses aç/kapat butonu
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

            try {
                formData.append('lang', currentLang); // Aktif dili STT'ye ilet
                const res = await fetch('http://localhost:8001/api/stt', { method: 'POST', body: formData });
                if (res.ok) {
                    const data = await res.json();
                    if (data.text && data.text.trim().length > 0) { 
                        chatInput.value = data.text; 
                        sendMessage(); 
                    }
                    else subtitle.textContent = "Sesi anlayamadım.";
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
        setEmotion('relaxed'); // Dinlerken sakin ifade
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
    if (e.key === 'Enter') {
        e.preventDefault();
        sendMessage(); 
    }
});
chatInput.addEventListener('input', () => { if (chatInput.value.trim().length > 0) stopAudio(); });

const chatHistory = []; // Konuşma geçmişi (son 10 mesaj gönderilir)

let isSending = false;

async function sendMessage() {
    if (isSending) return;
    const text = chatInput.value.trim();
    if (!text) return;

    isSending = true;
    stopAudio();
    await initWebAudio();
    handleEmotionsLocal(text); // Kullanıcı mesajına anlık tepki
    chatHistory.push({ role: 'user', content: text });
    addToHistoryPanel('user', text); // Sidebar'a ekle
    chatInput.value = '';

    subtitle.textContent = translations[currentLang].thinking;
    setEmotion('think'); // Düşünüyor ifadesi
    currentFullResponse = ""; // Yeni stream için sıfırla

    const payload = JSON.stringify({
        text: text,
        lang: currentLang,
        history: chatHistory.slice(0, -1).slice(-10) // SADECE önceki mesajları gönder (son mesaj hariç)
    });

    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(payload);
    } else {
        // Socket kapalıysa bağlan ve hazır olunca gönder
        subtitle.textContent = "Bağlanıyor...";
        initWebSocket();
        const waitAndSend = setInterval(() => {
            if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                clearInterval(waitAndSend);
                chatSocket.send(payload);
            }
        }, 200);
        // 5 saniye sonra vazgeç
        setTimeout(() => {
            clearInterval(waitAndSend);
            if (subtitle.textContent === "Bağlanıyor...") subtitle.textContent = "Bağlantı sağlanamadı.";
        }, 5000);
    }
}

// ============================================================
// SES ÇALMA — TTS STREAMING QUEUE
// Chunk'lar sırayla çalınır, önceki bitmeden sonraki başlamaz
// ============================================================
let audioQueue = [];       // Bekleyen ses chunk'ları
let isPlayingQueue = false; // Kuyruk şu an işleniyor mu

async function processAudioQueue() {
    if (isPlayingQueue || audioQueue.length === 0) return;
    isPlayingQueue = true;

    // Index'e göre sırala
    audioQueue.sort((a, b) => a.index - b.index);

    while (audioQueue.length > 0) {
        const item = audioQueue.shift();
        await playBase64Audio(item.content);
    }
    isPlayingQueue = false;
}

// ============================================================
// SES ÇALMA (BASE64 MP3)
// Backend'den gelen base64 sesi çözer ve Web Audio API ile çalar
// ============================================================
async function playBase64Audio(base64Str) {
    if (!audioCtx) await initWebAudio();
    if (isListening || chatInput.value.trim().length > 0) return; // Kullanıcı aktifse çalma

    try {
        const res = await fetch(`data:audio/mpeg;base64,${base64Str}`);
        const arrayBuffer = await res.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

        stopAudio(); // Varsa önceki sesi durdur

        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        activeSource = source;
        isSpeaking = true;

        source.onended = () => {
            if (activeSource === source) { activeSource = null; isSpeaking = false; }
            // Konuşma bitince 2 saniye sonra nötre dön
            setTimeout(() => setEmotion('neutral'), 2000);
        };

        // Ses -> Analizör (lip-sync için) -> Hoparlör
        source.connect(analyser);
        if (!isAudioMuted) analyser.connect(audioCtx.destination);
        source.start(0);

    } catch (e) {
        isSpeaking = false;
        subtitle.textContent = "Ses çalınamadı.";
    }
}