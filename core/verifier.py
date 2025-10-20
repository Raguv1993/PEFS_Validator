import fitz
import pandas as pd
import json
import io
from rapidfuzz import fuzz
from core.extractor import extract_text_positions


# ---------------- SETTINGS LOADER ----------------
def load_settings(config_path="config/settings.json"):
    """Load tolerance, prefix, and scaling settings from JSON file."""
    with open(config_path, "r") as f:
        return json.load(f)


# ---------------- CONTEXT BUILDER ----------------
def build_context(df, radius=250):
    """
    Build local text context for each detected text region.
    This helps compare same logical areas between drawings.
    """
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
    """
    Compare a context region from Drawing 1 against Drawing 2 contexts
    using fuzzy matching. Returns the best-matching region.
    """
    best_row, best_score = None, 0
    for _, cand in df2_ctx.iterrows():
        score = fuzz.partial_ratio(src_context, cand["context"])
        if score > best_score:
            best_row, best_score = cand, score
    if best_row is not None and best_score >= threshold:
        return best_row, best_score
    return None, best_score


# ---------------- MAIN VALIDATION LOGIC ----------------
def verify_drawings_memory(
    drawing1_bytes,
    drawing2_bytes,
    mapping_csv,
    config_path="config/settings.json",
    progress_callback=None,
):
    """
    Validate Drawing 2 against Drawing 1 using mapping.csv.
    Highlights matched/mismatched/unmapped text directly on Drawing 2.
    Returns annotated PDF bytes, summary, and debug DataFrame.
    """
    settings = load_settings(config_path)
    prefix_5ad = settings.get("scan_prefix", "5-AD")

    # Load mapping
    df_map = pd.read_csv(mapping_csv)
    map_dict = {
        str(row["Drawing1_No"]).strip().upper(): str(row["Drawing2_No"]).strip().upper()
        for _, row in df_map.iterrows()
    }

    # Extract text and positions from both PDFs
    df1 = extract_text_positions(drawing1_bytes)
    df2 = extract_text_positions(drawing2_bytes)

    # Build local text context around each tag
    df1_ctx = build_context(df1)
    df2_ctx = build_context(df2)

    # Find 5-AD numbers in Drawing 1
    df1_targets = df1_ctx[df1_ctx["text"].str.startswith(prefix_5ad, na=False)]
    total = len(df1_targets)

    # Prepare Drawing 2 for annotation
    doc2 = fitz.open(stream=drawing2_bytes, filetype="pdf")

    matched = mismatched = missing = unmapped = 0
    debug_rows = []

    for i, row in enumerate(df1_targets.itertuples(), start=1):
        tag_5ad = row.text
        expected_rhl = map_dict.get(tag_5ad)
        color = (0.53, 0.81, 0.92)  # Azure (unmapped/missing default)
        result = "Unmapped"
        found_rhl = "-"
        confidence = 0
        rect = fitz.Rect(row.x0 - 1, row.y0 - 1, row.x1 + 1, row.y1 + 1)

        if expected_rhl:
            # Find the most similar context region in Drawing 2
            best_row, score = find_best_context_region(row.context, df2_ctx)
            confidence = score
            if best_row is not None:
                region_text = best_row.context
                if expected_rhl in region_text:
                    # ✅ Matched
                    color = (0, 1, 0)
                    result = "Matched"
                    matched += 1
                    found_rhl = expected_rhl
                    rect = fitz.Rect(best_row.x0, best_row.y0, best_row.x1, best_row.y1)
                elif "RHL-" in region_text:
                    # ❌ Mismatched
                    color = (1, 0, 0)
                    result = "Mismatched"
                    mismatched += 1
                    try:
                        found_rhl = "RHL-" + region_text.split("RHL-")[1].split()[0]
                    except IndexError:
                        found_rhl = "RHL-???"
                    rect = fitz.Rect(best_row.x0, best_row.y0, best_row.x1, best_row.y1)
                else:
                    # 🔍 Missing in context
                    result = "Missing"
                    missing += 1
            else:
                result = "Missing"
                missing += 1
        else:
            unmapped += 1

        # Draw colored rectangle on Drawing 2
        page_obj = doc2.load_page(row.page - 1)
        ann = page_obj.add_rect_annot(rect)
        ann.set_colors(stroke=color, fill=color)
        ann.set_opacity(0.4)
        ann.update()

        # Debug log entry
        debug_rows.append({
            "5-AD Number": tag_5ad,
            "Expected RHL": expected_rhl or "-",
            "Found RHL": found_rhl,
            "Confidence": round(confidence, 1),
            "Result": result
        })

        # Progress bar update
        if progress_callback:
            progress_callback(i, total)

    # Save annotated PDF in memory
    output_stream = io.BytesIO()
    doc2.save(output_stream)
    doc2.close()
    output_stream.seek(0)

    # Create summary and debug table
    summary = {
        "Total Tags Found": total,
        "Matched": matched,
        "Mismatched": mismatched,
        "Missing": missing,
        "Unmapped": unmapped,
    }

    debug_df = pd.DataFrame(debug_rows)
    return output_stream, summary, debug_df
