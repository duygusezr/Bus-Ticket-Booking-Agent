/**
 * js/chat.js
 * WebSocket bağlantısı, mesaj gönderme, sohbet geçmişi UI,
 * dil desteği.
 */
import { playBase64Audio, stopAudio, initWebAudio } from './audio.js';
import { showSeatMap, trySelectSeatFromText } from './seatmap.js';

// ─── Yapılandırma ─────────────────────────────────────────────

const _cfg   = window.__APP_CONFIG__ || {};
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
export const API_BASE = _cfg.apiBase || (isLocal ? 'http://localhost:8001' : '');
export const WS_BASE  = _cfg.wsBase  || (isLocal ? 'ws://localhost:8001'
    : API_BASE.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:'));

if (!API_BASE) {
    console.warn('[CONFIG] API_BASE tanımlı değil. window.__APP_CONFIG__.apiBase ayarlayın.');
}
console.log(`[CONFIG] API: ${API_BASE} | WS: ${WS_BASE}`);

// ─── Oturum ───────────────────────────────────────────────────

export let SESSION_ID = crypto.randomUUID();

// ─── UI referansları ──────────────────────────────────────────

const subtitle    = document.getElementById('subtitle');
const chatInput   = document.getElementById('chat-input');
const historyList = document.getElementById('history-list');

let welcomeMessagePlayed = false;

// ─── Dil ─────────────────────────────────────────────────────

let _currentLang = 'tr';
export const getLang = () => _currentLang;

const translations = {
    tr: {
        subtitle:    'Müşteri Asistanı',
        placeholder: 'Bir mesaj yazın...',
        welcome:     'Merhaba! Size en uygun otobüs biletini bulmam için nereden nereye ve hangi tarihte seyahat edeceğinizi söyler misiniz?',
        thinking:    'Düşünüyor...',
    },
    en: {
        subtitle:    'Müşteri Asistanı',
        placeholder: 'Type a message...',
        welcome:     "Hello! Could you tell me where you are traveling from, your destination, and your travel dates so I can find the best bus ticket for you?",
        thinking:    'Thinking...',
    },
};

/**
 * Sohbet geçmişini temizler ve hoş geldin mesajını gösterir.
 * Avatar değişiminde veya dil değişiminde çağrılır.
 */
export function resetChat() {
    stopAudio();
    welcomeMessagePlayed = false;
    isSending = false;
    currentFullResponse = '';
    chatHistory.length = 0;
    SESSION_ID = crypto.randomUUID();
    if (subtitle) subtitle.textContent = '';

    // Geçmiş listesini temizle, sadece hoş geldin mesajını bırak
    if (historyList) {
        historyList.innerHTML = '';
        const item = document.createElement('div');
        item.className = 'history-item ai';
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        const img = document.createElement('img');
        img.src = './avatar_icon.png';
        img.alt = 'bot';
        img.className = 'avatar-icon';
        const content = document.createElement('div');
        content.className = 'content';
        content.id = 'welcome-msg';
        content.textContent = translations[_currentLang].welcome;
        bubble.appendChild(img);
        bubble.appendChild(content);
        item.appendChild(bubble);
        historyList.appendChild(item);
    }
}

/**
 * Hoş geldin mesajını sesli olarak okur.
 */
export async function speakWelcomeMessage() {
    if (welcomeMessagePlayed) return;
    
    const welcomeText = translations[_currentLang].welcome;
    try {
        const response = await fetch(`${API_BASE}/api/tts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                text: welcomeText, 
                lang: _currentLang,
                voice: localStorage.getItem('avatarVoice') || 'default'
            })
        });
        if (response.ok) {
            const data = await response.json();
            if (data.audio) {
                const ctx = await initWebAudio();
                if (ctx && ctx.state === 'running') {
                    welcomeMessagePlayed = true;
                    await playBase64Audio(data.audio, data.visemes || [], welcomeText);
                } else {
                    console.warn('[TTS] AudioContext not running, welcome message deferred.');
                }
            }
        }
    } catch (err) {
        console.error('[TTS] Hoş geldin mesajı okunamadı:', err);
    }
}

export function setLanguage(lang) {
    _currentLang = lang;
    if (chatInput) chatInput.placeholder = translations[lang].placeholder;
    const aiSub = document.getElementById('ai-subtitle');
    if (aiSub) aiSub.textContent = translations[lang].subtitle;
    const welcomeMsg = document.getElementById('welcome-msg');
    if (welcomeMsg) {
        const isCurrent = [translations.tr.welcome, translations.en.welcome]
            .includes(welcomeMsg.textContent);
        if (isCurrent) welcomeMsg.textContent = translations[lang].welcome;
    }
    document.getElementById('lang-tr')?.classList.toggle('active', lang === 'tr');
    document.getElementById('lang-en')?.classList.toggle('active', lang === 'en');
}

// ─── Sohbet geçmişi UI ───────────────────────────────────────

const chatHistory = [];

/**
 * Kullanıcı veya asistan mesajını sohbet paneline ekle.
 * textContent kullanılır — XSS güvenli.
 */
export function addToHistoryPanel(role, text) {
    const item = document.createElement('div');
    item.className = `history-item ${role === 'user' ? 'user' : 'ai'}`;

    if (role === 'user') {
        const content = document.createElement('div');
        content.className = 'content';
        content.textContent = text.trim();
        item.appendChild(content);
    } else {
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        const img = document.createElement('img');
        img.src = './avatar_icon.png';
        img.alt = 'bot';
        img.className = 'avatar-icon';
        const content = document.createElement('div');
        content.className = 'content';
        content.textContent = text.trim();
        bubble.appendChild(img);
        bubble.appendChild(content);
        item.appendChild(bubble);
    }

    historyList.appendChild(item);
    historyList.scrollTop = historyList.scrollHeight;
}

// ─── WebSocket ────────────────────────────────────────────────

let chatSocket          = null;
let currentFullResponse = '';
let wsReconnectTimer    = null;
let isReconnecting      = false;
let isSending           = false;

export function initWebSocket() {
    if (chatSocket && (
        chatSocket.readyState === WebSocket.OPEN ||
        chatSocket.readyState === WebSocket.CONNECTING
    )) return;

    isReconnecting = false;
    chatSocket = new WebSocket(`${WS_BASE}/ws/chat`);

    chatSocket.onopen = () => {
        console.log('WebSocket bağlantısı başarılı.');
        if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
    };

    let currentAiBubble = null;

    chatSocket.onmessage = async event => {
        const data = JSON.parse(event.data);

        if (data.type === 'text') {
            currentFullResponse += data.content;
            const clean = currentFullResponse.trim();
            if (clean) {
                if (subtitle) subtitle.textContent = '';
                if (!currentAiBubble) {
                    currentAiBubble = document.createElement('div');
                    currentAiBubble.className = 'history-item ai';
                    const bubble = document.createElement('div');
                    bubble.className = 'bubble';
                    const img = document.createElement('img');
                    img.src = './avatar_icon.png';
                    img.alt = 'bot';
                    img.className = 'avatar-icon';
                    const content = document.createElement('div');
                    content.className = 'content';
                    bubble.appendChild(img);
                    bubble.appendChild(content);
                    currentAiBubble.appendChild(bubble);
                    historyList.appendChild(currentAiBubble);
                }
                currentAiBubble.querySelector('.content').textContent = clean;
                historyList.scrollTop = historyList.scrollHeight;
            }
        } else if (data.type === 'audio') {
            console.log('[VISEME] kelime sayisi:', (data.words||[]).length);
            await playBase64Audio(data.content, data.words || [], currentFullResponse.trim());
        } else if (data.type === 'seat_map') {
            // Koltuk haritası popup'u göster
            showSeatMap(
                data.available_seats || '',
                data.occupied_seats  || '',
                (selectedSeat) => {
                    // Kullanıcı koltuğu seçip onayladı: mesaj olarak gönder
                    if (chatInput) chatInput.value = String(selectedSeat);
                    sendMessage(`${selectedSeat} numaralı koltuğu seçiyorum`);
                }
            );
        } else if (data.type === 'done') {
            isSending = false;
            chatHistory.push({ role: 'assistant', content: currentFullResponse });
            if (!currentAiBubble && currentFullResponse.trim()) {
                addToHistoryPanel('ai', currentFullResponse);
            }
            currentAiBubble = null;
            currentFullResponse = '';
        } else if (data.type === 'error') {
            isSending = false;
            if (subtitle) subtitle.textContent = 'Hata: ' + data.content;
            addToHistoryPanel('ai', 'Hata: ' + data.content);
        }
    };

    chatSocket.onclose = event => {
        if (event.code === 1000 || isReconnecting) return;
        isReconnecting = true;
        console.warn(`WebSocket kapandı (code: ${event.code}). 3sn sonra yeniden bağlanılıyor...`);
        wsReconnectTimer = setTimeout(initWebSocket, 3000);
    };

    chatSocket.onerror = err => console.error('WebSocket hatası:', err);
}

// ─── Mesaj gönderme ───────────────────────────────────────────

export async function sendMessage(displayText = null) {
    if (isSending) return;
    const text = chatInput?.value.trim();
    if (!text) return;

    // Koltuk haritası popup'ı açıksa, metinde koltuk no varsa görsel seçimi yap
    // Normalize edilmiş 'text' kullanılır (sesli girişte displayText Türkçe kelime olabilir)
    trySelectSeatFromText(text);

    isSending = true;

    // Avatar'ı durdur — barge-in veya yazıyla gönderme fark etmez
    stopAudio();
    await initWebAudio();

    // Backend'e normalize metin gider; ekranda görünen metin ayrı olabilir
    const backendText  = text;
    const panelText    = displayText || text;

    chatHistory.push({ role: 'user', content: backendText });
    addToHistoryPanel('user', panelText);
    if (chatInput) chatInput.value = '';

    if (subtitle) subtitle.textContent = translations[_currentLang].thinking;
    currentFullResponse = '';

    const payload = JSON.stringify({
        text: backendText,
        lang: _currentLang,
        history: chatHistory.slice(0, -1).slice(-10),
        session_id: SESSION_ID,
        voice: localStorage.getItem('avatarVoice') || 'default',
    });

    if (chatSocket?.readyState === WebSocket.OPEN) {
        chatSocket.send(payload);
    } else {
        if (subtitle) subtitle.textContent = 'Bağlanıyor...';
        initWebSocket();
        const waitAndSend = setInterval(() => {
            if (chatSocket?.readyState === WebSocket.OPEN) {
                clearInterval(waitAndSend);
                chatSocket.send(payload);
            }
        }, 200);
        setTimeout(() => {
            clearInterval(waitAndSend);
            if (subtitle?.textContent === 'Bağlanıyor...') {
                subtitle.textContent = 'Bağlantı sağlanamadı.';
            }
        }, 5000);
    }
}
