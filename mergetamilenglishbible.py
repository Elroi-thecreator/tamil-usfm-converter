import streamlit as st
import sqlite3
import urllib.request
import json
import tempfile
import os

st.set_page_config(page_title="Tamil + KJV Bible Database Merger", page_icon="📖", layout="centered")

st.title("📖 Tamil + KJV Bible DB Merger")
st.write("Upload your existing `tamil_bible.db` to automatically merge the public-domain King James Version (KJV) text.")

uploaded_file = st.file_uploader("Choose your `tamil_bible.db` file", type=["db", "sqlite", "sqlite3"])

if uploaded_file is not None:
    # Save the uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(uploaded_file.read())
        tmp_db_path = tmp.name

    st.success("File uploaded successfully!")

    if st.button("🚀 Merge KJV English Verses"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Step 1: Download KJV Dataset
        status_text.text("1/4: Downloading KJV text from public domain archive...")
        progress_bar.progress(20)

        kjv_url = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/KJV.json"
        req = urllib.request.Request(kjv_url, headers={"User-Agent": "Mozilla/5.0"})

        try:
            with urllib.request.urlopen(req) as response:
                raw_data = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            st.error(f"Failed to download KJV text: {e}")
            st.stop()

        # Step 2: Open DB and Add Column
        status_text.text("2/4: Connecting to SQLite database & altering schema...")
        progress_bar.progress(40)

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(verses);")
        columns = [col[1] for col in cursor.fetchall()]

        if "text_en" not in columns:
            cursor.execute("ALTER TABLE verses ADD COLUMN text_en TEXT;")
            conn.commit()

        # Step 3: Populate English text
        status_text.text("3/4: Merging English verses into database...")
        progress_bar.progress(60)

        rows = raw_data.get("resultset", {}).get("row", [])
        updated_count = 0

        if rows:
            for row in rows:
                fields = row.get("field", [])
                if len(fields) >= 5:
                    book_id = int(fields[1])
                    chapter = int(fields[2])
                    verse = int(fields[3])
                    text_en = str(fields[4]).strip()

                    cursor.execute(
                        "UPDATE verses SET text_en = ? WHERE book_id = ? AND chapter = ? AND verse = ?",
                        (text_en, book_id, chapter, verse)
                    )
                    updated_count += 1
        else:
            for item in raw_data:
                b_id = item.get("book") or item.get("book_id")
                ch = item.get("chapter")
                v = item.get("verse")
                txt = item.get("text")
                if b_id and ch and v and txt:
                    cursor.execute(
                        "UPDATE verses SET text_en = ? WHERE book_id = ? AND chapter = ? AND verse = ?",
                        (txt.strip(), int(b_id), int(ch), int(v))
                    )
                    updated_count += 1

        conn.commit()
        progress_bar.progress(85)

        # Step 4: Verification sample
        status_text.text("4/4: Verifying sample verses...")
        cursor.execute(
            "SELECT book_id, chapter, verse, text_ta, text_en FROM verses WHERE book_id = 43 AND chapter = 3 AND verse = 16"
        )
        sample = cursor.fetchone()
        conn.close()

        progress_bar.progress(100)
        status_text.empty()

        st.success(f" Successfully merged {updated_count:,} KJV verses into the database!")

        if sample:
            st.markdown("###  Sample Output (John 3:16)")
            st.write(f"**Tamil:** {sample[3]}")
            st.write(f"**English (KJV):** {sample[4]}")

        # Step 5: Download the processed SQLite database
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