/**
 * js/avatar.js
 * VRM avatar yükleme, animasyon döngüsü, göz kırpma,
 * nefes, kafa ve göz hareketleri, lip-sync.
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// ─── Sahne kurulumu ───────────────────────────────────────────

const canvas = document.getElementById('canvas');
const canvasContainer = document.getElementById('canvas-container');

export const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);

const scene = new THREE.Scene();
export const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
camera.position.set(0, 1.15, 1.3);

if (canvasContainer) {
    const ro = new ResizeObserver(entries => {
        for (const entry of entries) {
            const { width, height } = entry.contentRect;
            if (width > 0 && height > 0) {
                camera.aspect = width / height;
                camera.updateProjectionMatrix();
                renderer.setSize(width, height);
            }
        }
    });
    ro.observe(canvasContainer);
} else {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
}

const dirLight = new THREE.DirectionalLight(0xffffff, 2.0);
dirLight.position.set(1, 1, 1).normalize();
scene.add(dirLight);
scene.add(new THREE.AmbientLight(0xffffff, 1.0));

// ─── VRM durumu ───────────────────────────────────────────────

export let currentVrm = undefined;
export const cachedBones = { head: null, neck: null, spine: null, chest: null, upperChest: null };

let _isSpeaking = false;
let _isListening = false;
export const getSpeaking = () => _isSpeaking;
export const getListening = () => _isListening;
export function setSpeaking(v) { _isSpeaking = v; }
export function setListening(v) { _isListening = v; }

// ─── VRM yükleme ─────────────────────────────────────────────

const loader = new GLTFLoader();
loader.register(parser => new VRMLoaderPlugin(parser));

/**
 * Aktif avatar URL'ini döner.
 * Kullanıcı özel bir VRM yüklediyse o kullanılır, yoksa varsayılan.
 */
export function getActiveAvatarUrl() {
    // Blob URL kalıcı değil — initAvatar() bunu yönetir.
    // Bu fonksiyon sadece isim göstermek için kullanılır.
    const name = localStorage.getItem('avatarFileName');
    return name ? `[custom: ${name}]` : './models/character.vrm';
}

/**
 * Mevcut VRM'i sahneden kaldırır ve yeni VRM'i yükler.
 * @param {string} url - VRM dosyasının URL'i
 * @param {function} [onProgress] - Yükleme ilerleme callback'i
 * @returns {Promise<void>}
 */
export function loadVRM(url, onProgress, yRotation = 0) {
    return new Promise((resolve, reject) => {
        // Eski modeli temizle
        if (currentVrm) {
            scene.remove(currentVrm.scene);
            VRMUtils.deepDispose(currentVrm.scene);
            currentVrm = undefined;
            Object.keys(cachedBones).forEach(k => cachedBones[k] = null);
        }
        loader.load(
            url,
            gltf => {
                const vrm = gltf.userData.vrm;
                VRMUtils.removeUnnecessaryVertices(gltf.scene);
                VRMUtils.removeUnnecessaryJoints(gltf.scene);
                // VRM 0.x modeller ters yönde yüklenir — rotateVRM0 ile düzelt
                if (VRMUtils.rotateVRM0) {
                    VRMUtils.rotateVRM0(vrm);
                } else if (vrm.meta?.metaVersion === '0') {
                    vrm.scene.rotation.y = Math.PI;
                }
                if (yRotation) vrm.scene.rotation.y += yRotation;
                // Rotasyon sonrası pozisyonu sıfırla — fitCamera düzgün hizalsın
                vrm.scene.position.set(0, 0, 0);
                scene.add(vrm.scene);
                currentVrm = vrm;
                if (vrm.humanoid) {
                    const lua = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
                    const rua = vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
                    if (lua) lua.rotation.z = -1.2;
                    if (rua) rua.rotation.z = 1.2;
                    const ls = vrm.humanoid.getNormalizedBoneNode('leftShoulder');
                    const rs = vrm.humanoid.getNormalizedBoneNode('rightShoulder');
                    if (ls) ls.rotation.z = -0.1;
                    if (rs) rs.rotation.z = 0.1;
                    cachedBones.head       = vrm.humanoid.getNormalizedBoneNode('head');
                    cachedBones.neck       = vrm.humanoid.getNormalizedBoneNode('neck');
                    cachedBones.spine      = vrm.humanoid.getNormalizedBoneNode('spine');
                    cachedBones.chest      = vrm.humanoid.getNormalizedBoneNode('chest');
                    cachedBones.upperChest = vrm.humanoid.getNormalizedBoneNode('upperChest');
                }
                if (vrm.lookAt) {
                    // autoUpdate kapatılıyor — ARKit blendshape'lerle manuel kontrol
                    vrm.lookAt.autoUpdate = false;
                }

                // GLTF animasyonlarını kontrol et
                if (gltf.animations && gltf.animations.length > 0) {
                    console.log('[Anim] Animasyonlar:', gltf.animations.map(a => a.name));
                    const mixer = new THREE.AnimationMixer(vrm.scene);
                    const clip = gltf.animations.find(a => /idle|breathing|stand|loop/i.test(a.name)) || gltf.animations[0];
                    mixer.clipAction(clip).play();
                    vrm._mixer = mixer;
                } else {
                    console.log('[Anim] Modelde animasyon yok.');
                }

                // ─── Otomatik kamera hizalama ─────────────────────────────
                // Her VRM modelinin kendi orijin noktası farklı olabiliyor.
                // Bounding box hesaplayıp modelin baş üst noktasına göre
                // kamerayı konumlandırıyoruz — hangi model yüklenirse yüklensin
                // yüz/göğüs bölgesi ekranın ortasında görünür.
                _fitCameraToVRM(vrm);

                // ── Expression adapter: VRM expression mapping yoksa
                //    doğrudan blendshape (morph target) erişimine fallback yapar.
                //    Rocketbox / VIVERSE / VRoid arası uyumluluk için.
                _initExpressions(vrm);

                console.log('VRM başarıyla yüklendi:', url);
                _startBlinking();
                resolve();
            },
            p => {
                if (onProgress) onProgress(p);
            },
            err => {
                console.error('VRM yükleme hatası:', err);
                reject(err);
            }
        );
    });
}

