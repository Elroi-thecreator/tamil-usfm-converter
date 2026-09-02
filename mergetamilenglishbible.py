import streamlit as st
import sqlite3
import urllib.request
import json
import tempfile
import os

st.set_page_config(page_title="Tamil + KJV Bible Database Merger", page_icon="📖", layout="centered")

st.title("📖 Tamil + KJV Bible DB Merger")
st.write("Upload your existing `tamil_bible.db` to merge public domain King James Version (KJV) text.")

CANONICAL_BOOKS = [
    "genesis", "exodus", "leviticus", "numbers", "deuteronomy",
    "joshua", "judges", "ruth", "1 samuel", "2 samuel",
    "1 kings", "2 kings", "1 chronicles", "2 chronicles", "ezra",
    "nehemiah", "esther", "job", "psalms", "proverbs",
    "ecclesiastes", "song of solomon", "isaiah", "jeremiah", "lamentations",
    "ezekiel", "daniel", "hosea", "joel", "amos",
    "obadiah", "jonah", "micah", "nahum", "habakkuk",
    "zephaniah", "haggai", "zechariah", "malachi",
    "matthew", "mark", "luke", "john", "acts",
    "romans", "1 corinthians", "2 corinthians", "galatians", "ephesians",
    "philippians", "colossians", "1 thessalonians", "2 thessalonians", "1 timothy",
    "2 timothy", "titus", "philemon", "hebrews", "james",
    "1 peter", "2 peter", "1 john", "2 john", "3 john",
    "jude", "revelation"
]
BOOK_MAP = {name: i + 1 for i, name in enumerate(CANONICAL_BOOKS)}
BOOK_MAP["psalm"] = 19
BOOK_MAP["song of songs"] = 22

uploaded_file = st.file_uploader("Choose your tamil_bible.db file", type=["db", "sqlite", "sqlite3"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(uploaded_file.read())
        tmp_db_path = tmp.name

    st.success("File uploaded successfully!")

    if st.button("🚀 Merge KJV English Verses"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("1/4: Downloading KJV dataset...")
        progress_bar.progress(20)

        # Download from a raw, flat cross-platform source
        url = "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/en_kjv.json"
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            st.error(f"Failed to fetch data: {e}")
            st.stop()

        status_text.text("2/4: Connecting to SQLite database...")
        progress_bar.progress(40)

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(verses);")
        columns = [col[1] for col in cursor.fetchall()]
        if "text_en" not in columns:
            cursor.execute("ALTER TABLE verses ADD COLUMN text_en TEXT;")
            conn.commit()

        status_text.text("3/4: Parsing and populating KJV verses...")
        progress_bar.progress(60)

        parsed_verses = []

        # Thiago Bodruk KJV format: list of 66 book objects:
        # [{"abbrev": "gn", "name": "Genesis", "chapters": [ ["In the beginning...", ...], ... ] }]
        if isinstance(data, list):
            for book_idx, book_obj in enumerate(data, start=1):
                if isinstance(book_obj, dict) and "chapters" in book_obj:
                    for ch_idx, chapter in enumerate(book_obj["chapters"], start=1):
                        if isinstance(chapter, list):
                            for v_idx, verse_text in enumerate(chapter, start=1):
                                parsed_verses.append((str(verse_text).strip(), book_idx, ch_idx, v_idx))
                elif isinstance(book_obj, dict) and ("book" in book_obj or "book_id" in book_obj):
                    b = book_obj.get("book") or book_obj.get("book_id")
                    c = book_obj.get("chapter")
                    v = book_obj.get("verse")
                    t = book_obj.get("text")
                    if b and c and v and t:
                        parsed_verses.append((str(t).strip(), int(b), int(c), int(v)))

        # Fallback dictionary recursive unpacker
        elif isinstance(data, dict):
            # If wrapped in a top-level key like "books" or "verses"
            for key, val in data.items():
                b_id = BOOK_MAP.get(str(key).strip().lower()) or (int(key) if str(key).isdigit() else None)
                if b_id and isinstance(val, dict):
                    for ch_key, verses in val.items():
                        if isinstance(verses, dict):
                            for v_key, t in verses.items():
                                parsed_verses.append((str(t).strip(), b_id, int(ch_key), int(v_key)))
                        elif isinstance(verses, list):
                            for v_idx, t in enumerate(verses, start=1):
                                parsed_verses.append((str(t).strip(), b_id, int(ch_key), v_idx))

        if not parsed_verses:
            st.error(f"Keys found in payload: {list(data.keys())[:10] if isinstance(data, dict) else 'Not a dict'}")
            conn.close()
            st.stop()

        # Batch update SQLite database
        cursor.executemany(
            "UPDATE verses SET text_en = ? WHERE book_id = ? AND chapter = ? AND verse = ?;",
            parsed_verses
        )
        conn.commit()
        progress_bar.progress(85)

        # Verification sample
        status_text.text("4/4: Verifying sample (John 3:16)...")
        cursor.execute(
            "SELECT book_id, chapter, verse, text_ta, text_en FROM verses WHERE book_id = 43 AND chapter = 3 AND verse = 16;"
        )
        sample = cursor.fetchone()
        conn.close()

        progress_bar.progress(100)
        status_text.empty()

        st.success(f"Successfully processed and merged {len(parsed_verses):,} KJV verses!")

        if sample:
            st.markdown("### 🔍 Preview: John 3:16 (யோவான் 3:16)")
            st.write(f"**Tamil:** {sample[3]}")
            st.write(f"**English (KJV):** {sample[4]}")

        with open(tmp_db_path, "rb") as fp:
            db_bytes = fp.read()

        st.download_button(
            label="⬇️ Download Updated tamil_bible.db",
            data=db_bytes,
            file_name="tamil_bible.db",
            mime="application/x-sqlite3",
        )

        try:
            os.remove(tmp_db_path)
        except Exception:
            pass