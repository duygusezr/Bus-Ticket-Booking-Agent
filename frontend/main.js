/**
 * main.js — Giriş noktası
 *
 * Tüm modülleri bir araya getirir ve UI olay dinleyicilerini bağlar.
 * İş mantığı avatar.js / audio.js / chat.js içindedir.
 *
 * Mikrofon artık "basılı tut" değil, VAD (Voice Activity Detection)
 * toggle sistemiyle çalışır: bir kez tıkla → sürekli dinle.
 */
import './js/avatar.js';   // Sahneyi başlatır ve animasyon döngüsünü çalıştırır
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