// ─── Kamera otomatik hizalama ────────────────────────────────

/**
 * Head kemiğinin dünya pozisyonunu hedef alır — bounding box oranına
 * bağlı kalmadan her modelde tutarlı "göğüs ortası" görünümü sağlar.
 *
 * Strateji:
 *   1. Head kemiği world-space Y koordinatını al  → yüzün nerede olduğunu biliyoruz
 *   2. Kamera o noktanın biraz altına (göğüs hizasına) baksın
 *   3. Mesafeyi modelin toplam boyuna göre ölçekle — ne çok yakın ne çok uzak
 */
function _fitCameraToVRM(vrm) {
    vrm.scene.updateWorldMatrix(true, true);
    vrm.scene.updateMatrixWorld(true);

    // ── Bounding box: X/Z ortalama + toplam boy ──────────────
    const box = new THREE.Box3().setFromObject(vrm.scene);
    const size   = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);

    const modelHeight = size.y;

    // Modeli yatayda ortala
    vrm.scene.position.x = -center.x;
    vrm.scene.position.z = -center.z;

    // ── Head kemiği world-Y koordinatı ──────────────────────
    let headWorldY = null;
    if (vrm.humanoid) {
        const headBone = vrm.humanoid.getNormalizedBoneNode('head')
                      ?? vrm.humanoid.getNormalizedBoneNode('neck');
        if (headBone) {
            const wp = new THREE.Vector3();
            headBone.getWorldPosition(wp);
            headWorldY = wp.y;
        }
    }

    // Head kemiği yoksa bounding box üst %85'ini kullan (fallback)
    const headY = headWorldY ?? (box.min.y + modelHeight * 0.85);

    // Kamera göğüs hizasına baksın: head'in 0.18m altı
    // (bu sabit metre cinsinden — model boyuna bağımlı değil)
    const targetY = headY - 0.05;

    // ── Kamera mesafesi ──────────────────────────────────────
    // Modelin boyuyla orantılı, 1.0–1.8m arası
    // %45 → bel–baş arasını çerçeveler, bacaklar görünmez
    const fovRad = camera.fov * (Math.PI / 180);
    const desiredFrameHeight = modelHeight * 0.45;
    const distance = (desiredFrameHeight / 2) / Math.tan(fovRad / 2);
    const camDist  = Math.max(1.0, Math.min(distance, 1.8));

    camera.position.set(0, targetY, camDist);
    camera.lookAt(0, targetY, 0);

    console.log(
        `[fitCamera] boy=${modelHeight.toFixed(2)}m`,
        `headY=${headY.toFixed(2)}`,
        `targetY=${targetY.toFixed(2)}`,
        `mesafe=${camDist.toFixed(2)}m`
    );
}

// LookAt hedef nesnesi — kamera pozisyonuna sabitlenir
const _lookAtTarget = new THREE.Object3D();
scene.add(_lookAtTarget);

