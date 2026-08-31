import streamlit as st
import json
import sqlite3
import tempfile
import os
import re

st.set_page_config(page_title="Tamil Bible to SQLite Converter", layout="centered")
st.title("📖 Tamil Bible to SQLite (.db) Converter")

CANON_ORDER = [
    ("GEN", "ஆதியாகமம்", "Genesis", "OT"),
    ("EXO", "யாத்திராகமம்", "Exodus", "OT"),
    ("LEV", "லேவியராகமம்", "Leviticus", "OT"),
    ("NUM", "எண்ணாகமம்", "Numbers", "OT"),
    ("DEU", "உபாகமம்", "Deuteronomy", "OT"),
    ("JOS", "யோசுவா", "Joshua", "OT"),
    ("JDG", "நியாயாதிபதிகள்", "Judges", "OT"),
    ("RUT", "ரூத்", "Ruth", "OT"),
    ("1SA", "1 சாமுவேல்", "1 Samuel", "OT"),
    ("2SA", "2 சாமுவேல்", "2 Samuel", "OT"),
    ("1KI", "1 இராஜாக்கள்", "1 Kings", "OT"),
    ("2KI", "2 இராஜாக்கள்", "2 Kings", "OT"),
    ("1CH", "1 நாளாகமம்", "1 Chronicles", "OT"),
    ("2CH", "2 நாளாகமம்", "2 Chronicles", "OT"),
    ("EZR", "எஸ்றா", "Ezra", "OT"),
    ("NEH", "நெகேமியா", "Nehemiah", "OT"),
    ("EST", "எஸ்தர்", "Esther", "OT"),
    ("JOB", "யோபு", "Job", "OT"),
    ("PSA", "சங்கீதம்", "Psalms", "OT"),
    ("PRO", "நீதிமொழிகள்", "Proverbs", "OT"),
    ("ECC", "பிரசங்கி", "Ecclesiastes", "OT"),
    ("SNG", "உன்னதப்பாட்டு", "Song of Solomon", "OT"),
    ("ISA", "ஏசாயா", "Isaiah", "OT"),
    ("JER", "எரேமியா", "Jeremiah", "OT"),
    ("LAM", "புலம்பல்", "Lamentations", "OT"),
    ("EZK", "எசேக்கியேல்", "Ezekiel", "OT"),
    ("DAN", "தானியேல்", "Daniel", "OT"),
    ("HOS", "ஓசியா", "Hosea", "OT"),
    ("JOL", "யோவேல்", "Joel", "OT"),
    ("AMO", "ஆமோஸ்", "Amos", "OT"),
    ("OBA", "ஒபதியா", "Obadiah", "OT"),
    ("JON", "யோனா", "Jonah", "OT"),
    ("MIC", "மீகா", "Micah", "OT"),
    ("NAM", "நாகூம்", "Nahum", "OT"),
    ("HAB", "அபகூக்", "Habakkuk", "OT"),
    ("ZEP", "செப்பனியா", "Zephaniah", "OT"),
    ("HAG", "ஆகாய்", "Haggai", "OT"),
    ("ZEC", "சகரியா", "Zechariah", "OT"),
    ("MAL", "மல்கியா", "Malachi", "OT"),
    ("MAT", "மத்தேயு", "Matthew", "NT"),
    ("MRK", "மாற்கு", "Mark", "NT"),
    ("LUK", "லூக்கா", "Luke", "NT"),
    ("JHN", "யோவான்", "John", "NT"),
    ("ACT", "அப்போஸ்தலர்", "Acts", "NT"),
    ("ROM", "ரோமர்", "Romans", "NT"),
    ("1CO", "1 கொரிந்தியர்", "1 Corinthians", "NT"),
    ("2CO", "2 கொரிந்தியர்", "2 Corinthians", "NT"),
    ("GAL", "கலாத்தியர்", "Galatians", "NT"),
    ("EPH", "எபேசியர்", "Ephesians", "NT"),
    ("PHP", "பிலிப்பியர்", "Philippians", "NT"),
    ("COL", "கொலோசெயர்", "Colossians", "NT"),
    ("1TH", "1 தெசலோனிக்கேயர்", "1 Thessalonians", "NT"),
    ("2TH", "2 தெசலோனிக்கேயர்", "2 Thessalonians", "NT"),
    ("1TI", "1 தீமோத்தேயு", "1 Timothy", "NT"),
    ("2TI", "2 தீமோத்தேயு", "2 Timothy", "NT"),
    ("TIT", "தீத்து", "Titus", "NT"),
    ("PHM", "பிலேமோன்", "Philemon", "NT"),
    ("HEB", "எபிரெயர்", "Hebrews", "NT"),
    ("JAS", "யாக்கோபு", "James", "NT"),
    ("1PE", "1 பேதுரு", "1 Peter", "NT"),
    ("2PE", "2 பேதுரு", "2 Peter", "NT"),
    ("1JN", "1 யோவான்", "1 John", "NT"),
    ("2JN", "2 யோவான்", "2 John", "NT"),
    ("3JN", "3 யோவான்", "3 John", "NT"),
    ("JUD", "யூதா", "Jude", "NT"),
    ("REV", "வெளிப்படுத்தின விசேஷம்", "Revelation", "NT")
]

# Canonical lookup dictionaries
NAME_TO_CANON = {}
for idx, (code, ta_name, en_name, test) in enumerate(CANON_ORDER):
    info = (idx + 1, code, ta_name, test)
    NAME_TO_CANON[code.upper()] = info
    NAME_TO_CANON[en_name.lower().replace(" ", "")] = info
    NAME_TO_CANON[ta_name.strip().replace(" ", "")] = info

