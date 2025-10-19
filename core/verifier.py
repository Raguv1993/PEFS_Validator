import fitz
import pandas as pd
import json
import io
from .extractor import extract_text_positions

def load_settings(config_path="config/settings.json"):
    with open(config_path, "r") as f:
        return json.load(f)

def align_coordinate_system(df1, df2, settings):
    anchor_text = settings["alignment_anchor"]
    tol_align = settings["tolerance_alignment"]
    scale_corr = settings["scale_correction"]

    a1 = df1[df1["text"].str.contains(anchor_text, case=False, na=False)]
    a2 = df2[df2["text"].str.contains(anchor_text, case=False, na=False)]

    if a1.empty or a2.empty:
        print("⚠️ No common anchor text found — skipping alignment.")
        return df1

    a1, a2 = a1.iloc[0], a2.iloc[0]
    dx = a2["x0"] - a1["x0"]
    dy = a2["y0"] - a1["y0"]
    df1[["x0", "x1"]] += dx
    df1[["y0", "y1"]] += dy

    if scale_corr:
        scale_x = df2["x0"].max() / df1["x0"].max()
        scale_y = df2["y0"].max() / df1["y0"].max()
        df1["x0"] *= scale_x
        df1["x1"] *= scale_x
        df1["y0"] *= scale_y
        df1["y1"] *= scale_y

    return df1

def verify_drawings_memory(
    drawing1_bytes,
    drawing2_bytes,
    mapping_csv,
    config_path="config/settings.json",
    progress_callback=None,
):
    """Perform in-memory validation and return PDF bytes + summary."""
    settings = load_settings(config_path)
    tol = settings["tolerance_coordinate"]
    prefix = settings["scan_prefix"]

    df_map = pd.read_csv(mapping_csv)

    # ✅ Read uploads once into memory
    drawing1_data = drawing1_bytes.read()
    drawing2_data = drawing2_bytes.read()

    # ✅ Extract text from byte data
    df1 = extract_text_positions(drawing1_data)
    df2 = extract_text_positions(drawing2_data)

    # ✅ Align coordinates
    df1 = align_coordinate_system(df1, df2, settings)

    # ✅ Mapping dictionary
    map_dict = {
        str(row["Drawing1_No"]).strip().upper(): str(row["Drawing2_No"]).strip().upper()
        for _, row in df_map.iterrows()
    }

    # ✅ Open Drawing 2 once from memory
    doc2 = fitz.open("pdf", drawing2_data)

    # ✅ Begin comparison
    df1_targets = df1[df1["text"].str.match(prefix, case=False, na=False)]
    total = len(df1_targets)

    matched = mismatched = missing = unmapped = 0

    for i, (_, tag) in enumerate(df1_targets.iterrows(), start=1):
        tag_text = tag["text"].upper()
        page = tag["page"]
        x0, y0, x1, y1 = tag["x0"], tag["y0"], tag["x1"], tag["y1"]
        page_obj = doc2.load_page(page - 1)

        if tag_text not in map_dict:
            # 🩵 Unmapped
            rect = fitz.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
            ann = page_obj.add_rect_annot(rect)
            ann.set_colors(stroke=(0.53, 0.81, 0.92))
            ann.update()
            unmapped += 1
        else:
            mapped_rhl = map_dict[tag_text]
            df2_page = df2[df2["page"] == page]
            nearby = df2_page[
                (abs(df2_page["x0"] - x0) <= tol) &
                (abs(df2_page["y0"] - y0) <= tol)
            ]

            if nearby.empty:
                color = (0.53, 0.81, 0.92)
                missing += 1
            else:
                texts_here = [t.strip().upper() for t in nearby["text"]]
                if mapped_rhl in texts_here:
                    color = (0, 1, 0)
                    matched += 1
                else:
                    color = (1, 0, 0)
                    mismatched += 1

            rect = fitz.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
            ann = (
                page_obj.add_highlight_annot(rect)
                if color == (0, 1, 0)
                else page_obj.add_rect_annot(rect)
            )
            ann.set_colors(stroke=color)
            ann.update()

        if progress_callback:
            progress_callback(i, total)

    # ✅ Save to memory
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

