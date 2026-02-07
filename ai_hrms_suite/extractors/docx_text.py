def extract_docx_text(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs]).strip()