def clean_text(raw_text):
    """Strips USFM remnants, extra spaces, and special artifacts."""
    clean = re.sub(r"\\f\s*\+.*?\s*\\f\*", "", raw_text)
    clean = re.sub(r"\\x\s*\+.*?\s*\\x\*", "", clean)
    clean = re.sub(r"\\[a-zA-Z0-9]+(\s+)?", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()

def match_canonical_book(book_key, en_name="", ta_name=""):
    """Finds canonical ID by matching code, English name, or Tamil name."""
    clean_k = str(book_key).strip().upper()[:3]
    if clean_k in NAME_TO_CANON:
        return NAME_TO_CANON[clean_k]
    
    clean_en = str(en_name).strip().lower().replace(" ", "")
    if clean_en in NAME_TO_CANON:
        return NAME_TO_CANON[clean_en]
    
    clean_ta = str(ta_name).strip().replace(" ", "")
    if clean_ta in NAME_TO_CANON:
        return NAME_TO_CANON[clean_ta]
    
    return None

def normalize_bible_payload(json_objects):
    """
    Normalizes both format styles:
    1. New Format: {"book": {"english": "...", "tamil": "..."}, "chapters": [{"chapter": "1", "verses": [...]}]}
    2. Old Format: {"GEN": {"chapters": {"1": {"1": "text"}}}}
    """
    normalized = []

    for item in json_objects:
        # Check if item is a list of books or single book
        if isinstance(item, list):
            items_to_process = item
        elif isinstance(item, dict) and "book" in item and "chapters" in item:
            items_to_process = [item]
        elif isinstance(item, dict):
            # Key-based multi-book dictionary
            for b_code, b_content in item.items():
                canon_info = match_canonical_book(b_code)
                if not canon_info:
                    continue
                book_id = canon_info[0]
                chapters_dict = b_content.get("chapters", {})
                for ch_str, v_dict in chapters_dict.items():
                    try:
                        ch_num = int(ch_str)
                        for v_str, text_val in v_dict.items():
                            v_num = int(v_str)
                            txt = clean_text(str(text_val))
                            if txt:
                                normalized.append((book_id, ch_num, v_num, txt))
                    except Exception:
                        continue
            continue
        else:
            continue

        # Processing New Format List items
        for book_obj in items_to_process:
            if not isinstance(book_obj, dict):
                continue
            
            book_meta = book_obj.get("book", {})
            en_name = book_meta.get("english", "") if isinstance(book_meta, dict) else ""
            ta_name = book_meta.get("tamil", "") if isinstance(book_meta, dict) else ""
            
            canon_info = match_canonical_book("", en_name=en_name, ta_name=ta_name)
            if not canon_info:
                continue
            
            book_id = canon_info[0]
            chapters_list = book_obj.get("chapters", [])

            for ch_entry in chapters_list:
                try:
                    ch_num = int(ch_entry.get("chapter", 0))
                    verses_list = ch_entry.get("verses", [])
                    for v_entry in verses_list:
                        v_num = int(v_entry.get("verse", 0))
                        txt = clean_text(str(v_entry.get("text", "")))
                        if txt:
                            normalized.append((book_id, ch_num, v_num, txt))
                except Exception:
                    continue

    return normalized

def build_sqlite_db(verse_tuples, output_path):
    conn = sqlite3.connect(output_path)
    cur = conn.cursor()

    cur.execute("PRAGMA page_size = 4096;")
    cur.execute("PRAGMA auto_vacuum = FULL;")
    cur.execute("PRAGMA synchronous = OFF;")
    cur.execute("PRAGMA journal_mode = MEMORY;")

    cur.execute("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name_ta TEXT NOT NULL,
            testament TEXT NOT NULL
        );
    """)

    cur.execute("""
        CREATE TABLE verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text_ta TEXT NOT NULL,
            FOREIGN KEY(book_id) REFERENCES books(id)
        );
    """)

    # Populate canonical order
    for idx, (code, ta_name, en_name, test) in enumerate(CANON_ORDER):
        cur.execute("INSERT INTO books VALUES (?, ?, ?, ?)", (idx + 1, code, ta_name, test))

    # Bulk insert verses
    cur.executemany(
        "INSERT INTO verses (book_id, chapter, verse, text_ta) VALUES (?, ?, ?, ?)",
        verse_tuples
    )
    conn.commit()

    cur.execute("CREATE INDEX idx_book_chapter ON verses(book_id, chapter);")
    conn.commit()

    cur.execute("VACUUM;")
    conn.commit()
    conn.close()

    return len(verse_tuples)

# Streamlit UI
st.subheader("Convert Bible JSON files to Optimized SQLite (`tamil_bible.db`)")
uploaded_files = st.file_uploader(
    "Upload JSON file(s) (Single file or multiple book files supported)",
    type=["json"],
    accept_multiple_files=True
)

if uploaded_files and st.button("Generate tamil_bible.db"):
    with st.spinner("Processing Bible files and compiling SQLite database..."):
        json_payloads = []
        for file in uploaded_files:
            try:
                data = json.load(file)
                json_payloads.append(data)
            except Exception as e:
                st.error(f"Failed to parse {file.name}: {e}")

        all_verses = normalize_bible_payload(json_payloads)

        if not all_verses:
            st.error("No valid verses could be parsed from the uploaded JSON file(s).")
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp_path = tmp.name

            total = build_sqlite_db(all_verses, tmp_path)

            with open(tmp_path, "rb") as f:
                db_bytes = f.read()
            os.remove(tmp_path)

            size_mb = len(db_bytes) / (1024 * 1024)
            st.success(f"✅ Generated compact SQLite DB ({size_mb:.2f} MB) with {total:,} verses!")
            st.download_button(
                label="⬇️ Download Optimized tamil_bible.db",
                data=db_bytes,
                file_name="tamil_bible.db",
                mime="application/x-sqlite3"
            )