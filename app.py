import streamlit as st
from core.verifier import verify_drawings_memory
from pathlib import Path

# -------------------- UI SETTINGS --------------------
st.set_page_config(page_title="PEFS Drawing Validator", layout="centered")

st.title("📘 PEFS Drawing Number Validator")
st.markdown(
    "Upload **Drawing 1** and **Drawing 2**, then click **Start Validation**. "
    "The output file will be directly available for download — nothing is stored locally."
)

st.divider()

# -------------------- FILE UPLOAD SECTION --------------------
drawing1 = st.file_uploader("📤 Upload Drawing 1 (PDF)", type=["pdf"], key="draw1")
drawing2 = st.file_uploader("📤 Upload Drawing 2 (PDF)", type=["pdf"], key="draw2")

# -------------------- VALIDATION BUTTON --------------------
if drawing1 and drawing2:
    st.success("✅ Both drawings uploaded successfully.")
    start_validation = st.button("🚀 Start Validation")

    if start_validation:
        with st.spinner("Initializing validation..."):
            mapping_csv = Path("data/mapping.csv")
            if not mapping_csv.exists():
                st.error("⚠️ mapping.csv not found in the 'data/' folder.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()

                def update_progress(current, total):
                    pct = int((current / total) * 100)
                    progress_bar.progress(pct)
                    status_text.text(f"🔍 Processing tag {current}/{total} ({pct}%)")

                output_bytes, summary = verify_drawings_memory(
                    drawing1, drawing2, mapping_csv, progress_callback=update_progress
                )

                progress_bar.progress(100)
                status_text.text("✅ Validation finished!")

                # ✅ Summary table
                st.subheader("📊 Validation Summary")
                st.table(
                    {
                        "Category": [
                            "Total Tags Found",
                            "Matched (🟩)",
                            "Mismatched (🟥)",
                            "Missing (🩵)",
                            "Unmapped (🩵)",
                        ],
                        "Count": [
                            summary["Total Tags Found"],
                            summary["Matched"],
                            summary["Mismatched"],
                            summary["Missing"],
                            summary["Unmapped"],
                        ],
                    }
                )

                # ✅ Direct Download
                st.download_button(
                    label="📥 Download Verified Drawing 2",
                    data=output_bytes,
                    file_name="Drawing2_Checked.pdf",
                    mime="application/pdf",
                )
else:
    st.info("📂 Please upload both Drawing 1 and Drawing 2 to enable validation.")