loadVRM('https://pub-1dbdf22ad0894ae8ab30f25240bada34.r2.dev/avatar.vrm', p => {
    console.log('Yükleniyor...', (100 * p.loaded / p.total).toFixed(2), '%');
}).catch(() => {
    const sub = document.getElementById('subtitle');
    if (sub) sub.textContent = "Model yüklenemedi. İnternet bağlantınızı kontrol edin.";
});



// ─── Expression Adapter ──────────────────────────────────────
// VRM 1.0 expression mapping yapılmamış veya farklı blendshape
// isimleri kullanan modellerde (Rocketbox: viseme_aa, eye_blink_L vb.),
// SkinnedMesh.morphTargetInfluences'a doğrudan yazarak fallback sağlar.
// Bu sayede tek bir setExpression('aa', x) çağrısı hem VRoid hem
// Rocketbox hem VIVERSE modellerinde çalışır.

let _morphLookup = {};            // { blendshapeName: [{mesh, index}, ...] }
const _expressionState = {};      // { aa: 0.5, blink: 0, ... }
let _smileBlendshapes = [];       // [{mesh, index}, ...] - idle smile için
let _idleSmileValue = 0;          // mevcut gülümseme şiddeti (lerp ile yumuşak geçiş)

// VRM standart adı → muhtemel blendshape adları (öncelik sırasıyla)
const EXPRESSION_ALIASES = {
    aa:    ['aa', 'viseme_aa', 'blendShape1.AA_VI_10_aa', 'A',  'mouth_a', 'Mouth_A'],
    ih:    ['ih', 'viseme_I',  'viseme_ih', 'blendShape1.AA_VI_12_I', 'I', 'mouth_i', 'Mouth_I'],
    ee:    ['ee', 'viseme_E',  'blendShape1.AA_VI_11_E', 'E', 'mouth_e', 'Mouth_E'],
    oh:    ['oh', 'viseme_O',  'viseme_oh', 'blendShape1.AA_VI_13_O', 'O', 'mouth_o', 'Mouth_O'],
    ou:    ['ou', 'viseme_U',  'viseme_ou', 'blendShape1.AA_VI_14_U', 'U', 'mouth_u', 'Mouth_U'],
    blink: ['blink', 'Blink'],
};

// Blink için tek blendshape yoksa L+R ayrı blendshape'leri dene
const BLINK_LR_ALIASES = [
    ['eye_blink_L', 'EyeBlinkLeft',  'blendShape1.AK_09_EyeBlinkLeft',  'BlinkL', 'blink_L'],
    ['eye_blink_R', 'EyeBlinkRight', 'blendShape1.AK_10_EyeBlinkRight', 'BlinkR', 'blink_R'],
];

function _initExpressions(vrm) {
    _morphLookup = {};
    _smileBlendshapes = [];
    _idleSmileValue = 0;
    Object.keys(_expressionState).forEach(k => _expressionState[k] = 0);

    vrm.scene.traverse(obj => {
        if (obj.isSkinnedMesh && obj.morphTargetDictionary) {
            for (const [name, idx] of Object.entries(obj.morphTargetDictionary)) {
                if (!_morphLookup[name]) _morphLookup[name] = [];
                _morphLookup[name].push({ mesh: obj, index: idx });
            }
        }
    });

    // Idle smile için gülümseme blendshape'lerini bul (Rocketbox: AK_XX_MouthSmileLeft/Right,
    // ARKit: mouthSmileLeft/Right, VRoid: Mouth_Smile vb. — substring match ile)
    // Geniş regex: smile içeren her blendshape adını yakala
    const smilePattern = /smile|happy|joy|^blendShape1\.AK.*[Ss]mile/i;
    for (const name of Object.keys(_morphLookup)) {
        if (smilePattern.test(name)) {
            _smileBlendshapes.push(...(_morphLookup[name]));
            console.log(`[Expr] Smile blendshape: ${name}`);
        }
    }

    const names = Object.keys(_morphLookup);
    console.log(`[Expr] ${names.length} blendshape bulundu`,
                names.length ? names.slice(0, 30) : '(model blendshape içermiyor!)');
    console.log(`[Expr] ${_smileBlendshapes.length} smile blendshape eşleşmesi`);
}

function _setMorphByAlias(aliases, value) {
    for (const alias of aliases) {
        const entries = _morphLookup[alias];
        if (entries) {
            for (const { mesh, index } of entries) {
                mesh.morphTargetInfluences[index] = value;
            }
            return true;
        }
    }
    return false;
}

