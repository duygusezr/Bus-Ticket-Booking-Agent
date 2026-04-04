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

loader.load(
    './models/character.vrm',
    gltf => {
        const vrm = gltf.userData.vrm;
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.removeUnnecessaryJoints(gltf.scene);
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
        if (vrm.lookAt) vrm.lookAt.autoUpdate = false;
        console.log('VRM başarıyla yüklendi!');
        _startBlinking();
    },
    p => console.log('Yükleniyor...', (100 * p.loaded / p.total).toFixed(2), '%'),
    err => {
        console.error('VRM yükleme hatası:', err);
        const sub = document.getElementById('subtitle');
        if (sub) sub.textContent = "Model yüklenemedi. 'models/character.vrm' dosyasını koyun.";
    }
);

// ─── Göz kırpma ──────────────────────────────────────────────

function _startBlinking() {
    const blink = () => {
        if (currentVrm?.expressionManager) {
            currentVrm.expressionManager.setValue('blink', 1.0);
            setTimeout(() => {
                if (currentVrm) currentVrm.expressionManager.setValue('blink', 0.0);
                if (Math.random() > 0.7) {
                    setTimeout(() => {
                        if (!currentVrm) return;
                        currentVrm.expressionManager.setValue('blink', 1.0);
                        setTimeout(() => {
                            if (currentVrm) currentVrm.expressionManager.setValue('blink', 0.0);
                        }, 80);
                    }, 120);
                }
            }, 100);
        }
        setTimeout(blink, 2000 + Math.random() * 4000);
    };
    blink();
}

// ─── Nefes ───────────────────────────────────────────────────

function _updateBreathing(elapsed) {
    if (!currentVrm?.humanoid) return;
    const b = (Math.sin(elapsed * 0.35) + 1) / 2;
    const ls = currentVrm.humanoid.getNormalizedBoneNode('leftShoulder');
    const rs = currentVrm.humanoid.getNormalizedBoneNode('rightShoulder');
    if (ls) ls.rotation.x = -b * 0.12;
    if (rs) rs.rotation.x = -b * 0.12;
    const lua = currentVrm.humanoid.getNormalizedBoneNode('leftUpperArm');
    const rua = currentVrm.humanoid.getNormalizedBoneNode('rightUpperArm');
    if (lua) lua.rotation.z = -1.2 - b * 0.06;
    if (rua) rua.rotation.z = 1.2 + b * 0.06;
    if (cachedBones.neck) cachedBones.neck.rotation.x = -b * 0.03;
}

// ─── Idle kafa ───────────────────────────────────────────────

const _idleHead = { x: 0, y: 0, z: 0 };
const _idleHeadTarget = { x: 0, y: 0, z: 0 };
let _idleHeadTimer = 0;

