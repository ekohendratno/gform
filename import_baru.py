"""
Import Google Forms JSON (format baru) ke SQLite Database
Format: judul, kelas, jumlah_soal, soal[]
"""

import json
import sqlite3
import os
import re

DB_FILE = "gform_data.db"


def clean_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def init_db():
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except PermissionError:
            pass

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("DROP TABLE IF EXISTS soal")

    c.execute("""
        CREATE TABLE soal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mapel TEXT,
            kelas TEXT,
            paket TEXT,
            nomor INTEGER,
            jenis TEXT,
            pertanyaan TEXT,
            gambar TEXT,
            jawaban TEXT,
            jawaban_benar TEXT,
            poin INTEGER
        )
    """)

    conn.commit()
    return conn


def import_json(conn, json_data):
    c = conn.cursor()
    soal_list = json_data.get("soal", [])
    mapel = json_data.get("mapel", "")
    kelas = json_data.get("kelas", "")
    paket = json_data.get("paket", "")

    for soal in soal_list:
        gambar = json.dumps(soal.get("gambar", []), ensure_ascii=False)
        jawaban = json.dumps(soal.get("jawaban", []), ensure_ascii=False)
        jawaban_benar = json.dumps(soal.get("jawaban_benar", []), ensure_ascii=False)

        c.execute("""
            INSERT INTO soal (mapel, kelas, paket, nomor, jenis, pertanyaan, gambar, jawaban, jawaban_benar, poin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mapel,
            kelas,
            paket,
            soal.get("nomor"),
            soal.get("jenis"),
            clean_html(soal.get("pertanyaan", "")),
            gambar,
            jawaban,
            jawaban_benar,
            soal.get("poin", 0),
        ))

    conn.commit()


def print_summary(conn, json_data):
    c = conn.cursor()

    print("=" * 70)
    print("IMPORT BERHASIL")
    print("=" * 70)

    print(f"\nMapel:      {json_data.get('mapel')}")
    print(f"Kelas:      {json_data.get('kelas')}")
    print(f"Paket:      {json_data.get('paket')}")
    print(f"Judul:      {json_data.get('judul')}")
    print(f"Jumlah Soal: {json_data.get('jumlah_soal')}")

    c.execute("SELECT COUNT(*) FROM soal")
    total = c.fetchone()[0]
    print(f"Total rows:  {total}")

    c.execute("SELECT COUNT(*) FROM soal WHERE gambar != '[]'")
    with_img = c.fetchone()[0]
    print(f"Dengan gambar: {with_img}")

    print("\n--- SEMUA SOAL ---")
    c.execute("SELECT nomor, jenis, pertanyaan, gambar, jawaban, jawaban_benar, poin FROM soal ORDER BY nomor")
    for row in c.fetchall():
        nomor, jenis, pertanyaan, gambar, jawaban, jawaban_benar, poin = row
        gambar_list = json.loads(gambar)
        jawaban_list = json.loads(jawaban)

        img_flag = ""
        if gambar_list:
            img_flag = f" [GAMBAR: {gambar_list[0][:60]}...]"

        print(f"\n  {nomor}. {pertanyaan[:70]}...{img_flag}")
        print(f"     Jenis: {jenis} | Poin: {poin}")
        if jawaban_list:
            print(f"     Jawaban: {jawaban_list}")

    print("\n" + "=" * 70)


def main():
    print("=" * 70)
    print("IMPORT GOOGLE FORMS JSON KE SQLITE")
    print("=" * 70)

    json_file = "soal.json"

    if not os.path.exists(json_file):
        print(f"\nFile '{json_file}' tidak ditemukan.")
        print("Simpan JSON dari Apps Script sebagai 'soal.json'")
        return

    with open(json_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    print(f"\nMembaca: {json_file}")
    print(f"Judul: {json_data.get('judul')}")

    conn = init_db()
    import_json(conn, json_data)
    print_summary(conn, json_data)
    conn.close()

    print(f"\nDatabase tersimpan: {DB_FILE}")


if __name__ == "__main__":
    main()
