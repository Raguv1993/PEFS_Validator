import fitz
import pandas as pd
import io

def extract_text_positions(pdf_input):
    """Extract word positions and text from a PDF.
       Supports both file paths and in-memory bytes.
    """
    # Handle both cases: path or UploadedFile
    if hasattr(pdf_input, "read"):  # Streamlit uploaded file (in-memory)
        pdf_bytes = pdf_input.read()
        doc = fitz.open("pdf", pdf_bytes)
    elif isinstance(pdf_input, (bytes, bytearray)):
        doc = fitz.open("pdf", pdf_input)
    else:
        doc = fitz.open(pdf_input)  # File path on disk

    data = []
    for page_num, page in enumerate(doc, start=1):
        for x0, y0, x1, y1, word, *_ in page.get_text("words"):
            data.append({
                "page": page_num,
                "x0": round(x0, 2),
                "y0": round(y0, 2),
                "x1": round(x1, 2),
                "y1": round(y1, 2),
                "text": word.strip()
            })
    doc.close()
    return pd.DataFrame(data)
