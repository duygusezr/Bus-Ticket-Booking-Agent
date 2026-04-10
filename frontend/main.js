/**
 * main.js — Giriş noktası
 *
 * Tüm modülleri bir araya getirir ve UI olay dinleyicilerini bağlar.
 * İş mantığı avatar.js / audio.js / chat.js içindedir.
 *
 * Mikrofon artık "basılı tut" değil, VAD (Voice Activity Detection)
 * toggle sistemiyle çalışır: bir kez tıkla → sürekli dinle.
 */
import { loadVRM } from './js/avatar.js';   // Sahneyi başlatır ve animasyon döngüsünü çalıştırır
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
} from './js/chat.js';

// ─── WebSocket bağlantısını başlat ───────────────────────────

initWebSocket();

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

langTrBtn?.addEventListener('click', () => setLanguage('tr'));
langEnBtn?.addEventListener('click', () => setLanguage('en'));

// ─── Mesaj gönderme ───────────────────────────────────────────

sendBtn?.addEventListener('click', sendMessage);
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
        // Transkript gelince input'a yaz ve gönder
        text => {
            if (chatInput) chatInput.value = text;
            sendMessage();
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

        setTimeout(() => {
            if (avatarProgressWrap) avatarProgressWrap.hidden = true;
        }, 2000);

    } catch (err) {
        if (avatarProgressWrap) avatarProgressWrap.hidden = true;
        _setAvatarStatus('❌ Yükleme başarısız: ' + (err?.message || 'Bilinmeyen hata'), 'error');
        URL.revokeObjectURL(blobUrl);
    }
}

// Modal açılınca adı güncelle
avatarSettingsBtn?.addEventListener('click', () => {
    _updateAvatarNameDisplay();
    _setAvatarStatus('');
    if (avatarProgressWrap) avatarProgressWrap.hidden = true;
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

// Varsayılana dön
avatarResetBtn?.addEventListener('click', async () => {
    localStorage.removeItem('avatarUrl');
    localStorage.removeItem('avatarFileName');
    _setAvatarStatus('');
    if (avatarProgressWrap) avatarProgressWrap.hidden = false;
    if (avatarProgressFill) avatarProgressFill.style.width = '0%';
    if (avatarProgressText) avatarProgressText.textContent = 'Yükleniyor...';
    try {
        await loadVRM('./models/character.vrm', p => {
            const pct = p.total > 0 ? Math.round((p.loaded / p.total) * 100) : 0;
            if (avatarProgressFill) avatarProgressFill.style.width = pct + '%';
        });
        if (avatarProgressFill) avatarProgressFill.style.width = '100%';
        if (avatarProgressText) avatarProgressText.textContent = 'Tamamlandı!';
        _setAvatarStatus('✅ Varsayılan avatar geri yüklendi.', 'success');
        _updateAvatarNameDisplay();
        setTimeout(() => { if (avatarProgressWrap) avatarProgressWrap.hidden = true; }, 2000);
    } catch {
        _setAvatarStatus('❌ Varsayılan avatar yüklenemedi.', 'error');
        if (avatarProgressWrap) avatarProgressWrap.hidden = true;
    }
});