function setExpression(name, value) {
    _expressionState[name] = value;

    // 1) VRM expression manager (mapping varsa kullan)
    const exprMgr = currentVrm?.expressionManager;
    if (exprMgr?.expressionMap?.[name]) {
        exprMgr.setValue(name, value);
        return;
    }

    // 2) Doğrudan morph target (Rocketbox / mapping yapılmamış VRM'ler)
    const aliases = EXPRESSION_ALIASES[name] || [name];
    if (_setMorphByAlias(aliases, value)) return;

    // 3) Blink özel durumu: tek blendshape yoksa L+R'ı dene
    if (name === 'blink') {
        for (const lrAliases of BLINK_LR_ALIASES) {
            _setMorphByAlias(lrAliases, value);
        }
    }
}

function getExpression(name) {
    return _expressionState[name] || 0;
}

// ─── ARKit yüz blendshape'leri ────────────────────────────────
// Rocketbox modelinin AK_ prefix'li blendshape'lerini doğrudan yazar

const FACE_SHAPES = {
    browInnerUp:      'blendShape1.AK_03_BrowInnerUp',
    browOuterUpL:     'blendShape1.AK_04_BrowOuterUpLeft',
    browOuterUpR:     'blendShape1.AK_05_BrowOuterUpRight',
    browDownL:        'blendShape1.AK_01_BrowDownLeft',
    browDownR:        'blendShape1.AK_02_BrowDownRight',
    cheekSquintL:     'blendShape1.AK_07_CheekSquintLeft',
    cheekSquintR:     'blendShape1.AK_08_CheekSquintRight',
    eyeLookDownL:     'blendShape1.AK_11_EyeLookDownLeft',
    eyeLookDownR:     'blendShape1.AK_12_EyeLookDownRight',
    eyeLookInL:       'blendShape1.AK_13_EyeLookInLeft',
    eyeLookInR:       'blendShape1.AK_14_EyeLookInRight',
    eyeLookOutL:      'blendShape1.AK_15_EyeLookOutLeft',
    eyeLookOutR:      'blendShape1.AK_16_EyeLookOutRight',
    eyeLookUpL:       'blendShape1.AK_17_EyeLookUpLeft',
    eyeLookUpR:       'blendShape1.AK_18_EyeLookUpRight',
};

function _setFace(key, value) {
    const name = FACE_SHAPES[key];
    if (!name) return;
    const entries = _morphLookup[name];
    if (entries) {
        for (const { mesh, index } of entries) {
            mesh.morphTargetInfluences[index] = Math.max(0, Math.min(1, value));
        }
    }
}

// ─── Kaş hareketi ────────────────────────────────────────
// Idle: ara sıra hafif kaş kaldırma (~soru ifadesi, dikkat)
// Konuşurken: daha cıvanlara kaş hareketi

let _browInner = 0, _browOuter = 0, _browDown = 0;
let _browTimer = 0;
let _browTarget = { inner: 0, outer: 0, down: 0 };

function _updateBrow(elapsed, dt) {
    _browTimer -= dt;
    if (_browTimer <= 0) {
        const r = Math.random();
        if (r < 0.35) {
            // Nötr
            _browTarget = { inner: 0, outer: 0, down: 0 };
            _browTimer = 2.0 + Math.random() * 3.0;
        } else if (r < 0.55) {
            // İç kaş kalkışı (düşünme/soru ifadesi)
            _browTarget = { inner: 0.25 + Math.random() * 0.2, outer: 0, down: 0 };
            _browTimer = 1.5 + Math.random() * 2.0;
        } else if (r < 0.70) {
            // Tam kaş kaldırma (vurgu)
            _browTarget = { inner: 0.15, outer: 0.2 + Math.random() * 0.15, down: 0 };
            _browTimer = 0.8 + Math.random() * 1.2;
        } else if (r < 0.82) {
            // Kaş çatma (odaklanma)
            _browTarget = { inner: 0, outer: 0, down: 0.12 + Math.random() * 0.1 };
            _browTimer = 1.0 + Math.random() * 2.0;
        } else {
            // Üstünkör dalga
            _browTarget = { inner: 0.08, outer: 0.08, down: 0 };
            _browTimer = 0.5 + Math.random() * 0.8;
        }
    }
    const sp = Math.min(3.5 * dt, 1.0);
    _browInner += (_browTarget.inner - _browInner) * sp;
    _browOuter += (_browTarget.outer - _browOuter) * sp;
    _browDown  += (_browTarget.down  - _browDown)  * sp;

    _setFace('browInnerUp',  _browInner);
    _setFace('browOuterUpL', _browOuter);
    _setFace('browOuterUpR', _browOuter);
    _setFace('browDownL',    _browDown);
    _setFace('browDownR',    _browDown);
}

