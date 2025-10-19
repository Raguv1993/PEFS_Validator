import streamlit as st
from core.verifier import verify_drawings_memory
from pathlib import Path
import io

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="PEFS Drawing Validator", layout="wide")

st.title("📘 PEFS Smart Drawing Validator (Context-Aware)")
st.markdown(
    """
This tool validates PEFS drawing numbers between two drawings from **different CAD systems** (e.g., MicroStation → AVEVA P&ID).

**Workflow:**
1. Scans Drawing 1 for all tags starting with `5-AD…`  
2. Retrieves mapped `RHL-…` from mapping.csv  
3. Searches Drawing 2 by *text context similarity*, not coordinates  
4. Highlights validation results in Drawing 2:
   - 🟩 **Green** = Matched  
   - 🟥 **Red** = Mismatched  
   - 🩵 **Azure** = Missing / Unmapped  
"""
)

st.divider()

# -------------------- FILE UPLOAD SECTION --------------------
col1, col2 = st.columns(2)
with col1:
    drawing1 = st.file_uploader("📤 Upload Drawing 1 (MicroStation PDF)", type=["pdf"], key="draw1")
with col2:
    drawing2 = st.file_uploader("📤 Upload Drawing 2 (AVEVA PDF)", type=["pdf"], key="draw2")

st.info("⚙️ Ensure `mapping.csv` is available in the `data/` folder inside the project repository.")

# -------------------- VALIDATION BUTTON --------------------
if drawing1 and drawing2:
    st.success("✅ Both drawings uploaded successfully.")

    start_validation = st.button("🚀 Start Validation", type="primary")

    if start_validation:
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

            with st.spinner("Running Smart Context-Based Validation..."):
                output_bytes, summary, debug_df = verify_drawings_memory(
                    drawing1, drawing2, mapping_csv, progress_callback=update_progress
                )

            progress_bar.progress(100)
            status_text.text("✅ Validation completed successfully!")

            # -------------------- SUMMARY SECTION --------------------
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

            # -------------------- OUTPUT DOWNLOAD --------------------
            st.download_button(
                label="📥 Download Highlighted Drawing 2 (PDF)",
                data=output_bytes,
                file_name="Drawing2_Checked.pdf",
                mime="application/pdf",
            )

            # -------------------- QA DEBUG LOG --------------------
            st.subheader("🧾 Detailed Validation Log (QA Report)")
            st.caption("This table shows each tag comparison result with context similarity confidence.")
            st.dataframe(debug_df, use_container_width=True, height=500)

            # Allow CSV download of QA log
            csv_buffer = io.StringIO()
            debug_df.to_csv(csv_buffer, index=False)
            st.download_button(
                label="📤 Download Validation Log as CSV",
                data=csv_buffer.getvalue(),
                file_name="validation_report.csv",
                mime="text/csv",
            )
else:
    st.warning("📂 Please upload both Drawing 1 and Drawing 2 before starting validation.")
