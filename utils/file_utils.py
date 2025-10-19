from pathlib import Path

def save_uploaded_file(uploaded_file, filename):
    """Save a Streamlit-uploaded file to disk."""
    path = Path(filename)
    path.write_bytes(uploaded_file.getvalue())
    return path