// ─── Yanak gülümseme sıkma (Duchenne smile) ──────────────────
// İdleSmile ile eş zamanlı — gülümseme varsa gozler de hafifçe kıışar

function _updateCheekSquint(dt) {
    // _idleSmileValue ile orantılı (0.18 hedef için max ~0.22)
    const target = _idleSmileValue * 1.2;
    _setFace('cheekSquintL', target);
    _setFace('cheekSquintR', target);
}

// ─── Yavaş göz kırpma ────────────────────────────────────────
// Normal kırpma hızlıdır (~100ms).
// Zaman zaman yavaş bir kırpma eklenir (~300ms) — çok daha doğal görünür.

function _startBlinking() {
    const blink = () => {
        if (!currentVrm) { setTimeout(blink, 3000); return; }
        const slow = Math.random() < 0.2; // %20 ihtimalle yavaş kırpma
        const closeMs = slow ? 220 : 95;
        setExpression('blink', 1.0);
        setTimeout(() => {
            if (currentVrm) setExpression('blink', 0.0);
        }, closeMs);
        // Zaman zaman ardışık çift kırpma
        if (!slow && Math.random() > 0.75) {
            setTimeout(() => {
                if (!currentVrm) return;
                setExpression('blink', 1.0);
                setTimeout(() => { if (currentVrm) setExpression('blink', 0.0); }, 80);
            }, 160);
        }
        setTimeout(blink, 2500 + Math.random() * 4500);
    };
    setTimeout(blink, 1000 + Math.random() * 2000);
}

// ─── Nefes ───────────────────────────────────────────────────

function _updateBreathing(elapsed) {
    if (!currentVrm?.humanoid) return;
    const b = (Math.sin(elapsed * 0.35) + 1) / 2;

    // Omuzlar hafifçe kalkar
    const ls = currentVrm.humanoid.getNormalizedBoneNode('leftShoulder');
    const rs = currentVrm.humanoid.getNormalizedBoneNode('rightShoulder');
    if (ls) ls.rotation.x = -b * 0.08;
    if (rs) rs.rotation.x = -b * 0.08;

    // Kollar omuzla birlikte
    const lua = currentVrm.humanoid.getNormalizedBoneNode('leftUpperArm');
    const rua = currentVrm.humanoid.getNormalizedBoneNode('rightUpperArm');
    if (lua) lua.rotation.z = -1.2 - b * 0.04;
    if (rua) rua.rotation.z =  1.2 + b * 0.04;

    // Göğüs kemikleri sadece öne doğru hafifçe şişer (z ekseni = öne)
    if (cachedBones.upperChest) cachedBones.upperChest.rotation.z = b * 0.012;
    if (cachedBones.chest)      cachedBones.chest.rotation.z      = b * 0.010;
}

// ─── Idle kafa ───────────────────────────────────────────────

const _idleHead = { x: 0, y: 0, z: 0 };

function _updateIdleHead(elapsed, delta) {
    if (!currentVrm || !cachedBones.head) return;
    if (_isSpeaking || _isListening) {
        const rs = Math.min(2.5 * delta, 1.0);
        _idleHead.x *= (1 - rs);
        _idleHead.y *= (1 - rs);
        _idleHead.z *= (1 - rs);
    } else {
        _idleHead.y = Math.sin(elapsed * 0.19) * 0.022 + Math.sin(elapsed * 0.07) * 0.014;
        _idleHead.x = Math.sin(elapsed * 0.13) * 0.012 + Math.sin(elapsed * 0.31) * 0.006;
        _idleHead.z = _idleHead.y * 0.12;
    }
    _applyHead();
}

// ─── Aktif kafa ──────────────────────────────────────────────

const _headOffset = { x: 0, y: 0, z: 0 };

function _updateActiveHead(elapsed, delta) {
    if (!currentVrm || !cachedBones.head) return;
    const sx = _isSpeaking ? Math.sin(elapsed * 2.2) * 0.012 : 0;
    const sz = _isSpeaking ? Math.cos(elapsed * 1.8) * 0.006 : 0;
    const lx = _isListening ? Math.sin(elapsed * 1.5) * 0.012 : 0;
    const lz = _isListening ? Math.cos(elapsed * 1.1) * 0.008 : 0;
    const hs = Math.min(3.0 * delta, 1.0);
    _headOffset.x += (sx + lx - _headOffset.x) * hs;
    _headOffset.y += (0 - _headOffset.y) * hs;
    _headOffset.z += (sz + lz - _headOffset.z) * hs;
    _applyHead();
}

