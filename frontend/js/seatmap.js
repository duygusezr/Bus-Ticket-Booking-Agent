/**
 * js/seatmap.js
 * Koltuk seçim popup — görseldeki düzenle birebir eşleşir.
 *
 * Otobüs düzeni (önden arkaya, yatay görünüm):
 *   ─────────────────────────────────────────────────────────
 *   [3][6][9][12][15][18]  [23]          [26][29][32][35][38][40]
 *   [2][5][8][11][14][17]  [22]          [25][28][31][34][37][39]
 *   ═══════════════════════════════════════════════════════════ ← Ana koridor
 *   [1][4][7][10][13][16]  [19][20][21]  [24][27][30][33][36]   [41]
 *   ─────────────────────────────────────────────────────────
 *
 * Sütun yapısı (17 sütun, 41 koltuk):
 *   Col 0-5 : Sol bölüm (koltuk üçlüsü: pencere+koridor+alt)
 *   Col 6   : Geçiş sütunu (23,22 üstte; altta yok — giriş kapısı)
 *   Col 7-9 : Giriş koltukları (19,20,21 altta; üstte yok)
 *   Col 10-14: Sağ bölüm ana (üçlüler)
 *   Col 15  : Sağ bölüm son üst çifti (40,39; altta yok)
 *   Col 16  : Arka köşe (41 altta; üstte yok)
 */

// ─── Sütun verisi ─────────────────────────────────────────────
// w = pencere tarafı (üst sıra),  a = koridor tarafı (orta sıra),  l = alt sıra
// null = o pozisyonda koltuk yok (boşluk hücresi)
const COLS = [
    { w: 3,    a: 2,    l: 1    },  // 0
    { w: 6,    a: 5,    l: 4    },  // 1
    { w: 9,    a: 8,    l: 7    },  // 2
    { w: 12,   a: 11,   l: 10   },  // 3
    { w: 15,   a: 14,   l: 13   },  // 4
    { w: 18,   a: 17,   l: 16   },  // 5
    { w: 23,   a: 22,   l: null },  // 6  ← geçiş (üstte 22-23, altta giriş kapısı)
    { w: null, a: null, l: 19   },  // 7  ┐
    { w: null, a: null, l: 20   },  // 8  ├─ giriş koltukları
    { w: null, a: null, l: 21   },  // 9  ┘
    { w: 26,   a: 25,   l: 24   },  // 10
    { w: 29,   a: 28,   l: 27   },  // 11
    { w: 32,   a: 31,   l: 30   },  // 12
    { w: 35,   a: 34,   l: 33   },  // 13
    { w: 38,   a: 37,   l: 36   },  // 14
    { w: 40,   a: 39,   l: null },  // 15 ← son üst çift (altta yok)
    { w: null, a: null, l: 41   },  // 16 ← arka köşe koltuk
];

// Sütun 6 ile 10 arasına bölüm ayrımı eklemek için bu index'te görsel ara boşluk koyacağız
const SECTION_GAP_AFTER = 6; // col 6'dan sonra görsel ara boşluk

let _overlay     = null;
let _availableSet = new Set();

/**
 * Popup açıkken gelen metinde koltuk numarası var mı diye kontrol eder.
 * Varsa o koltuğu seçili (yeşil) gösterir ve ~700ms sonra popup'ı kapatır.
 * @param {string} text  — Kullanıcının söylediği / yazdığı metin
 * @returns {boolean}    — Koltuk bulunup seçildiyse true
 */
export function trySelectSeatFromText(text) {
    if (!_overlay) return false;

    // Metinden 1-2 basamaklı sayı çıkar
    const match = String(text).match(/\b(\d{1,2})\b/);
    if (!match) return false;
    const num = parseInt(match[1]);
    if (isNaN(num) || num < 1) return false;

    // Sadece boş koltuklar seçilebilir
    const btn = _overlay.querySelector(`.smi-seat[data-n="${num}"].avail`);
    if (!btn) return false;

    // Önceki seçimi temizle, yeniyi işaretle
    _overlay.querySelectorAll('.smi-seat.selected').forEach(el => el.classList.remove('selected'));
    btn.classList.add('selected');

    // Bilgi metnini güncelle
    const info = document.getElementById('smi-info');
    if (info) info.textContent = `Seçilen koltuk: ${num}`;

    // Onayla butonunu aktif et (görsel için)
    const confirmBtn = document.getElementById('smi-confirm');
    if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.classList.remove('disabled'); }

    // Kısa bir süre seçimi göster, sonra kapat
    setTimeout(() => _close(), 750);
    return true;
}

