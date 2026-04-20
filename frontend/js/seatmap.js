/**
 * js/seatmap.js
 * Koltuk seçim popup modülü.
 * Görseldeki gibi otobüs içini gösterir; boş/dolu koltuklara renk verir.
 * Kullanıcı koltuk seçip "Onayla ve Devam Et" butonuna basınca onConfirm(seatNo) çağrılır.
 */

// ─── Otobüs koltuk düzeni (standart Türk şehirlerarası otobüs, 41 koltuk) ────
// 2+2 dizilim, 10 sıra + arka 1 koltuk
// Her satır: [solPencere, solKoridur, null=koridor, sağKoridur, sağPencere]
// null = aisle (koridor boşluğu)
const BUS_ROWS = [
    // [sol-pencere, sol-koridor, SAĞ-koridor, sağ-pencere]
    [1,  2,  3,  4],
    [5,  6,  7,  8],
    [9,  10, 11, 12],
    [13, 14, 15, 16],
    [17, 18, 19, 20],
    [21, 22, 23, 24],
    [25, 26, 27, 28],
    [29, 30, 31, 32],
    [33, 34, 35, 36],
    [37, 38, 39, 40],
];
const BACK_SEAT = 41;

let _overlay = null;

/**
 * Koltuk seçim popup'ını göster.
 * @param {string} availableSeatsStr  - Virgülle ayrılmış boş koltuk numaraları ("1,3,5,...")
 * @param {string} occupiedSeatsStr   - Virgülle ayrılmış dolu koltuk numaraları ("2,4,6,...")
 * @param {function} onConfirm        - Kullanıcı koltuk seçip onaylayınca çağrılır (seatNo: number)
 */
