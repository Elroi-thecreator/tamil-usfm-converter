import streamlit as st
import sqlite3
import urllib.request
import json
import tempfile
import os

st.set_page_config(page_title="Tamil + KJV Bible Database Merger", page_icon="📖", layout="centered")

st.title("📖 Tamil + KJV Bible DB Merger")
st.write("Upload your existing `tamil_bible.db` to merge public domain King James Version (KJV) text.")

# 66 canonical books mapping to standard IDs (1 to 66)
CANONICAL_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
    "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
    "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
    "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy",
    "2 Timothy", "Titus", "Philemon", "Hebrews", "James",
    "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
    "Jude", "Revelation"
]
BOOK_NAME_TO_ID = {name.lower(): i + 1 for i, name in enumerate(CANONICAL_BOOKS)}
# Common name variations
BOOK_NAME_TO_ID["psalm"] = 19
BOOK_NAME_TO_ID["song of songs"] = 22

uploaded_file = st.file_uploader("Choose your tamil_bible.db file", type=["db", "sqlite", "sqlite3"])

if uploaded_file is not None:
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(uploaded_file.read())
        tmp_db_path = tmp.name

    st.success("File uploaded successfully!")

    if st.button("🚀 Merge KJV English Verses"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Step 1: Fetch reliable KJV data source
        status_text.text("1/4: Downloading clean KJV dataset...")
        progress_bar.progress(20)

        # Using aruljohn's clean 66-book JSON repository structure
        url = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/KJV.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        try:
            with urllib.request.urlopen(req) as response:
                content = response.read().decode("utf-8")
                raw_data = json.loads(content)
        except Exception as e:
            st.error(f"Failed to download KJV text: {e}")
            st.stop()

        # Step 2: Open SQLite database & add text_en column
        status_text.text("2/4: Connecting to SQLite database & checking schema...")
        progress_bar.progress(40)

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()

        # Verify verses table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='verses';")
        if not cursor.fetchone():
            st.error("Table 'verses' not found in uploaded database!")
            conn.close()
            st.stop()

        cursor.execute("PRAGMA table_info(verses);")
        columns = [col[1] for col in cursor.fetchall()]

        if "text_en" not in columns:
            cursor.execute("ALTER TABLE verses ADD COLUMN text_en TEXT;")
            conn.commit()

        # Step 3: Parse and Populate (Universal parser)
        status_text.text("3/4: Parsing and updating English verses...")
        progress_bar.progress(60)

        parsed_verses = []  # list of tuples: (text_en, book_id, chapter, verse)

        # Format A: Scrollmapper structure {"resultset": {"row": [...]}}
        if isinstance(raw_data, dict) and "resultset" in raw_data and "row" in raw_data["resultset"]:
            rows = raw_data["resultset"]["row"]
            for row in rows:
                if isinstance(row, dict) and "field" in row:
                    f = row["field"]
                    if len(f) >= 5:
                        parsed_verses.append((str(f[4]).strip(), int(f[1]), int(f[2]), int(f[3])))

        # Format B: List of verse dicts
        elif isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    b_id = item.get("book") or item.get("book_id") or item.get("b")
                    ch = item.get("chapter") or item.get("c")
                    v = item.get("verse") or item.get("v")
                    txt = item.get("text") or item.get("t")

                    if isinstance(b_id, str):
                        b_id = BOOK_NAME_TO_ID.get(b_id.strip().lower(), None)

                    if b_id and ch and v and txt:
                        parsed_verses.append((str(txt).strip(), int(b_id), int(ch), int(v)))

        # Format C: Dict of books {"Genesis": {"1": {"1": "In the beginning..."}}}
        elif isinstance(raw_data, dict):
            for book_key, chapters in raw_data.items():
                b_id = BOOK_NAME_TO_ID.get(str(book_key).strip().lower(), None)
                if not b_id and str(book_key).isdigit():
                    b_id = int(book_key)

                if b_id and isinstance(chapters, dict):
                    for ch_key, verses in chapters.items():
                        if isinstance(verses, dict):
                            for v_key, txt in verses.items():
                                parsed_verses.append((str(txt).strip(), int(b_id), int(ch_key), int(v_key)))

        if not parsed_verses:
            st.error("Could not parse KJV JSON data structure. Please verify the source.")
            conn.close()
            st.stop()

        # Batch execute updates inside a single transaction
        cursor.executemany(
            "UPDATE verses SET text_en = ? WHERE book_id = ? AND chapter = ? AND verse = ?;",
            parsed_verses
        )
        conn.commit()
        updated_count = len(parsed_verses)

        progress_bar.progress(85)

        # Step 4: Verification sample (John 3:16)
        status_text.text("4/4: Verifying sample...")
        cursor.execute(
            "SELECT book_id, chapter, verse, text_ta, text_en FROM verses WHERE book_id = 43 AND chapter = 3 AND verse = 16;"
        )
        sample = cursor.fetchone()
        conn.close()

        progress_bar.progress(100)
        status_text.empty()

        st.success(f"Successfully processed and merged {updated_count:,} KJV verses!")

        if sample:
            st.markdown("### 🔍 Preview: John 3:16 (யோவான் 3:16)")
            st.write(f"**Tamil:** {sample[3]}")
            st.write(f"**English (KJV):** {sample[4]}")

        # Read back merged DB for download
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