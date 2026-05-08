/**
 * main.js — Giriş noktası
 *
 * Tüm modülleri bir araya getirir ve UI olay dinleyicilerini bağlar.
 * İş mantığı avatar.js / audio.js / chat.js içindedir.
 *
 * Mikrofon artık "basılı tut" değil, VAD (Voice Activity Detection)
 * toggle sistemiyle çalışır: bir kez tıkla → sürekli dinle.
 */
import { loadVRM, AVATAR_URLS } from './js/avatar.js';   // Sahneyi başlatır ve animasyon döngüsünü çalıştırır

// ─── Varsayılan ses garantisi ───────────────────────────────────────
// Özel bir avatar yüklenmemişse (avatarFileName yoksa) ses her zaman
// kadın (default) olmalıdır — avatar.vrm varsayılan kadın karakterdir.
if (!localStorage.getItem('avatarFileName')) {
    localStorage.setItem('avatarVoice', 'default');
}
import {
    initWebAudio,
    playBase64Audio,
    stopAudio,
    toggleMute,
    toggleVAD,
} from './js/audio.js';
import {
    API_BASE,
    getLang,
    setLanguage,
    sendMessage,
    addToHistoryPanel,
    initWebSocket,
    resetChat,
    speakWelcomeMessage,
} from './js/chat.js';

// ─── WebSocket bağlantısını başlat ───────────────────────────

initWebSocket();

// İlk yüklemede avatar hazır olunca konuşmayı dene
window.addEventListener('vrm-loaded', () => {
    speakWelcomeMessage();
});

// Tarayıcı autoplay kısıtlamalarını aşmak için ilk etkileşimde (tıklama, dokunma) ses tetikleyici
const _initOnFirstInteraction = async () => {
    await initWebAudio();
    speakWelcomeMessage();
    // Dinleyiciyi kaldır (sadece bir kez çalışmalı)
    ['click', 'touchstart', 'keydown'].forEach(evt => 
        window.removeEventListener(evt, _initOnFirstInteraction)
    );
};
['click', 'touchstart', 'keydown'].forEach(evt => 
    window.addEventListener(evt, _initOnFirstInteraction, { once: false })
);

// ─── UI elementleri ───────────────────────────────────────────

const chatInput       = document.getElementById('chat-input');
const sendBtn         = document.getElementById('send-btn');
const micBtn          = document.getElementById('mic-btn');
const audioBtn        = document.getElementById('audio-btn');
const langTrBtn       = document.getElementById('lang-tr');
const langEnBtn       = document.getElementById('lang-en');
const historySidebar  = document.getElementById('history-sidebar');
const toggleSidebarBtn = document.getElementById('toggle-sidebar');
const closeSidebarBtn  = document.getElementById('close-sidebar');
const subtitle        = document.getElementById('subtitle');

// ─── Dil butonları ────────────────────────────────────────────

langTrBtn?.addEventListener('click', () => { setLanguage('tr'); resetChat(); speakWelcomeMessage(); });
langEnBtn?.addEventListener('click', () => { setLanguage('en'); resetChat(); speakWelcomeMessage(); });

// ─── Mesaj gönderme ───────────────────────────────────────────

sendBtn?.addEventListener('click', () => sendMessage());
chatInput?.addEventListener('keypress', e => {
    if (e.key === 'Enter') { e.preventDefault(); sendMessage(); }
});
chatInput?.addEventListener('input', () => {
    if (chatInput.value.trim().length > 0) stopAudio();
});

// ─── Ses açma/kapama ─────────────────────────────────────────

audioBtn?.addEventListener('click', async () => {
    await initWebAudio();
    toggleMute(audioBtn);
});

// ─── Mikrofon: VAD Toggle ──────────────────────────────────────
// Tek tıkla aç, tek tıkla kapat. Konuşma algılanınca otomatik kayıt.

micBtn?.addEventListener('click', async () => {
    await initWebAudio();
    await toggleVAD(
        micBtn,
        // normalize metin backend'e, ham transkript ekranda görünsün
        async (normalizedText, displayText) => {
            if (chatInput) chatInput.value = normalizedText;
            sendMessage(displayText);
        },
        API_BASE,
        getLang,
        subtitle,
    );
});