/**
 * Koltuk seçim popup'ını göster.
 * @param {string}   availableSeatsStr  Virgülle ayrılmış boş koltuk no'ları
 * @param {string}   occupiedSeatsStr   Virgülle ayrılmış dolu koltuk no'ları
 * @param {function} onConfirm          (seatNo: number) → void
 */
export function showSeatMap(availableSeatsStr, occupiedSeatsStr, onConfirm) {
    if (_overlay) _overlay.remove();

    const availableSet = _parseSeats(availableSeatsStr);
    _availableSet = availableSet; // trySelectSeatFromText için koru
    let selectedSeat = null;

    // ── Overlay ───────────────────────────────────────────────
    _overlay = document.createElement('div');
    _overlay.id  = 'seat-map-overlay';
    _overlay.className = 'seat-map-overlay';

    // ── Kutu ──────────────────────────────────────────────────
    const box = document.createElement('div');
    box.className = 'seat-map-box';

    // Başlık
    box.appendChild(_buildHeader());

    // Gövde
    const body = document.createElement('div');
    body.className = 'seat-map-body';

    // Otobüs
    body.appendChild(_buildBus(availableSet, _onSeatClick));

    // Lejant
    body.appendChild(_buildLegend());

    // Seçim bilgisi
    const info = document.createElement('div');
    info.className = 'seat-selection-info';
    info.id = 'smi-info';
    info.textContent = 'Henüz koltuk seçilmedi';
    body.appendChild(info);

    box.appendChild(body);

    // Footer
    box.appendChild(_buildFooter());
    _overlay.appendChild(box);
    document.body.appendChild(_overlay);
    requestAnimationFrame(() => _overlay.classList.add('visible'));

    // ── Koltuk tıklama ────────────────────────────────────────
    function _onSeatClick(num) {
        document.querySelectorAll('.smi-seat.selected')
            .forEach(el => el.classList.remove('selected'));
        const el = document.querySelector(`.smi-seat[data-n="${num}"]`);
        if (el) el.classList.add('selected');
        selectedSeat = num;
        const infoEl = document.getElementById('smi-info');
        if (infoEl) infoEl.textContent = `Seçilen koltuk: ${num}`;
        const btn = document.getElementById('smi-confirm');
        if (btn) { btn.disabled = false; btn.classList.remove('disabled'); }
    }

    // Onayla butonu
    document.getElementById('smi-confirm')?.addEventListener('click', () => {
        if (selectedSeat === null) return;
        _close();
        onConfirm(selectedSeat);
    });
}

// ─── İç yardımcılar ──────────────────────────────────────────

function _parseSeats(str) {
    return new Set(
        (str || '').split(',')
            .map(s => parseInt(s.trim()))
            .filter(n => !isNaN(n) && n > 0)
    );
}

function _close() {
    if (!_overlay) return;
    _overlay.classList.remove('visible');
    setTimeout(() => { _overlay?.remove(); _overlay = null; }, 300);
}

function _buildHeader() {
    const h = document.createElement('div');
    h.className = 'seat-map-header';
    h.innerHTML = `
        <div class="smi-title"><i class="fa-solid fa-bus"></i> Koltuk Seçimi</div>
        <div class="smi-sub">Lütfen boş bir koltuk seçin</div>
    `;
    return h;
}

function _buildLegend() {
    const l = document.createElement('div');
    l.className = 'smi-legend';
    l.innerHTML = `
        <div class="smi-leg-item"><div class="smi-leg-box smi-avail"></div><span>Boş Koltuk</span></div>
        <div class="smi-leg-item"><div class="smi-leg-box smi-occ"></div><span>Dolu Koltuk</span></div>
        <div class="smi-leg-item"><div class="smi-leg-box smi-sel"></div><span>Seçilen Koltuk</span></div>
    `;
    return l;
}

