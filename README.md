# 🧠 PEFS Smart Drawing Validator

A Streamlit-based app to validate PEFS drawings (MicroStation vs AVEVA)  
by comparing `5-AD` numbers from Drawing 1 with mapped `RHL-` numbers in Drawing 2.

### 🚀 How It Works
1. Extracts text and coordinates from both PDFs using PyMuPDF.  
2. Looks for `5-AD` tags in Drawing 1.  
3. Finds corresponding `RHL-` tags in Drawing 2 (using mapping.csv).  
4. Highlights results:
   - 🟩 Matched
   - 🟥 Mismatched
   - 🩵 Missing / Unmapped  
5. Generates a QA report (CSV) + Annotated PDF.

### 🧩 Folder Structure
