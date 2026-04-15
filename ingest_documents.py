from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import sqlite3
import os

DOC_FOLDER = "documents"

model = SentenceTransformer("all-MiniLM-L6-v2")

conn = sqlite3.connect("knowledge.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS documents(
    id INTEGER PRIMARY KEY,
    filename TEXT,
    content TEXT,
    embedding BLOB
)
""")

def chunk_text(text, size=400):
    words = text.split()
    return [
        " ".join(words[i:i+size])
        for i in range(0, len(words), size)
    ]

for file in os.listdir(DOC_FOLDER):

    if not file.endswith(".pdf"):
        continue

    print("Reading:", file)

    reader = PdfReader(os.path.join(DOC_FOLDER, file))

    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    chunks = chunk_text(text)

    for chunk in chunks:
        emb = model.encode(chunk).astype("float32").tobytes()

        cur.execute(
            "INSERT INTO documents(filename, content, embedding) VALUES(?,?,?)",
            (file, chunk, emb)
        )

conn.commit()
conn.close()

print("Knowledge base created.")