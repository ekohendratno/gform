"""
Import Google Forms JSON (dari Apps Script) ke SQLite Database
"""

import json
import sqlite3
import os
import re
from datetime import datetime

DB_FILE = "gform_data.db"


def clean_html(text):
    """Hapus tag HTML dari teks"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()


def init_db():
    """Buat database baru"""
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except PermissionError:
            pass

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Drop all tables if they exist
    c.execute("DROP TABLE IF EXISTS images")
    c.execute("DROP TABLE IF EXISTS choices")
    c.execute("DROP TABLE IF EXISTS questions")
    c.execute("DROP TABLE IF EXISTS sections")
    c.execute("DROP TABLE IF EXISTS form_info")

    c.execute("""
        CREATE TABLE form_info (
            form_id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            published_url TEXT,
            edit_url TEXT,
            exported_at TEXT,
            is_quiz INTEGER,
            total_items INTEGER,
            total_questions INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id TEXT,
            item_index INTEGER,
            title TEXT,
            description TEXT,
            FOREIGN KEY (form_id) REFERENCES form_info(form_id)
        )
    """)

    c.execute("""
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id TEXT,
            item_index INTEGER,
            item_id TEXT,
            question_number INTEGER,
            type TEXT,
            title TEXT,
            help_text TEXT,
            required INTEGER,
            points INTEGER,
            section_id INTEGER,
            FOREIGN KEY (form_id) REFERENCES form_info(form_id),
            FOREIGN KEY (section_id) REFERENCES sections(id)
        )
    """)

    c.execute("""
        CREATE TABLE choices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            item_index INTEGER,
            choice_index INTEGER,
            value TEXT,
            is_correct INTEGER DEFAULT 0,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    """)

    c.execute("""
        CREATE TABLE images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id TEXT,
            item_index INTEGER,
            question_id INTEGER,
            path TEXT,
            alt_text TEXT,
            content_uri TEXT,
            drive_file_id TEXT,
            drive_file_name TEXT,
            drive_url TEXT,
            drive_direct_url TEXT,
            drive_thumbnail_url TEXT,
            FOREIGN KEY (form_id) REFERENCES form_info(form_id),
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    """)

    conn.commit()
    return conn


def import_json(conn, json_data):
    """Import JSON data ke database"""
    c = conn.cursor()

    # ============ FORM INFO ============
    c.execute("""
        INSERT INTO form_info (form_id, title, description, published_url, edit_url,
                               exported_at, is_quiz, total_items, total_questions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        json_data.get("formId"),
        json_data.get("title"),
        json_data.get("description"),
        json_data.get("publishedUrl"),
        json_data.get("editUrl"),
        json_data.get("exportedAt"),
        1 if json_data.get("isQuiz") else 0,
        json_data.get("totalItems"),
        json_data.get("totalQuestions"),
    ))

    form_id = json_data.get("formId")
    items = json_data.get("items", [])

    # ============ ITEMS ============
    section_counter = 0
    question_counter = 0
    current_section_id = None
    sections = []

    for item in items:
        item_index = item.get("index")
        item_type = item.get("type")
        title = clean_html(item.get("title", ""))
        help_text = clean_html(item.get("helpText", ""))

        # PAGE_BREAK = section header
        if item_type == "PAGE_BREAK":
            section_counter += 1
            c.execute("""
                INSERT INTO sections (form_id, item_index, title, description)
                VALUES (?, ?, ?, ?)
            """, (form_id, item_index, title, help_text))
            current_section_id = c.lastrowid
            sections.append({
                "id": current_section_id,
                "title": title,
                "description": help_text,
            })
            continue

        # Identity fields (TEXT, LIST sebelum soal pertama)
        if item_type in ["TEXT", "LIST"] and section_counter == 0:
            continue

        # ============ QUESTIONS ============
        question_counter += 1
        data = item.get("data", {})
        quiz = item.get("quiz", {})
        required = 1 if data.get("required") else 0
        points = quiz.get("points") if quiz else None

        c.execute("""
            INSERT INTO questions (form_id, item_index, item_id, question_number, type,
                                   title, help_text, required, points, section_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            form_id,
            item_index,
            item.get("itemId"),
            question_counter,
            item_type,
            title,
            help_text,
            required,
            points,
            current_section_id,
        ))

        question_id = c.lastrowid

        # ============ CHOICES ============
        choices = data.get("choices", [])
        correct_answers = quiz.get("correctAnswers", []) if quiz else []

        for choice in choices:
            choice_index = choice.get("index")
            choice_value = choice.get("value", "")
            is_correct = 1 if choice_value in correct_answers else 0

            c.execute("""
                INSERT INTO choices (question_id, item_index, choice_index, value, is_correct)
                VALUES (?, ?, ?, ?, ?)
            """, (question_id, item_index, choice_index, choice_value, is_correct))

        # ============ IMAGES ============
        images = item.get("images", [])
        for img in images:
            image_data = img.get("image", {})
            c.execute("""
                INSERT INTO images (form_id, item_index, question_id, path, alt_text,
                                    content_uri, drive_file_id, drive_file_name,
                                    drive_url, drive_direct_url, drive_thumbnail_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                form_id,
                item_index,
                question_id,
                img.get("path", ""),
                img.get("altText", ""),
                img.get("contentUri", ""),
                image_data.get("id", ""),
                image_data.get("name", ""),
                image_data.get("url", ""),
                image_data.get("directUrl", ""),
                image_data.get("thumbnailUrl", ""),
            ))

    # ============ GLOBAL IMAGES ============
    global_images = json_data.get("images", [])
    for img in global_images:
        image_data = img.get("image", {})
        # Cari question_id berdasarkan path
        path = img.get("path", "")
        match = re.search(r"items\[(\d+)\]", path)
        question_id = None
        if match:
            target_index = int(match.group(1))
            c.execute(
                "SELECT id FROM questions WHERE item_index = ? AND form_id = ?",
                (target_index, form_id),
            )
            row = c.fetchone()
            if row:
                question_id = row[0]

        c.execute("""
            INSERT INTO images (form_id, item_index, question_id, path, alt_text,
                                content_uri, drive_file_id, drive_file_name,
                                drive_url, drive_direct_url, drive_thumbnail_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            form_id,
            None,
            question_id,
            path,
            img.get("altText", ""),
            img.get("contentUri", ""),
            image_data.get("id", ""),
            image_data.get("name", ""),
            image_data.get("url", ""),
            image_data.get("directUrl", ""),
            image_data.get("thumbnailUrl", ""),
        ))

    conn.commit()


def print_summary(conn):
    """Tampilkan ringkasan"""
    c = conn.cursor()

    print("=" * 70)
    print("IMPORT BERHASIL")
    print("=" * 70)

    c.execute("SELECT * FROM form_info")
    info = c.fetchone()
    if info:
        print(f"\nForm ID:    {info[0]}")
        print(f"Title:      {info[1]}")
        print(f"Description:{info[2][:60]}...")
        print(f"Exported:   {info[5]}")
        print(f"Is Quiz:    {'Ya' if info[6] else 'Tidak'}")

    c.execute("SELECT COUNT(*) FROM sections")
    print(f"\nSections:   {c.fetchone()[0]}")

    c.execute("SELECT COUNT(*) FROM questions")
    print(f"Questions:  {c.fetchone()[0]}")

    c.execute("SELECT COUNT(*) FROM choices")
    print(f"Choices:    {c.fetchone()[0]}")

    c.execute("SELECT COUNT(*) FROM images")
    total_img = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM images WHERE drive_file_id != ''")
    downloaded_img = c.fetchone()[0]
    print(f"Images:     {total_img} ({downloaded_img} with Drive files)")

    # Sections
    print("\n--- SECTIONS ---")
    c.execute("SELECT id, title, description FROM sections")
    for row in c.fetchall():
        print(f"  [{row[0]}] {row[1]}")
        if row[2]:
            print(f"      {row[2]}")

    # Questions
    print("\n--- QUESTIONS ---")
    c.execute("""
        SELECT q.question_number, q.title, q.type, q.points, s.title,
               (SELECT COUNT(*) FROM choices WHERE question_id = q.id),
               (SELECT COUNT(*) FROM images WHERE question_id = q.id)
        FROM questions q
        LEFT JOIN sections s ON q.section_id = s.id
        ORDER BY q.question_number
    """)
    for row in c.fetchall():
        num, title, qtype, points, section, choice_count, img_count = row
        img_flag = f" [GAMBAR x{img_count}]" if img_count > 0 else ""
        print(f"\n  {num}. {title[:70]}...{img_flag}")
        print(f"     Type: {qtype} | Points: {points} | Section: {section}")
        print(f"     Choices: {choice_count}")

    # Images with Drive URLs
    print("\n--- IMAGES WITH DRIVE URLS ---")
    c.execute("""
        SELECT q.question_number, i.drive_file_name, i.drive_direct_url, i.drive_thumbnail_url
        FROM images i
        LEFT JOIN questions q ON i.question_id = q.id
        WHERE i.drive_file_id != ''
    """)
    for row in c.fetchall():
        q_num, name, direct, thumb = row
        print(f"  Q{q_num}: {name}")
        print(f"    Direct:     {direct}")
        print(f"    Thumbnail:  {thumb}")

    print("\n" + "=" * 70)


def main():
    print("=" * 70)
    print("IMPORT GOOGLE FORMS JSON KE SQLITE")
    print("=" * 70)

    # Baca JSON dari file atau input
    json_file = "bank-soal-export.json"

    if not os.path.exists(json_file):
        print(f"\nFile '{json_file}' tidak ditemukan.")
        print("Paste JSON dari Apps Script, lalu save sebagai 'bank-soal-export.json'")
        print("Atau jalankan Apps Script exportFormToJSON terlebih dahulu.")
        return

    with open(json_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    print(f"\nMembaca JSON: {json_file}")
    print(f"Form: {json_data.get('title')}")
    print(f"Items: {json_data.get('totalItems')}")
    print(f"Images: {len(json_data.get('images', []))}")

    # Buat database
    conn = init_db()

    # Import
    import_json(conn, json_data)

    # Ringkasan
    print_summary(conn)

    conn.close()
    print(f"\nDatabase tersimpan: {DB_FILE}")


if __name__ == "__main__":
    main()
