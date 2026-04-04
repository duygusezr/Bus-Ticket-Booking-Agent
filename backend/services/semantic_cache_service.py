# Bu dosya kaldırıldı.
#
# Semantic cache özelliği devre dışıydı (ENABLED = False) ve hiçbir zaman
# production'da aktif edilmedi. Bağımlılıkları (numpy, sentence-transformers)
# requirements.txt'e eklenmemişti; dolayısıyla dead code olarak tespit edildi.
#
# Eğer gelecekte semantik önbellek gerekirse:
#   1. services/types.py içine CacheEntry dataclass ekle
#   2. Bağımsız bir cache servisi yaz (Redis önerilir)
#   3. requirements.txt'e bağımlılıkları ekle
#   4. chat.py'da opsiyonel olarak etkinleştir
#
# Bu dosyaya hiçbir import yok — güvenle silinebilir.
