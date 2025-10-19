import fitz
import pandas as pd
import json
import io
from rapidfuzz import fuzz
from .extractor import extract_text_positions


# ---------------- SETTINGS LOADER ----------------
def load_settings(config_path="config/settings.json"):
    with open(config_path, "r") as f:
        return json.load(f)


# ---------------- ALIGN COORDINATES (IF POSSIBLE) ----------------
def align_coordinate_system(df1, df2, settings):
    """Try aligning by anchor text if both CAD systems are similar."""
    anchor_text = settings["alignment_anchor"]
    tol_align = settings["tolerance_alignment"]
    scale_corr = settings["scale_correction"]

    a1 = df1[df1["text"].str.contains(anchor_text, case=False, na=False)]
    a2 = df2[df2["text"].str.contains(anchor_text, case=False, na=False)]

    if a1.empty or a2.empty:
        print("⚠️ No common anchor text found — skipping alignment.")
        return df1, False

    a1, a2 = a1.iloc[0], a2.iloc[0]
    dx = a2["x0"] - a1["x0"]
    dy = a2["y0"] - a1["y0"]
    df1[["x0", "x1"]] += dx
    df1[["y0", "y1"]] += dy

    if scale_corr:
        scale_x = df2["x0"].max() / max(df1["x0"].max(), 1)
        scale_y = df2["y0"].max() / max(df1["y0"].max(), 1)
        df1["x0"] *= scale_x
        df1["x1"] *= scale_x
        df1["y0"] *= scale_y
        df1["y1"] *= scale_y

    return df1, True


# ---------------- SMART CONTEXT BUILDER ----------------
def build_context(df, target_prefix, radius=120):
    """Build text context windows around each target tag."""
    contexts = []
    for _, tag in df[df["text"].str.startswith(target_prefix, na=False)].iterrows():
        same_page = df[df["page"] == tag["page"]]
        neighbors = same_page[
            (abs(same_page["x0"] - tag["x0"]) <= radius)
            & (abs(same_page["y0"] - tag["y0"]) <= radius)
        ]
        context_words = " ".join(neighbors["text"].tolist())
        contexts.append({"page": tag["page"], "text": tag["text"], "context": context_words})
    return pd.DataFrame(contexts)


# ---------------- SMART MATCHING ----------------
def find_best_context_match(tag_row, df2_ctx, threshold=75):
    """Find most similar region in Drawing 2 using fuzzy context matching."""
    best_row, best_score = None, 0
    for _, cand in df2_ctx.iterrows():
        if cand["page"] != tag_row["page"]:
            continue
        score = fuzz.partial_ratio(tag_row["context"], cand["context"])
        if score > best_score:
            best_row, best_score = cand, score
    if best_score >= threshold:
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
    """Perform validation with coordinate + smart context fallback."""
    settings = load_settings(config_path)
    tol = settings["tolerance_coordinate"]
    prefix = settings["scan_prefix"]

    df_map = pd.read_csv(mapping_csv)

    # Read uploads once into memory
    drawing1_data = drawing1_bytes.read()
    drawing2_data = drawing2_bytes.read()

    # Extract text data
    df1 = extract_text_positions(drawing1_data)
    df2 = extract_text_positions(drawing2_data)

    # Try coordinate alignment
    df1, aligned = align_coordinate_system(df1, df2, settings)

    # Mapping dict
    map_dict = {
        str(row["Drawing1_No"]).strip().upper(): str(row["Drawing2_No"]).strip().upper()
        for _, row in df_map.iterrows()
    }

    # Open Drawing 2 for annotation
    doc2 = fitz.open("pdf", drawing2_data)

    # Tag scan
    df1_targets = df1[df1["text"].str.match(prefix, case=False, na=False)]
    total = len(df1_targets)
    print(f"🔍 Found {total} tags starting with {prefix}")

    matched = mismatched = missing = unmapped = 0

    # Pre-build contexts for smart fallback
    df1_ctx = build_context(df1, prefix)
    df2_ctx = build_context(df2, "RHL")

    # --- MAIN VALIDATION LOOP ---
    for i, (_, tag) in enumerate(df1_targets.iterrows(), start=1):
        tag_text = tag["text"].upper()
        page = tag["page"]
        x0, y0, x1, y1 = tag["x0"], tag["y0"], tag["x1"], tag["y1"]
        page_obj = doc2.load_page(page - 1)

        # Default color (unmapped)
        color = (0.53, 0.81, 0.92)

        # --- CASE 1: Unmapped ---
        if tag_text not in map_dict:
            unmapped += 1

        else:
            mapped_rhl = map_dict[tag_text]
            df2_page = df2[df2["page"] == page]
            nearby = df2_page[
                (abs(df2_page["x0"] - x0) <= tol)
                & (abs(df2_page["y0"] - y0) <= tol)
            ]

            # --- CASE 2: Coordinate-based (if aligned) ---
            if aligned and not nearby.empty:
                texts_here = [t.strip().upper() for t in nearby["text"]]
                if mapped_rhl in texts_here:
                    color = (0, 1, 0)
                    matched += 1
                else:
                    color = (1, 0, 0)
                    mismatched += 1

            # --- CASE 3: Fallback to Context Matching ---
            else:
                tag_ctx_row = df1_ctx[df1_ctx["text"].str.upper() == tag_text]
                if not tag_ctx_row.empty:
                    best_row, score = find_best_context_match(tag_ctx_row.iloc[0], df2_ctx)
                    if best_row is not None:
                        found_rhl = best_row["text"].upper()
                        if found_rhl == mapped_rhl:
                            color = (0, 1, 0)
                            matched += 1
                        else:
                            color = (1, 0, 0)
                            mismatched += 1
                    else:
                        missing += 1
                else:
                    missing += 1

        # --- ANNOTATION ---
        rect = fitz.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
        ann = page_obj.add_rect_annot(rect)
        ann.set_colors(stroke=color, fill=color)
        ann.set_opacity(0.4)
        ann.update()

        if progress_callback:
            progress_callback(i, total)

    # Save output in memory
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