function _buildFooter() {
    const f = document.createElement('div');
    f.className = 'seat-map-footer';
    const btn = document.createElement('button');
    btn.className = 'seat-confirm-btn disabled';
    btn.id = 'smi-confirm';
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-check"></i> Onayla ve Devam Et`;
    f.appendChild(btn);
    return f;
}

/**
 * Otobüs gövdesini oluştur.
 * Görseldeki gibi yatay düzen:
 *   Üst-pencere satırı  →  tüm w koltukları
 *   Üst-koridor satırı  →  tüm a koltukları
 *   Ana koridor çizgisi →  görsel ayraç + şoför
 *   Alt satır           →  tüm l koltukları
 */
function _buildBus(availableSet, onSeatClick) {
    const wrap = document.createElement('div');
    wrap.className = 'smi-bus-wrap';

    // İçerik (4 satır)
    const grid = document.createElement('div');
    grid.className = 'smi-grid';

    // ── Satır 1: Pencere (üst) ────────────────────────────────
    const rowW = document.createElement('div');
    rowW.className = 'smi-row';
    // Şoför tarafındaki boşluk (şoför col 0'da görünecek)
    rowW.appendChild(_spacer('smi-driver-spacer'));
    COLS.forEach((col, i) => {
        if (i === SECTION_GAP_AFTER + 1) rowW.appendChild(_gapDiv());
        rowW.appendChild(col.w !== null
            ? _seat(col.w, availableSet, onSeatClick)
            : _spacer());
    });

    // ── Satır 2: Koridor tarafı (üst) ─────────────────────────
    const rowA = document.createElement('div');
    rowA.className = 'smi-row';
    rowA.appendChild(_spacer('smi-driver-spacer'));
    COLS.forEach((col, i) => {
        if (i === SECTION_GAP_AFTER + 1) rowA.appendChild(_gapDiv());
        rowA.appendChild(col.a !== null
            ? _seat(col.a, availableSet, onSeatClick)
            : _spacer());
    });

    // ── Satır 3: Ana koridor ───────────────────────────────────
    const rowMid = document.createElement('div');
    rowMid.className = 'smi-row smi-corridor';
    const driverBox = document.createElement('div');
    driverBox.className = 'smi-driver-box';
    driverBox.innerHTML = `<i class="fa-solid fa-circle-dot"></i>`;
    rowMid.appendChild(driverBox);
    const corridorLine = document.createElement('div');
    corridorLine.className = 'smi-corridor-line';
    rowMid.appendChild(corridorLine);

    // ── Satır 4: Alt satır ────────────────────────────────────
    const rowL = document.createElement('div');
    rowL.className = 'smi-row';
    rowL.appendChild(_spacer('smi-driver-spacer'));
    COLS.forEach((col, i) => {
        if (i === SECTION_GAP_AFTER + 1) rowL.appendChild(_gapDiv());
        rowL.appendChild(col.l !== null
            ? _seat(col.l, availableSet, onSeatClick)
            : _spacer());
    });

    grid.appendChild(rowW);
    grid.appendChild(rowA);
    grid.appendChild(rowMid);
    grid.appendChild(rowL);
    wrap.appendChild(grid);
    return wrap;
}

function _seat(num, availableSet, onSeatClick) {
    const btn = document.createElement('button');
    btn.className = 'smi-seat';
    btn.dataset.n = num;
    btn.textContent = num;
    if (availableSet.has(num)) {
        btn.classList.add('avail');
        btn.title = `Koltuk ${num} — Boş`;
        btn.addEventListener('click', () => onSeatClick(num));
    } else {
        btn.classList.add('occ');
        btn.disabled = true;
        btn.title = `Koltuk ${num} — Dolu`;
    }
    return btn;
}

function _spacer(cls = '') {
    const d = document.createElement('div');
    d.className = 'smi-spacer' + (cls ? ' ' + cls : '');
    return d;
}

function _gapDiv() {
    const d = document.createElement('div');
    d.className = 'smi-section-gap';
    return d;
}