function _applyHead() {
    if (!cachedBones.head) return;
    cachedBones.head.rotation.x = _idleHead.x + _headOffset.x;
    cachedBones.head.rotation.y = _idleHead.y + _headOffset.y;
    cachedBones.head.rotation.z = _idleHead.z + _headOffset.z;
}

// ─── Idle smile (konuşmazken hafif gülümseme) ──────────────
// • Konuşma yokken: gülümseme ~0.55 değerine yükselir (belirgin ama doğal)
// • Konuşma başlayınca: 0'a fade out (lip-sync ile çakışmasın)
// • Sadece smile blendshape'i bulunduğunda çalışır
function _updateIdleSmile(dt) {
    if (!_smileBlendshapes.length) return;
    const target = _isSpeaking ? 0.0 : 0.18;
    _idleSmileValue += (target - _idleSmileValue) * Math.min(3.0 * dt, 1.0);
    for (const { mesh, index } of _smileBlendshapes) {
        mesh.morphTargetInfluences[index] = _idleSmileValue;
    }
}

// ─── Göz hareketi ────────────────────────────────────────────

// Göz bakış durumu
let _eyeYaw = 0, _eyePitch = 0; // mevcut blendshape değerleri

function _updateEye(elapsed, delta) {
    // Tüm ARKit göz yön blendshape'lerini sıfırla — model öne bakıyor = kameraya bakmış
    _setFace('eyeLookInL',   0);
    _setFace('eyeLookOutL',  0);
    _setFace('eyeLookInR',   0);
    _setFace('eyeLookOutR',  0);
    _setFace('eyeLookDownL', 0);
    _setFace('eyeLookDownR', 0);
    _setFace('eyeLookUpL',   0);
    _setFace('eyeLookUpR',   0);
}

// ─── Viseme-driven lip sync ──────────────────────────────────
// Microsoft Edge-TTS viseme ID (0-21) → VRM expression değerleri
const VISEME_SHAPES = [
    { aa: 0,    ih: 0,    ee: 0,    oh: 0,    ou: 0    }, // 0: silence
    { aa: 0.45, ih: 0,    ee: 0,    oh: 0,    ou: 0    }, // 1: ae, ax, ah
    { aa: 0.60, ih: 0,    ee: 0,    oh: 0,    ou: 0    }, // 2: aa (geniş)
    { aa: 0,    ih: 0,    ee: 0,    oh: 0.55, ou: 0    }, // 3: ao
    { aa: 0,    ih: 0,    ee: 0.45, oh: 0,    ou: 0    }, // 4: ey, eh, uh
    { aa: 0,    ih: 0.25, ee: 0.25, oh: 0,    ou: 0    }, // 5: er
    { aa: 0,    ih: 0.50, ee: 0,    oh: 0,    ou: 0    }, // 6: y, iy, ih
    { aa: 0,    ih: 0,    ee: 0,    oh: 0,    ou: 0.50 }, // 7: w, uw
    { aa: 0,    ih: 0,    ee: 0,    oh: 0.50, ou: 0    }, // 8: ow
    { aa: 0.35, ih: 0,    ee: 0,    oh: 0.25, ou: 0    }, // 9: aw
    { aa: 0,    ih: 0,    ee: 0,    oh: 0.40, ou: 0    }, // 10: oy
    { aa: 0.35, ih: 0.20, ee: 0,    oh: 0,    ou: 0    }, // 11: ay
    { aa: 0.15, ih: 0,    ee: 0,    oh: 0,    ou: 0    }, // 12: h
    { aa: 0,    ih: 0,    ee: 0,    oh: 0,    ou: 0.25 }, // 13: r
    { aa: 0,    ih: 0.25, ee: 0,    oh: 0,    ou: 0    }, // 14: l
    { aa: 0,    ih: 0.12, ee: 0,    oh: 0,    ou: 0    }, // 15: s, z
    { aa: 0,    ih: 0,    ee: 0,    oh: 0,    ou: 0.30 }, // 16: sh, ch, jh
    { aa: 0.18, ih: 0,    ee: 0,    oh: 0,    ou: 0    }, // 17: th, dh
    { aa: 0,    ih: 0.18, ee: 0,    oh: 0,    ou: 0    }, // 18: f, v
    { aa: 0,    ih: 0.18, ee: 0,    oh: 0,    ou: 0    }, // 19: d, t, n
    { aa: 0.18, ih: 0,    ee: 0,    oh: 0,    ou: 0    }, // 20: k, g, ng
    { aa: 0,    ih: 0,    ee: 0,    oh: 0,    ou: 0    }, // 21: p, b, m (dudaklar kapalı)
];

