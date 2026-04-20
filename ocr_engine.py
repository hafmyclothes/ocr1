import io
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

def get_tesseract_lang(lang_choice: str) -> str:
    mapping = {"thai": "tha", "english": "eng", "mixed": "tha+eng", "auto": "tha+eng"}
    return mapping.get(lang_choice, "tha+eng")

def extract_text_from_pdf(pdf_bytes: bytes, lang: str = "tha+eng") -> list[str]:
    pages_text = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            text = page.get_text().strip()
            if not text:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes()))
                text = pytesseract.image_to_string(img, lang=lang)
            pages_text.append(text)
        doc.close()
    except Exception as e:
        pages_text = [f"Error extracting PDF: {str(e)}"]
    return pages_text

def extract_text_from_image(image_bytes: bytes, lang: str = "tha+eng") -> str:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img, lang=lang)
    except Exception as e:
        return f"Error extracting Image: {str(e)}"
