import cv2
import pytesseract
import pandas as pd
import numpy as np
import io
from pdf2image import convert_from_bytes
import fitz
from rapidfuzz import fuzz
import json


# ---------------- SETTINGS ----------------
def load_settings(config_path="config/settings.json"):
    with open(config_path, "r") as f:
        return json.load(f)


# ---------------- OCR TEXT EXTRACTOR ----------------
def extract_text_positions_opencv(pdf_bytes, dpi=300):
    """Convert each PDF page → image → OCR → return DataFrame of text boxes."""
    pages = convert_from_bytes(pdf_bytes, dpi=dpi)
    rows = []
    for page_no, pil_img in enumerate(pages, start=1):
        img = np.array(pil_img.convert("RGB"))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.bilateralFilter(gray, 5, 75, 75)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        data = pytesseract.image_to_data(
            th, lang="eng+deu", output_type=pytesseract.Output.DATAFRAME, config="--psm 6"
        ).dropna(subset=["text"])
        for _, r in data.iterrows():
            txt = str(r["text"]).strip()
            if not txt:
                continue
            x, y, w, h = int(r["left"]), int(r["top"]), int(r["width"]), int(r["height"])
            rows.append({"page": page_no, "x0": x, "y0": y, "x1": x + w, "y1": y + h, "text": txt})
    return pd.DataFrame(rows)


# ---------------- CONTEXT BUILDER ----------------
def build_context(df, radius=250):
    """Group neighbouring words to create context windows."""
    contexts = []
    for _, tag in df.iterrows():
        same_page = df[df["page"] == tag["page"]]
        neighbors = same_page[
            (abs(same_page["x0"] - tag["x0"]) <= radius)
            & (abs(same_page["y0"] - tag["y0"]) <= radius)
        ]
        context_words = " ".join(neighbors["text"].tolist())
        contexts.append({
            "page": tag["page"],
            "text": tag["text"].upper(),
            "context": context_words.upper(),
            "x0": tag["x0"],
            "y0": tag["y0"],
            "x1": tag["x1"],
            "y1": tag["y1"]
        })
    return pd.DataFrame(contexts)


# ---------------- CONTEXT MATCHER ----------------
def find_best_context_region(src_context, df2_ctx, threshold=75):
    """Find the most similar context region in Drawing 2."""
    best_row, best_score = None, 0
    for _, cand in df2_ctx.iterrows():
        score = fuzz.partial_ratio(src_context, cand["context"])
        if score > best_score:
            best_row, best_score = cand, score
    if best_row is not None and best_score >= threshold:
        return best_row, best_score
    return None, best_score


# ---------------- MAIN VALIDATOR ----------------
def verify_drawings_memory(
    drawing1_bytes,
    drawing2_bytes,
    mapping_csv,
    config_path="config/settings.json",
    progress_callback=None,
):
    """Validate Drawing 2 against Drawing 1 using pure OpenCV + OCR."""
    settings = load_settings(config_path)
    prefix_5ad = settings.get("scan_prefix", "5-AD")

    df_map = pd.read_csv(mapping_csv)
    drawing1_data = drawing1_bytes.read()
    drawing2_data = drawing2_bytes.read()

    # ---- OCR extraction ----
    df1 = extract_text_positions_opencv(drawing1_data)
    df2 = extract_text_positions_opencv(drawing2_data)

    # ---- Build contexts ----
    df1_ctx = build_context(df1)
    df2_ctx = build_context(df2)

    # ---- Mapping dictionary ----
    map_dict = {
        str(r["Drawing1_No"]).strip().upper(): str(r["Drawing2_No"]).strip().upper()
        for _, r in df_map.iterrows()
    }

    # ---- Targets (5-AD only) ----
    df1_targets = df1_ctx[df1_ctx["text"].str.startswith(prefix_5ad, na=False)]
    total = len(df1_targets)

    # ---- Prepare PDF for highlighting ----
    doc2 = fitz.open("pdf", drawing2_data)
    matched = mismatched = missing = unmapped = 0
    debug_rows = []

    for i, row in enumerate(df1_targets.itertuples(), start=1):
        tag_5ad = row.text
        expected_rhl = map_dict.get(tag_5ad)
        color = (0.53, 0.81, 0.92)
        result = "Unmapped"
        found_rhl = "-"
        confidence = 0
        rect = fitz.Rect(row.x0 - 1, row.y0 - 1, row.x1 + 1, row.y1 + 1)

        if expected_rhl:
            best_row, score = find_best_context_region(row.context, df2_ctx)
            confidence = score
            if best_row is not None:
                region_text = best_row.context
                df2_rhl = df2[
                    (df2["page"] == best_row.page)
                    & (df2["text"].str.upper() == expected_rhl)
                ]
                if not df2_rhl.empty:
                    x0, y0, x1, y1 = (
                        df2_rhl.iloc[0]["x0"],
                        df2_rhl.iloc[0]["y0"],
                        df2_rhl.iloc[0]["x1"],
                        df2_rhl.iloc[0]["y1"],
                    )
                    rect = fitz.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
                    color = (0, 1, 0)
                    result = "Matched"
                    matched += 1
                    found_rhl = expected_rhl
                elif any(w.startswith("RHL-") for w in region_text.split()):
                    color = (1, 0, 0)
                    result = "Mismatched"
                    mismatched += 1
                    found_rhl = next((w for w in region_text.split() if w.startswith("RHL-")), "-")
                    rect = fitz.Rect(best_row.x0 - 1, best_row.y0 - 1,
                                     best_row.x1 + 1, best_row.y1 + 1)
                else:
                    missing += 1
                    result = "Missing"
                    rect = fitz.Rect(best_row.x0 - 1, best_row.y0 - 1,
                                     best_row.x1 + 1, best_row.y1 + 1)
            else:
                missing += 1
                result = "Missing"
        else:
            unmapped += 1
            result = "Unmapped"

        page_obj = doc2.load_page(row.page - 1)
        ann = page_obj.add_rect_annot(rect)
        ann.set_colors(stroke=color, fill=color)
        ann.set_opacity(0.4)
        ann.update()

        debug_rows.append({
            "5-AD Number": tag_5ad,
            "Expected RHL": expected_rhl or "-",
            "Found RHL": found_rhl,
            "Confidence": round(confidence, 1),
            "Result": result
        })

        if progress_callback:
            progress_callback(i, total)

    # ---- Save annotated PDF ----
    output_stream = io.BytesIO()
    doc2.save(output_stream)
    doc2.close()

    summary = {
        "Total Tags Found": total,
        "Matched": matched,
        "Mismatched": mismatched,
        "Missing": missing,
        "Unmapped": unmapped,
    }
    debug_df = pd.DataFrame(debug_rows)
    output_stream.seek(0)
    return output_stream, summary, debug_df
