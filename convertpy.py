import streamlit as st
import json
import sqlite3
import tempfile
import os
import re

st.set_page_config(page_title="Tamil Bible to SQLite Converter", layout="centered")
st.title("📖 Tamil Bible to SQLite (.db) Converter")

CANON_ORDER = [
    ("GEN", "ஆதியாகமம்", "OT"), ("EXO", "யாத்திராகமம்", "OT"), ("LEV", "லேவியராகமம்", "OT"),
    ("NUM", "எண்ணாகமம்", "OT"), ("DEU", "உபாகமம்", "OT"), ("JOS", "யோசுவா", "OT"),
    ("JDG", "நியாயாதிபதிகள்", "OT"), ("RUT", "ரூத்", "OT"), ("1SA", "1 சாமுவேல்", "OT"),
    ("2SA", "2 சாமுவேல்", "OT"), ("1KI", "1 இராஜாக்கள்", "OT"), ("2KI", "2 இராஜாக்கள்", "OT"),
    ("1CH", "1 நாளாகமம்", "OT"), ("2CH", "2 நாளாகமம்", "OT"), ("EZR", "எஸ்றா", "OT"),
    ("NEH", "நெகேமியா", "OT"), ("EST", "எஸ்தர்", "OT"), ("JOB", "யோபு", "OT"),
    ("PSA", "சங்கீதம்", "OT"), ("PRO", "நீதிமொழிகள்", "OT"), ("ECC", "பிரசங்கி", "OT"),
    ("SNG", "உன்னதப்பாட்டு", "OT"), ("ISA", "ஏசாயா", "OT"), ("JER", "எரேமியா", "OT"),
    ("LAM", "புலம்பல்", "OT"), ("EZK", "எசேக்கியேல்", "OT"), ("DAN", "தானியேல்", "OT"),
    ("HOS", "ஓசியா", "OT"), ("JOL", "யோவேல்", "OT"), ("AMO", "ஆமோஸ்", "OT"),
    ("OBA", "ஒபதியா", "OT"), ("JON", "யோனா", "OT"), ("MIC", "மீகா", "OT"),
    ("NAM", "நாகூம்", "OT"), ("HAB", "அபகூக்", "OT"), ("ZEP", "செப்பனியா", "OT"),
    ("HAG", "ஆகாய்", "OT"), ("ZEC", "சகரியா", "OT"), ("MAL", "மல்கியா", "OT"),
    ("MAT", "மத்தேயு", "NT"), ("MRK", "மாற்கு", "NT"), ("LUK", "லூக்கா", "NT"),
    ("JHN", "யோவான்", "NT"), ("ACT", "அப்போஸ்தலர்", "NT"), ("ROM", "ரோமர்", "NT"),
    ("1CO", "1 கொரிந்தியர்", "NT"), ("2CO", "2 கொரிந்தியர்", "NT"), ("GAL", "கலாத்தியர்", "NT"),
    ("EPH", "எபேசியர்", "NT"), ("PHP", "பிலிப்பியர்", "NT"), ("COL", "கொலோசெயர்", "NT"),
    ("1TH", "1 தெசலோனிக்கேயர்", "NT"), ("2TH", "2 தெசலோனிக்கேயர்", "NT"),
    ("1TI", "1 தீமோத்தேயு", "NT"), ("2TI", "2 தீமோத்தேயு", "NT"), ("TIT", "தீத்து", "NT"),
    ("PHM", "பிலேமோன்", "NT"), ("HEB", "எபிரெயர்", "NT"), ("JAS", "யாக்கோபு", "NT"),
    ("1PE", "1 பேதுரு", "NT"), ("2PE", "2 பேதுரு", "NT"), ("1JN", "1 யோவான்", "NT"),
    ("2JN", "2 யோவான்", "NT"), ("3JN", "3 யோவான்", "NT"), ("JUD", "யூதா", "NT"),
    ("REV", "வெளிப்படுத்தின விசேஷம்", "NT")
]

CODE_TO_CANON = {code: (idx + 1, name, test) for idx, (code, name, test) in enumerate(CANON_ORDER)}