// Viseme modu aktifken frekans analizi devre dışı kalır
let _visemeMode = false;
export function setVisemeMode(enabled) { _visemeMode = enabled; }

// ─── Rocketbox AA_VI tam viseme sistemi ────────────────────
// Model şu blendshape'lere sahip (AA_VI prefix'li):
// 00_Sil  01_PP  02_FF  03_TH  04_DD  05_KK  06_CH
// 07_SS   08_nn  09_RR  10_aa  11_E   12_I   13_O  14_U
//
// Her harf bu setlerden birine map'lenir.
// applyRocketboxShape(suffix) → diğerlerini sıfırlayıp hedefi 1.0 yapır.

const ROCKETBOX_VISEMES = [
    'blendShape1.AA_VI_00_Sil',
    'blendShape1.AA_VI_01_PP',
    'blendShape1.AA_VI_02_FF',
    'blendShape1.AA_VI_03_TH',
    'blendShape1.AA_VI_04_DD',
    'blendShape1.AA_VI_05_KK',
    'blendShape1.AA_VI_06_CH',
    'blendShape1.AA_VI_07_SS',
    'blendShape1.AA_VI_08_nn',
    'blendShape1.AA_VI_09_RR',
    'blendShape1.AA_VI_10_aa',
    'blendShape1.AA_VI_11_E',
    'blendShape1.AA_VI_12_I',
    'blendShape1.AA_VI_13_O',
    'blendShape1.AA_VI_14_U',
];

// Viseme lerp sistemi: _targetVI index'ine doğru her frame yumuşak geçiş
let _targetVI  = 0;       // hedef AA_VI index (0-14)
let _currentVIValues = new Float32Array(15); // mevcut blendshape değerleri

/** Tüm AA_VI blendshape'lerini anında sıfırlar (lerp yok) — ses bitişinde çağrılır */
export function resetVisemeImmediate() {
    _targetVI = 0;
    _currentVIValues.fill(0);
    for (const name of ROCKETBOX_VISEMES) {
        const entries = _morphLookup[name];
        if (entries) {
            for (const { mesh, index: mIdx } of entries) {
                mesh.morphTargetInfluences[mIdx] = 0;
            }
        }
    }
}

/** Hedef viseme index'ini set eder — animation loop lerp ile uygular */
export function applyRocketboxViseme(index) {
    _targetVI = Math.max(0, Math.min(14, index));
}

/** Animation loop'tan her frame çağrılır */
export function updateVisemeLerp(dt) {
    if (!Object.keys(_morphLookup).length) return;
    // Viseme modu kapalıyken daha hızlı sıfırla (kapanış), açıkken doğal geçiş
    const speed = Math.min((_visemeMode ? 16 : 28) * dt, 1.0);
    for (let i = 0; i < 15; i++) {
        const target = (_visemeMode && i === _targetVI) ? 0.85 : 0;
        _currentVIValues[i] += (target - _currentVIValues[i]) * speed;
        const entries = _morphLookup[ROCKETBOX_VISEMES[i]];
        if (entries) {
            for (const { mesh, index: mIdx } of entries) {
                mesh.morphTargetInfluences[mIdx] = _currentVIValues[i];
            }
        }
    }
}

// Harf → AA_VI viseme index tablosu (0-14)
const CHAR_TO_VI = {
    // Sessizlik
    ' ':0, '\t':0, ',':0, '.':0, '!':0, '?':0, ';':0, ':':0,
    // Dudak kapatan (PP)
    'b':1, 'p':1, 'm':1,
    // Diş-dudak (FF)
    'f':2, 'v':2,
    // Diş-dil (TH) — Türkçe yok ama İngilizce için
    // D/T/N (DD)
    'd':4, 't':4, 'n':4,
    // K/G (KK)
    'k':5, 'g':5, 'ğ':5, 'c':5, 'q':5,
    // Ş/Ç/J (CH)
    'ş':6, 'ç':6, 'j':6,
    // S/Z (SS)
    's':7, 'z':7, 'x':7,
    // N/Ğ özel (nn)
    // R (RR)
    'r':9,
    // Ünlüler
    'a':10, 'â':10,
    'e':11,
    'ı':12, 'i':12, 'y':12,
    'o':13, 'ö':13,
    'u':14, 'ü':14, 'w':14,
    // İngilizce diğer
    'l':8, 'h':4,
};