export function showSeatMap(availableSeatsStr, occupiedSeatsStr, onConfirm) {
    // Zaten açıksa kapat
    if (_overlay) _overlay.remove();

    const availableSet = new Set(
        (availableSeatsStr || '').split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
    );
    const occupiedSet = new Set(
        (occupiedSeatsStr || '').split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
    );

    let selectedSeat = null;

    // ─── Overlay ────────────────────────────────────────────────
    _overlay = document.createElement('div');
    _overlay.id = 'seat-map-overlay';
    _overlay.className = 'seat-map-overlay';

    // Overlay dışına tıklanınca kapatma KAPATILDI (kullanıcı seçim yapmadan kapanmasın)

    // ─── Popup kutusu ────────────────────────────────────────────
    const box = document.createElement('div');
    box.className = 'seat-map-box';

    // Başlık
    const header = document.createElement('div');
    header.className = 'seat-map-header';
    header.innerHTML = `
        <div class="seat-map-title">
            <i class="fa-solid fa-bus"></i> Koltuk Seçimi
        </div>
        <div class="seat-map-subtitle">Lütfen bir koltuk seçin</div>
    `;

    // İçerik
    const body = document.createElement('div');
    body.className = 'seat-map-body';

    // Otobüs gövdesi
    const busWrap = document.createElement('div');
    busWrap.className = 'bus-wrap';

    // Şoför alanı
    const driverRow = document.createElement('div');
    driverRow.className = 'bus-driver-row';
    driverRow.innerHTML = `
        <div class="bus-driver-icon">
            <i class="fa-solid fa-steering-wheel"></i>
            <span>Şoför</span>
        </div>
        <div class="bus-door-icon">
            <i class="fa-solid fa-door-open"></i>
        </div>
    `;
    busWrap.appendChild(driverRow);

    // Koltuk sıraları
    const seatsArea = document.createElement('div');
    seatsArea.className = 'seats-area';

    // Sıra numaraları + koltuklar
    BUS_ROWS.forEach((row, rowIdx) => {
        const rowEl = document.createElement('div');
        rowEl.className = 'seat-row';

        // Sıra numarası
        const rowNum = document.createElement('div');
        rowNum.className = 'row-number';
        rowNum.textContent = rowIdx + 1;
        rowEl.appendChild(rowNum);

        // Sol taraf (2 koltuk)
        const leftPair = document.createElement('div');
        leftPair.className = 'seat-pair';
        [row[0], row[1]].forEach(seatNo => {
            leftPair.appendChild(_createSeat(seatNo, availableSet, occupiedSet, onSeatClick));
        });
        rowEl.appendChild(leftPair);

        // Koridor
        const aisle = document.createElement('div');
        aisle.className = 'aisle-gap';
        rowEl.appendChild(aisle);

        // Sağ taraf (2 koltuk)
        const rightPair = document.createElement('div');
        rightPair.className = 'seat-pair';
        [row[2], row[3]].forEach(seatNo => {
            rightPair.appendChild(_createSeat(seatNo, availableSet, occupiedSet, onSeatClick));
        });
        rowEl.appendChild(rightPair);

        seatsArea.appendChild(rowEl);
    });

    // Arka koltuk
    const backRowEl = document.createElement('div');
    backRowEl.className = 'seat-row back-row';
    const backLabel = document.createElement('div');
    backLabel.className = 'row-number';
    backLabel.textContent = '↑';
    backRowEl.appendChild(backLabel);
    const backCenter = document.createElement('div');
    backCenter.className = 'back-seat-center';
    backCenter.appendChild(_createSeat(BACK_SEAT, availableSet, occupiedSet, onSeatClick));
    backRowEl.appendChild(backCenter);
    seatsArea.appendChild(backRowEl);

    busWrap.appendChild(seatsArea);
    body.appendChild(busWrap);

    // Lejant
    const legend = document.createElement('div');
    legend.className = 'seat-legend';
    legend.innerHTML = `
        <div class="legend-item">
            <div class="legend-box legend-available"></div>
            <span>Boş Koltuk</span>
        </div>
        <div class="legend-item">
            <div class="legend-box legend-occupied"></div>
            <span>Dolu Koltuk</span>
        </div>
        <div class="legend-item">
            <div class="legend-box legend-selected"></div>
            <span>Seçilen Koltuk</span>
        </div>
    `;
    body.appendChild(legend);

    // Seçim bilgisi
    const selInfo = document.createElement('div');
    selInfo.className = 'seat-selection-info';
    selInfo.id = 'seat-selection-info';
    selInfo.textContent = 'Henüz koltuk seçilmedi';
    body.appendChild(selInfo);

    // Alt buton
    const footer = document.createElement('div');
    footer.className = 'seat-map-footer';
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'seat-confirm-btn disabled';
    confirmBtn.id = 'seat-confirm-btn';
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = `<i class="fa-solid fa-check"></i> Onayla ve Devam Et`;
    confirmBtn.addEventListener('click', () => {
        if (selectedSeat === null) return;
        _close();
        onConfirm(selectedSeat);
    });
    footer.appendChild(confirmBtn);
    body.appendChild(footer);

    // Birleştir
    box.appendChild(header);
    box.appendChild(body);
    _overlay.appendChild(box);
    document.body.appendChild(_overlay);

    // Animasyon
    requestAnimationFrame(() => _overlay.classList.add('visible'));

    // ─── Koltuk tıklama handler ──────────────────────────────────
    function onSeatClick(seatNo) {
        // Önceki seçimi temizle
        document.querySelectorAll('.seat-btn.selected').forEach(el => {
            el.classList.remove('selected');
        });

        selectedSeat = seatNo;

        // Yeni seçimi işaretle
        const target = document.querySelector(`.seat-btn[data-seat="${seatNo}"]`);
        if (target) target.classList.add('selected');

        // Bilgi güncelle
        const info = document.getElementById('seat-selection-info');
        if (info) info.textContent = `Seçilen koltuk: ${seatNo}`;

        // Butonu aktif et
        const btn = document.getElementById('seat-confirm-btn');
        if (btn) {
            btn.disabled = false;
            btn.classList.remove('disabled');
        }
    }
}

/** Popup'ı kapat */
function _close() {
    if (_overlay) {
        _overlay.classList.remove('visible');
        setTimeout(() => {
            _overlay?.remove();
            _overlay = null;
        }, 280);
    }
}

/** Tek bir koltuk elementi oluştur */
function _createSeat(seatNo, availableSet, occupiedSet, onSeatClick) {
    const btn = document.createElement('button');
    btn.className = 'seat-btn';
    btn.dataset.seat = seatNo;
    btn.textContent = seatNo;

    if (availableSet.has(seatNo)) {
        btn.classList.add('available');
        btn.title = `Koltuk ${seatNo} — Boş`;
        btn.addEventListener('click', () => onSeatClick(seatNo));
    } else {
        // Dolu (ya occupiedSet'te ya da DB'de available değil)
        btn.classList.add('occupied');
        btn.disabled = true;
        btn.title = `Koltuk ${seatNo} — Dolu`;
    }

    return btn;
}
