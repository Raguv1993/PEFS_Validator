import streamlit as st
from core.verifier import verify_drawings_memory
from pathlib import Path
import io

st.set_page_config(page_title="PEFS Drawing Validator", layout="wide")

st.title("📘 PEFS Smart Drawing Validator")
st.markdown("""
Compare Drawing 1 (MicroStation) and Drawing 2 (AVEVA) using 5-AD → RHL mapping.  
Highlights in Drawing 2:
- 🟩 Matched  
- 🟥 Mismatched  
- 🩵 Missing / Unmapped
""")

st.divider()

col1, col2 = st.columns(2)
with col1:
    drawing1 = st.file_uploader("📂 Upload Drawing 1 (PDF)", type=["pdf"])
with col2:
    drawing2 = st.file_uploader("📂 Upload Drawing 2 (PDF)", type=["pdf"])

st.info("Ensure `data/mapping.csv` exists in project with Drawing1_No, Drawing2_No columns.")

if drawing1 and drawing2:
    st.success("✅ Both drawings uploaded successfully.")
    if st.button("🚀 Start Validation", type="primary"):
        mapping_csv = Path("data/mapping.csv")
        if not mapping_csv.exists():
            st.error("⚠️ mapping.csv not found.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(current, total):
                pct = int((current / total) * 100)
                progress_bar.progress(pct)
                status_text.text(f"🔍 Processing tag {current}/{total} ({pct}%)")

            with st.spinner("Running validation..."):
                output_bytes, summary, debug_df = verify_drawings_memory(
                    drawing1, drawing2, mapping_csv, progress_callback=update_progress
                )

            progress_bar.progress(100)
            status_text.text("✅ Validation completed!")

            st.subheader("📊 Summary")
            st.table({
                "Category": ["Total", "Matched (🟩)", "Mismatched (🟥)", "Missing (🩵)", "Unmapped (🩵)"],
                "Count": [summary["Total Tags Found"], summary["Matched"], summary["Mismatched"], summary["Missing"], summary["Unmapped"]],
            })

            st.download_button(
                label="📥 Download Annotated Drawing 2 (PDF)",
                data=output_bytes,
                file_name="Drawing2_Checked.pdf",
                mime="application/pdf"
            )

            st.subheader("🧾 Validation Log")
            st.dataframe(debug_df, use_container_width=True)

            csv_buffer = io.StringIO()
            debug_df.to_csv(csv_buffer, index=False)
            st.download_button(
                label="📤 Download Validation Log (CSV)",
                data=csv_buffer.getvalue(),
                file_name="validation_log.csv",
                mime="text/csv"
            )
else:
    st.warning("📂 Please upload both Drawing 1 and Drawing 2 to begin.")