/**
 * Bir metni karakter-düzeyinde viseme index dizisine çevirir.
 * Sadece bilinir harfleri ekler (boşluk ve noktalama = sessizlik = 0).
 */
export function textToVisemeIndices(text) {
    const result = [];
    for (const ch of text.toLowerCase()) {
        const vi = CHAR_TO_VI[ch];
        if (vi !== undefined) result.push(vi);
    }
    return result;
}

export function applyViseme(id) { applyVisemeById(id); }
export function applyVisemeById(id) {
    const shape = VISEME_SHAPES[id] ?? VISEME_SHAPES[0];
    setExpression('aa', shape.aa);
    setExpression('ih', shape.ih);
    setExpression('ee', shape.ee);
    setExpression('oh', shape.oh);
    setExpression('ou', shape.ou);
}
export function wordToVisemes(text) { return textToVisemeIndices(text); }


// ─── Frekans tabanlı lip-sync (viseme yokken fallback) ───────────

let _analyser = null;
let _dataArray = null;
let _activeSource = null;

export function setAnalyser(a, d) { _analyser = a; _dataArray = d; }
export function setActiveSource(src) { _activeSource = src; }

export function updateLipSync() {
    if (!_analyser || !currentVrm || !_dataArray) return;
    // Viseme modu aktifse frekans analizini atla — audio.js zaten doğru shape'ı yazıyor
    if (_visemeMode) return;
    if (!_activeSource) {
        ['aa', 'ih', 'ee', 'oh', 'ou'].forEach(key => {
            const cur = getExpression(key);
            setExpression(key, cur > 0.01 ? cur * 0.85 : 0);
        });
        return;
    }
    _analyser.getByteFrequencyData(_dataArray);
    let low = 0, mid = 0, high = 0, vhigh = 0;
    for (let i = 1; i < 4; i++) low   += _dataArray[i];
    for (let i = 4; i < 10; i++) mid  += _dataArray[i];
    for (let i = 10; i < 20; i++) high += _dataArray[i];
    for (let i = 20; i < 35; i++) vhigh += _dataArray[i];
    // Orta nokta: görünür ama abartısız ağız hareketi
    // Cap ile maksimum açılma sınırlandırıldı
    const cap = (v, mx) => Math.min(v, mx);
    const lm = (key, target) => {
        const cur = getExpression(key);
        setExpression(key, cur + (target - cur) * 0.55);
    };
    lm('aa', cap(mid   / (5  * 255) * 1.1, 0.50));  // birincil ağız açma — max 0.50
    lm('ih', cap(high  / (7  * 255) * 0.9, 0.40));  // 'i' sesi
    lm('ee', cap(vhigh / (10 * 255) * 0.8, 0.35));  // 'e' sesi
    lm('oh', cap(low   / (3  * 255) * 1.0, 0.55));  // 'o' sesi
    lm('ou', cap(low   / (3  * 255) * 0.65, 0.40)); // 'u' sesi
}

export function stopLipSync() {
    if (!currentVrm) return;
    // Sadece soyut expression'ları sıfırla — Rocketbox AA_VI lerp kendi kapar
    ['aa', 'ih', 'ee', 'oh', 'ou'].forEach(key => setExpression(key, 0));
}

// ─── Ana animasyon döngüsü ────────────────────────────────────

const clock = new THREE.Clock();
const fpsCounter = document.getElementById('fps-counter');
let _frames = 0, _lastTime = performance.now();

function animate() {
    requestAnimationFrame(animate);
    const dt = clock.getDelta();
    const el = clock.getElapsedTime();
    if (currentVrm) {
        currentVrm.update(dt);
        if (currentVrm._mixer) currentVrm._mixer.update(dt);
        _updateBreathing(el);
        _updateIdleHead(el, dt);
        updateLipSync();
        _updateActiveHead(el, dt);
        _updateEye(el, dt);
        _updateIdleSmile(dt);
        _updateCheekSquint(dt);
        _updateBrow(el, dt);
        updateVisemeLerp(dt);
    }
    renderer.render(scene, camera);
    _frames++;
    const now = performance.now();
    if (now >= _lastTime + 1000) {
        if (fpsCounter) {
            fpsCounter.innerHTML = `<i class="fa-solid fa-gauge"></i> FPS: ${Math.round((_frames * 1000) / (now - _lastTime))}`;
        }
        _frames = 0;
        _lastTime = now;
    }
}
animate();