// Dokunmatik ekranlar için (mousedown/mouseup artık kullanılmıyor)
micBtn?.addEventListener('touchstart', e => e.preventDefault(), { passive: false });

// ─── Sidebar ─────────────────────────────────────────────────

toggleSidebarBtn?.addEventListener('click', () => historySidebar?.classList.add('open'));
closeSidebarBtn?.addEventListener('click',  () => historySidebar?.classList.remove('open'));

// ─── Cinsiyet / Avatar Seçimi ─────────────────────────────

const AVATARS = {
    female: { model: AVATAR_URLS.female, voice: 'default', rotation: 0 },
    male:   { model: AVATAR_URLS.male,   voice: 'male',    rotation: 0 },
};

const genderFemaleBtn = document.getElementById('gender-female');
const genderMaleBtn   = document.getElementById('gender-male');

async function _switchAvatar(gender) {
    const cfg = AVATARS[gender];
    if (!cfg) return;
    genderFemaleBtn?.classList.toggle('active', gender === 'female');
    genderMaleBtn?.classList.toggle('active',   gender === 'male');
    localStorage.setItem('avatarVoice', cfg.voice);
    resetChat();
    try { 
        await loadVRM(cfg.model, null, cfg.rotation); 
        speakWelcomeMessage();
    }
    catch (e) { console.error('Avatar yüklenemedi:', e); }
}

genderFemaleBtn?.addEventListener('click', () => _switchAvatar('female'));
genderMaleBtn?.addEventListener('click',   () => _switchAvatar('male'));

// ─── Avatar Ayarları Modal ───────────────────────────────────────

const avatarSettingsBtn  = document.getElementById('avatar-settings-btn');
const avatarModal        = document.getElementById('avatar-modal');
const avatarModalClose   = document.getElementById('avatar-modal-close');
const avatarFileInput    = document.getElementById('avatar-file-input');
const avatarCurrentName  = document.getElementById('avatar-current-name');
const avatarProgressWrap = document.getElementById('avatar-progress-wrap');
const avatarProgressFill = document.getElementById('avatar-progress-fill');
const avatarProgressText = document.getElementById('avatar-progress-text');
const avatarStatus       = document.getElementById('avatar-status');
const avatarResetBtn     = document.getElementById('avatar-reset-btn');
const avatarUploadLabel  = document.querySelector('.avatar-upload-label');

/** Aktif avatar adını modal'da günceller */
function _updateAvatarNameDisplay() {
    const fileName = localStorage.getItem('avatarFileName');
    if (avatarCurrentName) {
        avatarCurrentName.textContent = fileName
            ? `Özel avatar: ${fileName}`
            : 'Varsayılan avatar (character.vrm)';
    }
}

/** Durum mesajını gösterir */
function _setAvatarStatus(msg, type = '') {
    if (!avatarStatus) return;
    avatarStatus.textContent = msg;
    avatarStatus.className = 'avatar-status' + (type ? ` ${type}` : '');
}

/** VRM dosyasını alıp yükler */
async function _handleVRMFile(file) {
    if (!file || !file.name.toLowerCase().endsWith('.vrm')) {
        _setAvatarStatus('❌ Geçersiz dosya. Lütfen .vrm uzantılı bir dosya seçin.', 'error');
        return;
    }

    // Dosyayı blob URL'e çevir (oturum süresi boyunca geçerli)
    const blobUrl = URL.createObjectURL(file);

    // Progress göster
    if (avatarProgressWrap) avatarProgressWrap.hidden = false;
    if (avatarProgressFill) avatarProgressFill.style.width = '0%';
    if (avatarProgressText) avatarProgressText.textContent = 'Yükleniyor...';
    _setAvatarStatus('');

    try {
        await loadVRM(blobUrl, p => {
            const pct = p.total > 0 ? Math.round((p.loaded / p.total) * 100) : 0;
            if (avatarProgressFill) avatarProgressFill.style.width = pct + '%';
            if (avatarProgressText) avatarProgressText.textContent = `Yükleniyor... %${pct}`;
        });

        // Başarılı — dosya adını localStorage'a kaydet (blob URL değil)
        localStorage.setItem('avatarFileName', file.name);

        if (avatarProgressFill) avatarProgressFill.style.width = '100%';
        if (avatarProgressText) avatarProgressText.textContent = 'Tamamlandı!';
        _setAvatarStatus('✅ Avatar başarıyla yüklendi: ' + file.name, 'success');
        _updateAvatarNameDisplay();
        speakWelcomeMessage();

        setTimeout(() => {
            if (avatarProgressWrap) avatarProgressWrap.hidden = true;
        }, 2000);

    } catch (err) {
        if (avatarProgressWrap) avatarProgressWrap.hidden = true;
        _setAvatarStatus('❌ Yükleme başarısız: ' + (err?.message || 'Bilinmeyen hata'), 'error');
        URL.revokeObjectURL(blobUrl);
    }
}

