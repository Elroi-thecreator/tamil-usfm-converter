import streamlit as st
import re
import json

st.set_page_config(page_title="Tamil USFM to JSON Converter", layout="centered")
st.title("📖 Tamil USFM to Unified JSON Converter")

def clean_and_parse_usfm(content):
    lines = content.splitlines()
    book_id = "UNKNOWN"
    book_name = ""
    chapters = {}
    current_chapter = None
    current_verse = None
    current_text = []

    def flush_verse():
        nonlocal current_text
        if current_chapter and current_verse and current_text:
            raw = "".join(current_text)
            clean = re.sub(r"\\f\s*\+.*?\s*\\f\*", "", raw)
            clean = re.sub(r"\\[a-zA-Z0-9]+(\s+)?", " ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            chapters[current_chapter][current_verse] = clean
            current_text = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("\\id "):
            book_id = line.split()[1].upper()
        elif line.startswith("\\h ") or line.startswith("\\toc1 "):
            if not book_name:
                book_name = line.split(maxsplit=1)[1]
        elif line.startswith("\\c "):
            flush_verse()
            match = re.match(r"\\c\s+(\d+)", line)
            if match:
                current_chapter = match.group(1)
                chapters[current_chapter] = {}
                current_verse = None
        elif line.startswith("\\v "):
            flush_verse()
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

    flush_verse()
    return {
        "book_code": book_id,
        "book_name": book_name,
        "chapters": chapters
    }

uploaded_files = st.file_uploader(
    "Upload .usfm / .SFM files", 
    accept_multiple_files=True, 
    type=["usfm", "sfm", "txt"]
)

if uploaded_files:
    if st.button(f"Convert {len(uploaded_files)} File(s) to Single JSON"):
        combined_bible = {}
        progress_bar = st.progress(0)

        for i, file in enumerate(uploaded_files):
            raw_text = file.read().decode("utf-8", errors="ignore")
            parsed = clean_and_parse_usfm(raw_text)
            combined_bible[parsed["book_code"]] = parsed
            progress_bar.progress((i + 1) / len(uploaded_files))

        json_bytes = json.dumps(combined_bible, ensure_ascii=False, indent=2).encode("utf-8")

        st.success("✅ Conversion complete!")
        st.download_button(
            label="⬇️ Download Combined Tamil Bible JSON",
            data=json_bytes,
            file_name="tamil_bible_combined.json",
            mime="application/json"
        )