function _updateIdleHead(elapsed, delta) {
    if (!currentVrm || !cachedBones.head) return;
    if (_isSpeaking || _isListening) {
        const rs = Math.min(2.0 * delta, 1.0);
        _idleHead.x += (0 - _idleHead.x) * rs;
        _idleHead.y += (0 - _idleHead.y) * rs;
        _idleHead.z += (0 - _idleHead.z) * rs;
        _applyHead();
        _idleHeadTimer = 1.0;
        return;
    }
    _idleHeadTimer -= delta;
    if (_idleHeadTimer <= 0) {
        const r = Math.random();
        if (r < 0.30) {
            _idleHeadTarget.x = _idleHeadTarget.y = _idleHeadTarget.z = 0;
            _idleHeadTimer = 1.5 + Math.random() * 2;
        } else if (r < 0.48) {
            _idleHeadTarget.y = 0.07 + Math.random() * 0.06;
            _idleHeadTarget.x = 0;
            _idleHeadTarget.z = _idleHeadTarget.y * 0.10;
            _idleHeadTimer = 3 + Math.random() * 4;
        } else if (r < 0.66) {
            _idleHeadTarget.y = -(0.07 + Math.random() * 0.06);
            _idleHeadTarget.x = 0;
            _idleHeadTarget.z = _idleHeadTarget.y * 0.10;
            _idleHeadTimer = 3 + Math.random() * 4;
        } else if (r < 0.92) {
            _idleHeadTarget.y = (Math.random() - 0.5) * 0.1;
            _idleHeadTarget.x = 0.05 + Math.random() * 0.03;
            _idleHeadTarget.z = 0;
            _idleHeadTimer = 2 + Math.random() * 2;
        } else {
            _idleHeadTarget.y = (Math.random() - 0.5) * 0.1;
            _idleHeadTarget.x = -(0.03 + Math.random() * 0.03);
            _idleHeadTarget.z = 0;
            _idleHeadTimer = 1.5 + Math.random() * 2;
        }
    }
    const sp = Math.min(2.5 * delta, 1.0);
    _idleHead.x += (_idleHeadTarget.x - _idleHead.x) * sp;
    _idleHead.y += (_idleHeadTarget.y - _idleHead.y) * sp;
    _idleHead.z += (_idleHeadTarget.z - _idleHead.z) * sp;
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

// ─── Göz hareketi ────────────────────────────────────────────

const _eyeTarget  = { yaw: 0, pitch: 0 };
const _eyeCurrent = { yaw: 0, pitch: 0 };

function _updateEye(elapsed, delta) {
    if (!currentVrm?.lookAt) return;
    _eyeTarget.yaw   = _isSpeaking ? Math.sin(elapsed * 0.5)  * 0.008 : Math.sin(elapsed * 0.18) * 0.03;
    _eyeTarget.pitch = _isSpeaking ? Math.cos(elapsed * 0.4)  * 0.005 : Math.cos(elapsed * 0.13) * 0.02;
    const es = Math.min(1.5 * delta, 1.0);
    _eyeCurrent.yaw   += (_eyeTarget.yaw   - _eyeCurrent.yaw)   * es;
    _eyeCurrent.pitch += (_eyeTarget.pitch - _eyeCurrent.pitch) * es;
    try {
        if (typeof currentVrm.lookAt.yaw !== 'undefined') {
            currentVrm.lookAt.yaw   = _eyeCurrent.yaw;
            currentVrm.lookAt.pitch = _eyeCurrent.pitch;
        } else if (currentVrm.lookAt.applier) {
            currentVrm.lookAt.applier.applyYawPitch(_eyeCurrent.yaw, _eyeCurrent.pitch);
        }
    } catch (_) { /* VRM versiyonu uyumsuzsa sessizce geç */ }
}

// ─── Lip-sync ────────────────────────────────────────────────

let _analyser = null;
let _dataArray = null;
let _activeSource = null;

export function setAnalyser(a, d) { _analyser = a; _dataArray = d; }
export function setActiveSource(src) { _activeSource = src; }

export function updateLipSync() {
    if (!_analyser || !currentVrm?.expressionManager || !_dataArray) return;
    if (!_activeSource) {
        ['aa', 'ih', 'ee', 'oh', 'ou'].forEach(key => {
            const cur = currentVrm.expressionManager.getValue(key) || 0;
            currentVrm.expressionManager.setValue(key, cur > 0.01 ? cur * 0.85 : 0);
        });
        return;
    }
    _analyser.getByteFrequencyData(_dataArray);
    let low = 0, mid = 0, high = 0, vhigh = 0;
    for (let i = 1; i < 4; i++) low   += _dataArray[i];
    for (let i = 4; i < 10; i++) mid  += _dataArray[i];
    for (let i = 10; i < 20; i++) high += _dataArray[i];
    for (let i = 20; i < 35; i++) vhigh += _dataArray[i];
    const t = 0.04;
    const cl = (v, m) => v < t ? 0 : Math.min(v, m);
    const lm = (key, target) => {
        const cur = currentVrm.expressionManager.getValue(key) || 0;
        currentVrm.expressionManager.setValue(key, cur + (target - cur) * 0.35);
    };
    lm('aa', cl(mid   / (6  * 255) * 0.6,  0.45));
    lm('ih', cl(high  / (10 * 255) * 0.35, 0.3));
    lm('ee', cl(vhigh / (15 * 255) * 0.3,  0.25));
    lm('oh', cl(low   / (3  * 255) * 0.4,  0.35));
    lm('ou', cl(low   / (3  * 255) * 0.2,  0.22));
}

export function stopLipSync() {
    if (!currentVrm?.expressionManager) return;
    ['aa', 'ih', 'ee', 'oh', 'ou'].forEach(key =>
        currentVrm.expressionManager.setValue(key, 0)
    );
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
        _updateBreathing(el);
        _updateIdleHead(el, dt);
        updateLipSync();
        _updateActiveHead(el, dt);
        _updateEye(el, dt);
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
