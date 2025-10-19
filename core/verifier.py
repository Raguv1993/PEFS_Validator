import fitz
import pandas as pd
import json
import io
from rapidfuzz import fuzz
from .extractor import extract_text_positions


# ----------- Load Settings -----------
def load_settings(config_path="config/settings.json"):
    with open(config_path, "r") as f:
        return json.load(f)


# ----------- Build Context -----------
def build_context(df, radius=120):
    """Build text context window around every word."""
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
            "text": tag["text"].strip().upper(),
            "context": context_words.upper(),
            "x0": tag["x0"],
            "y0": tag["y0"],
            "x1": tag["x1"],
            "y1": tag["y1"]
        })
    return pd.DataFrame(contexts)


# ----------- Context-First Matching -----------
def find_best_context_region(src_context, df2_ctx, threshold=75):
    """Find region in Drawing 2 whose context best matches Drawing 1 region."""
    best_row, best_score = None, 0
    for _, cand in df2_ctx.iterrows():
        score = fuzz.partial_ratio(src_context, cand["context"])
        if score > best_score:
            best_row, best_score = cand, score
    if best_row is not None and best_score >= threshold:
        return best_row, best_score
    return None, best_score


# ----------- Main Validation -----------
def verify_drawings_memory(
    drawing1_bytes,
    drawing2_bytes,
    mapping_csv,
    config_path="config/settings.json",
    progress_callback=None,
):
    """Validate Drawing 2 using context-first logic."""
    settings = load_settings(config_path)
    prefix_5ad = settings.get("scan_prefix", "5-AD")

    df_map = pd.read_csv(mapping_csv)
    drawing1_data = drawing1_bytes.read()
    drawing2_data = drawing2_bytes.read()

    # Extract text data
    df1 = extract_text_positions(drawing1_data)
    df2 = extract_text_positions(drawing2_data)

    # Build contexts for both drawings
    df1_ctx = build_context(df1)
    df2_ctx = build_context(df2)

    # Build mapping dictionary
    map_dict = {
        str(r["Drawing1_No"]).strip().upper(): str(r["Drawing2_No"]).strip().upper()
        for _, r in df_map.iterrows()
    }

    # Filter only 5-AD tags from Drawing 1
    df1_targets = df1_ctx[df1_ctx["text"].str.startswith(prefix_5ad, na=False)]
    total = len(df1_targets)

    # Prepare output PDF
    doc2 = fitz.open("pdf", drawing2_data)
    matched = mismatched = missing = unmapped = 0

    for i, row in enumerate(df1_targets.itertuples(), start=1):
        tag_5ad = row.text
        expected_rhl = map_dict.get(tag_5ad)
        color = (0.53, 0.81, 0.92)  # default Azure
        rect = None

        if expected_rhl:
            # Step 1: find best-matching region by context
            best_row, score = find_best_context_region(row.context, df2_ctx)

            if best_row is not None:
                region_text = best_row.context
                rect = fitz.Rect(
                    best_row.x0 - 1, best_row.y0 - 1,
                    best_row.x1 + 1, best_row.y1 + 1
                )

                # Step 2: check if expected RHL exists inside that region text
                if expected_rhl in region_text:
                    color = (0, 1, 0)
                    matched += 1
                else:
                    color = (1, 0, 0)
                    mismatched += 1
            else:
                missing += 1
                rect = fitz.Rect(row.x0 - 1, row.y0 - 1, row.x1 + 1, row.y1 + 1)
        else:
            unmapped += 1
            rect = fitz.Rect(row.x0 - 1, row.y0 - 1, row.x1 + 1, row.y1 + 1)

        # Annotate Drawing 2
        page_obj = doc2.load_page(row.page - 1)
        ann = page_obj.add_rect_annot(rect)
        ann.set_colors(stroke=color, fill=color)
        ann.set_opacity(0.4)
        ann.update()

        if progress_callback:
            progress_callback(i, total)

    # Save in memory
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
    output_stream.seek(0)
    return output_stream, summary
