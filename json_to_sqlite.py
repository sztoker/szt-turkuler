"""JSON → SQLite
turkuler/*.json dosyalarını okuyup SQLite veritabanı üretir.
Sözlük verisini de ekler.
Çıktı: turku.db (repo kökünde)
"""
import json
import glob
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.join(BASE_DIR, 'turkuler')
SOZLUK_CSV = os.path.join(BASE_DIR, 'sozluk.csv')
OUT_DB = os.path.join(BASE_DIR, 'turku.db')

SCHEMA = """
DROP TABLE IF EXISTS turkuler;
DROP TABLE IF EXISTS turkuler_fts;
DROP TABLE IF EXISTS sozluk;

CREATE TABLE turkuler (
  id          TEXT PRIMARY KEY,
  baslik      TEXT NOT NULL,
  sozler_html TEXT NOT NULL,
  sozler_duz  TEXT NOT NULL,
  meta_json   TEXT NOT NULL,
  versiyon    INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_turkuler_baslik ON turkuler(baslik COLLATE NOCASE);

CREATE VIRTUAL TABLE turkuler_fts USING fts5(
  id UNINDEXED,
  baslik,
  sozler_duz,
  yore,
  derleyen,
  kaynak_kisi,
  soz,
  muzik,
  tokenize = "unicode61 remove_diacritics 2"
);

CREATE TABLE sozluk (
  deyim     TEXT PRIMARY KEY,
  aciklama  TEXT NOT NULL
);

CREATE INDEX idx_sozluk_deyim ON sozluk(deyim COLLATE NOCASE);
"""


def main():
    if os.path.exists(OUT_DB):
        os.remove(OUT_DB)

    conn = sqlite3.connect(OUT_DB)
    conn.executescript(SCHEMA)

    # Türküleri yükle
    json_files = sorted(glob.glob(os.path.join(JSON_DIR, '**', '*.json'), recursive=True))
    print(f"JSON dosyaları bulundu: {len(json_files)}")

    turku_sayisi = 0
    skipped = 0
    for path in json_files:
        with open(path, 'r', encoding='utf-8') as f:
            t = json.load(f)

        # Yayınlanabilir değilse atla
        sistem = t.get('sistem', {})
        if not sistem.get('yayinlanabilir', True):
            skipped += 1
            continue

        meta = t.get('meta', {})

        conn.execute(
            "INSERT INTO turkuler (id, baslik, sozler_html, sozler_duz, meta_json, versiyon) VALUES (?,?,?,?,?,?)",
            (
                t['id'],
                t['baslik'],
                t.get('sozler_html', ''),
                t.get('sozler_duz', ''),
                json.dumps(meta, ensure_ascii=False),
                sistem.get('versiyon', 1)
            )
        )

        conn.execute(
            "INSERT INTO turkuler_fts (id, baslik, sozler_duz, yore, derleyen, kaynak_kisi, soz, muzik) VALUES (?,?,?,?,?,?,?,?)",
            (
                t['id'],
                t['baslik'],
                t.get('sozler_duz', ''),
                meta.get('yore', ''),
                meta.get('derleyen', ''),
                meta.get('kaynak_kisi', ''),
                meta.get('soz', ''),
                meta.get('muzik', '')
            )
        )
        turku_sayisi += 1

    print(f"Türkü eklendi: {turku_sayisi}")
    if skipped:
        print(f"  Atlandı (yayinlanabilir=False): {skipped}")

    # Sözlüğü yükle
    if os.path.exists(SOZLUK_CSV):
        import csv
        sozluk_sayisi = 0
        with open(SOZLUK_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                deyim = (row.get('deyim') or '').strip()
                # CSV'de 'acıklama' (Türkçe i) veya 'aciklama' olabilir
                aciklama = (row.get('acıklama') or row.get('aciklama') or '').strip()
                if not deyim or not aciklama:
                    continue
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO sozluk (deyim, aciklama) VALUES (?,?)",
                        (deyim, aciklama)
                    )
                    sozluk_sayisi += 1
                except Exception as e:
                    print(f"  sozluk hata: {deyim}: {e}")
        print(f"Sözlük girdisi eklendi: {sozluk_sayisi}")
    else:
        print("sozluk.csv bulunamadı, sözlük atlandı.")

    conn.commit()

    # İstatistikler
    print("\n=== İstatistikler ===")
    for tbl in ['turkuler', 'sozluk']:
        cnt = conn.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
        print(f"  {tbl}: {cnt} kayıt")

    conn.close()

    size_mb = os.path.getsize(OUT_DB) / (1024 * 1024)
    print(f"\nDB boyutu: {size_mb:.2f} MB")
    print(f"Çıktı: {OUT_DB}")


if __name__ == '__main__':
    main()
