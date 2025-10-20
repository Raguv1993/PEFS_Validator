import fitz
import pandas as pd


def extract_text_positions(pdf_bytes):
    """
    Extracts all visible text and its coordinates from a PDF file (in memory).
    Uses PyMuPDF, which is reliable for engineering drawings with embedded text.

    Parameters
    ----------
    pdf_bytes : bytes
        Raw PDF bytes loaded from an uploaded file (Streamlit or local).

    Returns
    -------
    pd.DataFrame
        Columns: ['page', 'x0', 'y0', 'x1', 'y1', 'text']
        - page : Page number (1-based)
        - x0,y0,x1,y1 : Bounding box of text (in points)
        - text : Actual extracted text string
    """

    # Open PDF directly from memory (no need to save to disk)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    records = []

    for page_no, page in enumerate(doc, start=1):
        # Get all word-level text boxes
        # Each entry: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        words = page.get_text("words")

        for w in words:
            x0, y0, x1, y1, text, *_ = w
            text = text.strip()
            if not text:
                continue

            records.append({
                "page": page_no,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "text": text
            })

    doc.close()
    return pd.DataFrame(records)
