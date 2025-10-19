It’s written for engineers — short, visual, and clear enough for anyone in your company to understand and deploy your PEFS Drawing Validator.

📘 PEFS Drawing Validator

An intelligent Drawing Number Validation Tool built using Streamlit and PyMuPDF.
It compares two CAD-generated PDF drawings using a mapping file (mapping.csv) and visually highlights differences between drawing numbers.

⚙️ Features

🧩 Smart Forward Scan – Extracts all 5-AD... tags from Drawing 1 and maps them to RHL... codes via mapping.csv.

🟩 Green → Correct mapping found at the same coordinate

🟥 Red → Mismatched RHL at the same coordinate

🩵 Azure → Missing or unmapped tag

📊 Summary Table – Displays total, matched, mismatched, and missing counts

🧠 All Processing In-Memory – No files are stored on disk

🌐 Streamlit Web Interface – Just upload and click Start Validation

| Category         | Count |
| ---------------- | ----- |
| Total Tags Found | 1245  |
| Matched (🟩)     | 1180  |
| Mismatched (🟥)  | 35    |
| Missing (🩵)     | 20    |
| Unmapped (🩵)    | 10    |