def clean_usfm_text(raw_text):
    clean = re.sub(r"\\f\s*\+.*?\s*\\f\*", "", raw_text)
    clean = re.sub(r"\\[a-zA-Z0-9]+(\s+)?", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()

def parse_single_usfm(raw_text):
    """Parses raw USFM string into a structured dictionary without scope issues."""
    lines = raw_text.splitlines()
    book_id = "UNKNOWN"
    book_name = ""
    chapters = {}
    current_chapter = None
    current_verse = None
    current_text = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("\\id "):
            book_id = line.split()[1].upper()[:3]
        elif line.startswith("\\h ") or line.startswith("\\toc1 "):
            if not book_name:
                book_name = line.split(maxsplit=1)[1]
        elif line.startswith("\\c "):
            # Save previous verse
            if current_chapter and current_verse and current_text:
                chapters[current_chapter][current_verse] = clean_usfm_text("".join(current_text))
                current_text = []

            match = re.match(r"\\c\s+(\d+)", line)
            if match:
                current_chapter = match.group(1)
                chapters[current_chapter] = {}
                current_verse = None
        elif line.startswith("\\v "):
            # Save previous verse
            if current_chapter and current_verse and current_text:
                chapters[current_chapter][current_verse] = clean_usfm_text("".join(current_text))
                current_text = []

            match = re.match(r"\\v\s+(\d+)\s*(.*)", line)
            if match:
                current_verse = match.group(1)
                if match.group(2):
                    current_text = [match.group(2)]
        elif current_verse is not None and not line.startswith("\\s") and not line.startswith("\\is"):
            if line.startswith("\\q") or line.startswith("\\p"):
                content_part = re.sub(r"^\\[a-zA-Z0-9]+\s*", "", line)
                if content_part:
                    current_text.append(" " + content_part)
            elif not line.startswith("\\"):
                current_text.append(" " + line)

    # Save last verse in file
    if current_chapter and current_verse and current_text:
        chapters[current_chapter][current_verse] = clean_usfm_text("".join(current_text))

    return book_id, {"book_name": book_name, "chapters": chapters}

def build_sqlite_from_dict(bible_dict, output_path):
    conn = sqlite3.connect(output_path)
    cur = conn.cursor()

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

    for code, name, testament in CANON_ORDER:
        b_id = CODE_TO_CANON[code][0]
        cur.execute("INSERT INTO books VALUES (?, ?, ?, ?)", (b_id, code, name, testament))

    total_verses = 0
    for code, book_info in bible_dict.items():
        norm_code = code.upper()[:3]
        if norm_code not in CODE_TO_CANON:
            continue

        book_id = CODE_TO_CANON[norm_code][0]
        chapters = book_info.get("chapters", {})

        for ch_num_str in sorted(chapters.keys(), key=lambda x: int(x)):
            ch_num = int(ch_num_str)
            verses_dict = chapters[ch_num_str]

            for v_num_str in sorted(verses_dict.keys(), key=lambda x: int(x)):
                v_num = int(v_num_str)
                text = str(verses_dict[v_num_str]).strip()
                if text:
                    cur.execute(
                        "INSERT INTO verses (book_id, chapter, verse, text_ta) VALUES (?, ?, ?, ?)",
                        (book_id, ch_num, v_num, text)
                    )
                    total_verses += 1

    cur.execute("CREATE INDEX idx_book_chapter ON verses(book_id, chapter);")
    cur.execute("CREATE VIRTUAL TABLE verses_fts USING fts5(text_ta, content='verses', content_rowid='id');")
    cur.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild');")
    cur.execute("VACUUM;")

    conn.commit()
    conn.close()
    return total_verses

# UI Setup
tab1, tab2 = st.tabs(["Upload JSON File", "Upload USFM Files"])

with tab1:
    st.subheader("Convert `tamil_bible_combined.json` to SQLite")
    json_file = st.file_uploader("Upload your JSON file", type=["json"], key="json_uploader")

    if json_file and st.button("Generate tamil_bible.db from JSON"):
        with st.spinner("Processing JSON and generating SQLite database..."):
            bible_data = json.load(json_file)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp_path = tmp.name

            total = build_sqlite_from_dict(bible_data, tmp_path)

            with open(tmp_path, "rb") as f:
                db_bytes = f.read()
            os.remove(tmp_path)

            st.success(f"✅ Generated SQLite DB with {total:,} verses!")
            st.download_button(
                label="⬇️ Download tamil_bible.db",
                data=db_bytes,
                file_name="tamil_bible.db",
                mime="application/x-sqlite3"
            )

with tab2:
    st.subheader("Convert raw USFM files directly to SQLite")
    usfm_files = st.file_uploader(
        "Upload all .usfm / .SFM files", 
        accept_multiple_files=True, 
        type=["usfm", "sfm", "txt"], 
        key="usfm_uploader"
    )

    if usfm_files and st.button("Generate tamil_bible.db from USFM"):
        with st.spinner("Parsing USFM files..."):
            intermediate_dict = {}
            for file in usfm_files:
                raw_text = file.read().decode("utf-8", errors="ignore")
                b_code, b_data = parse_single_usfm(raw_text)
                intermediate_dict[b_code] = b_data

            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp_path = tmp.name

            total = build_sqlite_from_dict(intermediate_dict, tmp_path)

            with open(tmp_path, "rb") as f:
                db_bytes = f.read()
            os.remove(tmp_path)

            st.success(f"✅ Generated SQLite DB with {total:,} verses!")
            st.download_button(
                label="⬇️ Download tamil_bible.db",
                data=db_bytes,
                file_name="tamil_bible.db",
                mime="application/x-sqlite3"
            )