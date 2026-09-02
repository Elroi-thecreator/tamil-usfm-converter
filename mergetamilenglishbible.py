import streamlit as st
import sqlite3
import urllib.request
import json
import tempfile
import os

st.set_page_config(page_title="Tamil + KJV Bible Database Merger", page_icon="📖", layout="centered")

st.title("📖 Tamil + KJV Bible DB Merger")
st.write("Upload your existing `tamil_bible.db` to merge public domain King James Version (KJV) text.")

uploaded_file = st.file_uploader("Choose your tamil_bible.db file", type=["db", "sqlite", "sqlite3"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(uploaded_file.read())
        tmp_db_path = tmp.name

    st.success("File uploaded successfully!")

    if st.button("🚀 Merge KJV English Verses"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Step 1: Download verified flat KJV JSON
        status_text.text("1/4: Downloading KJV dataset...")
        progress_bar.progress(20)

        # Flat, reliable KJV dataset: list of [{"book": 1, "chapter": 1, "verse": 1, "text": "..."}, ...]
        primary_url = "https://raw.githubusercontent.com/jadenzaleski/bible-sqlite/master/KJV.json"
        fallback_url = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/KJV.json"

        raw_data = None
        for url in [primary_url, fallback_url]:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw_data = json.loads(resp.read().decode("utf-8"))
                if raw_data:
                    break
            except Exception:
                continue

        if not raw_data:
            st.error("Failed to download KJV text from public mirrors. Please check network/firewall.")
            st.stop()

        # Step 2: Open SQLite database & add text_en column
        status_text.text("2/4: Checking database schema...")
        progress_bar.progress(40)

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='verses';")
        if not cursor.fetchone():
            st.error("Table 'verses' was not found in the uploaded database.")
            conn.close()
            st.stop()

        cursor.execute("PRAGMA table_info(verses);")
        columns = [col[1] for col in cursor.fetchall()]

        if "text_en" not in columns:
            cursor.execute("ALTER TABLE verses ADD COLUMN text_en TEXT;")
            conn.commit()

        # Step 3: Universal verse extraction
        status_text.text("3/4: Parsing and populating KJV verses...")
        progress_bar.progress(60)

        parsed_verses = []

        # Parser Type 1: Direct list of dicts [{"book": 1, "chapter": 1, "verse": 1, "text": "..."}, ...]
        if isinstance(raw_data, list):
            for row in raw_data:
                if isinstance(row, dict):
                    b = row.get("book") or row.get("book_id") or row.get("b")
                    c = row.get("chapter") or row.get("c")
                    v = row.get("verse") or row.get("v")
                    t = row.get("text") or row.get("t")
                    if b and c and v and t:
                        parsed_verses.append((str(t).strip(), int(b), int(c), int(v)))

        # Parser Type 2: Scrollmapper SQL table dump format
        elif isinstance(raw_data, dict) and "resultset" in raw_data:
            rows = raw_data.get("resultset", {}).get("row", [])
            for r in rows:
                fields = r.get("field", [])
                if len(fields) >= 5:
                    parsed_verses.append((str(fields[4]).strip(), int(fields[1]), int(fields[2]), int(fields[3])))

        # Parser Type 3: Dict of books {"Genesis": [[v1, v2], ...]} or {"1": {"1": {"1": "..."}}}
        elif isinstance(raw_data, dict):
            # Check if root has a wrapper key like "verses" or "bible"
            candidate = raw_data.get("verses") or raw_data.get("bible") or raw_data
            if isinstance(candidate, list):
                for row in candidate:
                    if isinstance(row, dict):
                        b = row.get("book") or row.get("book_id")
                        c = row.get("chapter")
                        v = row.get("verse")
                        t = row.get("text")
                        if b and c and v and t:
                            parsed_verses.append((str(t).strip(), int(b), int(c), int(v)))
            elif isinstance(candidate, dict):
                for b_idx, (b_key, chs) in enumerate(candidate.items(), start=1):
                    book_id = int(b_key) if str(b_key).isdigit() else b_idx
                    if isinstance(chs, dict):
                        for c_key, v_map in chs.items():
                            if isinstance(v_map, dict):
                                for v_key, t_val in v_map.items():
                                    parsed_verses.append((str(t_val).strip(), int(book_id), int(c_key), int(v_key)))

        if not parsed_verses:
            st.error(f"Could not parse payload structure. Detected root type: {type(raw_data).__name__}")
            conn.close()
            st.stop()

        # Batch update SQLite in a single transaction
        cursor.executemany(
            "UPDATE verses SET text_en = ? WHERE book_id = ? AND chapter = ? AND verse = ?;",
            parsed_verses
        )
        conn.commit()
        progress_bar.progress(85)

        # Step 4: Verification sample
        status_text.text("4/4: Verifying sample (John 3:16)...")
        cursor.execute(
            "SELECT book_id, chapter, verse, text_ta, text_en FROM verses WHERE book_id = 43 AND chapter = 3 AND verse = 16;"
        )
        sample = cursor.fetchone()
        conn.close()

        progress_bar.progress(100)
        status_text.empty()

        st.success(f" Successfully merged {len(parsed_verses):,} KJV verses!")

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