// Modal açılınca adı ve aktif sesi güncelle
avatarSettingsBtn?.addEventListener('click', () => {
    _updateAvatarNameDisplay();
    _setAvatarStatus('');
    if (avatarProgressWrap) avatarProgressWrap.hidden = true;
    // Ses hiç ayarlanmamışsa varsayılan = kadın (avatar.vrm için)
    if (!localStorage.getItem('avatarVoice')) localStorage.setItem('avatarVoice', 'default');
    const savedVoice = localStorage.getItem('avatarVoice');
    document.querySelectorAll('.avatar-voice-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.voice === savedVoice);
    });
    if (avatarModal) avatarModal.hidden = false;
});

// Modal kapat
avatarModalClose?.addEventListener('click', () => { if (avatarModal) avatarModal.hidden = true; });
avatarModal?.addEventListener('click', e => { if (e.target === avatarModal) avatarModal.hidden = true; });

// Dosya seçimi
avatarFileInput?.addEventListener('change', e => {
    const file = e.target.files?.[0];
    if (file) _handleVRMFile(file);
    e.target.value = '';
});

// Sürükle-bırak desteği
avatarUploadLabel?.addEventListener('dragover', e => {
    e.preventDefault();
    avatarUploadLabel.classList.add('drag-over');
});
avatarUploadLabel?.addEventListener('dragleave', () => avatarUploadLabel.classList.remove('drag-over'));
avatarUploadLabel?.addEventListener('drop', e => {
    e.preventDefault();
    avatarUploadLabel.classList.remove('drag-over');
    const file = e.dataTransfer?.files?.[0];
    if (file) _handleVRMFile(file);
});

// Ses/Cinsiyet butonları
document.querySelectorAll('.avatar-voice-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const voice = btn.dataset.voice;
        localStorage.setItem('avatarVoice', voice);
        document.querySelectorAll('.avatar-voice-btn').forEach(b =>
            b.classList.toggle('active', b.dataset.voice === voice)
        );
    });
});

// Varsayılana dön
avatarResetBtn?.addEventListener('click', async () => {
    localStorage.removeItem('avatarUrl');
    localStorage.removeItem('avatarFileName');
    localStorage.setItem('avatarVoice', 'default');  // avatar.vrm → her zaman kadın sesi
    _setAvatarStatus('');
    if (avatarProgressWrap) avatarProgressWrap.hidden = false;
    if (avatarProgressFill) avatarProgressFill.style.width = '0%';
    if (avatarProgressText) avatarProgressText.textContent = 'Yükleniyor...';
    try {
        await loadVRM(AVATAR_URLS.female, p => {
            const pct = p.total > 0 ? Math.round((p.loaded / p.total) * 100) : 0;
            if (avatarProgressFill) avatarProgressFill.style.width = pct + '%';
        });
        if (avatarProgressFill) avatarProgressFill.style.width = '100%';
        if (avatarProgressText) avatarProgressText.textContent = 'Tamamlandı!';
        _setAvatarStatus('✅ Varsayılan avatar geri yüklendi.', 'success');
        _updateAvatarNameDisplay();
        speakWelcomeMessage();
        setTimeout(() => { if (avatarProgressWrap) avatarProgressWrap.hidden = true; }, 2000);
    } catch {
        _setAvatarStatus('❌ Varsayılan avatar yüklenemedi.', 'error');
        if (avatarProgressWrap) avatarProgressWrap.hidden = true;
    }
});
