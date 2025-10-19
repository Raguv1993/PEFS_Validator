import fitz
import pandas as pd

def extract_text_positions(pdf_path):
    """Extract word positions and text from a PDF."""
    doc = fitz.open(pdf_path)
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
