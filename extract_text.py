import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from PIL import Image
import re
import io # Required for handling image bytes

# --- Configuration ---
# Optional: Set the path to the Tesseract executable if it's not in your PATH
# pytesseract.pytesseract.tesseract_cmd = r'/path/to/tesseract'

def extract_text_with_ocr(pdf_path):
    """
    Extract text from a PDF page by page using Tesseract OCR on images.
    Uses fitz (PyMuPDF) for efficient image extraction.
    Returns a list of strings, one per page.
    """
    ocr_page_texts = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = ""
            # Extract images from the page
            # Using get_images(full=True) provides more details including xref
            image_list = page.get_images(full=True)

            if not image_list:
                 # If no images, maybe try rendering the page itself as an image
                 # This handles pages that are purely vector graphics or text that
                 # wasn't extracted by get_text() but could be OCR'd if rendered.
                 # Increase DPI for better OCR quality, e.g., 300
                 zoom = 300 / 72  # Scale factor for 300 DPI
                 mat = fitz.Matrix(zoom, zoom)
                 pix = page.get_pixmap(matrix=mat)
                 img_bytes = pix.tobytes("png") # Or "jpeg", etc.
                 try:
                     img = Image.open(io.BytesIO(img_bytes))
                     # Adding language might improve accuracy e.g., lang='eng'
                     page_text += pytesseract.image_to_string(img) + "\n"
                 except Exception as e:
                     print(f"Warning: Could not OCR page {page_num+1} render: {e}")

            else:
                # Process extracted images
                for img_index, img_info in enumerate(image_list):
                    xref = img_info[0]  # XREF of the image
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    try:
                        img = Image.open(io.BytesIO(image_bytes))
                        # Adding language might improve accuracy e.g., lang='eng'
                        img_text = pytesseract.image_to_string(img)
                        page_text += img_text + "\n"
                    except Exception as e:
                        print(f"Warning: Could not OCR image {img_index} on page {page_num+1}: {e}")

            ocr_page_texts.append(page_text)
        doc.close()
    except Exception as e:
        print(f"Error during OCR processing: {e}")
        # Return empty list matching page count if possible, else empty
        try:
            # Try to get page count even if OCR failed partially
            doc_check = fitz.open(pdf_path)
            count = len(doc_check)
            doc_check.close()
            return [""] * count
        except:
            return [] # Fallback if even opening fails

    return ocr_page_texts


def clean_and_structure_text(text, page_num):
    """
    Clean and structure the extracted text for a single page.
    Includes page number context in cleaning.
    """
    # Remove potential headers/footers - more specific patterns are better
    # Example: Remove lines that seem like 'Page X' or 'Document Title'
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Basic cleaning - remove lines that are just whitespace or likely page numbers
        if line.strip():
            # More robust page number removal (adjust regex as needed)
            if not re.fullmatch(r'^\s*(Page\s*)?\d+(\s*of\s*\d+)?\s*$', line.strip(), re.IGNORECASE):
                 # Add more header/footer patterns here if known
                 # if not re.match(r'^(Confidential|Internal Use Only)', line.strip()):
                 cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines)
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Normalize multiple newlines to double newline (paragraph break)

    # --- Structuring (Example - Adapt based on your specific document structure) ---
    # This part is highly dependent on the expected PDF format.
    # It might be better to do structuring *after* combining all pages
    # if sections span across pages. For now, we keep it per-page.

    structured_output = f"--- Page {page_num + 1} ---\n\n"

    # Example: Try to find common sections using keywords (case-insensitive)
    # This is a very basic example. Real-world structuring needs more robust logic.
    sections = {
        "Patient Details": None,
        "Biomarkers": None,
        "Observations": None,
        "Recommendations": None,
        "Other": []
    }

    current_section = "Other" # Default
    lines = text.split('\n')
    section_content = {key: "" for key in sections}

    # Basic keyword-based section identification (improve with regex)
    for line in lines:
        l_lower = line.strip().lower()
        if "patient details" in l_lower or "patient name" in l_lower:
            current_section = "Patient Details"
        elif "biomarker" in l_lower or "results" in l_lower or "test name" in l_lower :
             current_section = "Biomarkers"
        elif "observation" in l_lower or "finding" in l_lower:
             current_section = "Observations"
        elif "recommendation" in l_lower or "suggestion" in l_lower or "next step" in l_lower:
             current_section = "Recommendations"
        # Add more specific section start identifiers here

        # Add line to the current section
        if current_section == "Other":
             sections["Other"].append(line)
        elif sections[current_section] is not None: # Check if it's a valid section key
             section_content[current_section] += line + "\n"

    # Format the output
    for section, content in section_content.items():
         if content and content.strip():
              structured_output += f"### {section}\n{content.strip()}\n\n"

    # Add remaining 'Other' content
    if sections["Other"]:
         other_content = "\n".join(sections["Other"]).strip()
         if other_content:
              structured_output += f"### Other Content\n{other_content}\n\n"

    # Fallback if no sections were identified
    if not any(section_content.values()):
         structured_output += text # Return cleaned text if structuring failed

    return structured_output.strip()


def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file page by page, including tables and handling scanned content via OCR.
    Cleans and structures text for each page.
    Returns a list of cleaned and structured page texts.
    """
    page_texts = []
    page_count = 0

    # 1. Extract text using PyMuPDF (fitz)
    try:
        with fitz.open(pdf_path) as doc:
            page_count = len(doc)
            for page_num in range(page_count):
                page = doc.load_page(page_num)
                page_texts.append(page.get_text())
    except Exception as e:
        print(f"Error opening or reading PDF with Fitz: {e}")
        return [] # Cannot proceed

    # 2. Check if text extraction was successful, if not, use OCR
    # Check if *meaningful* text was extracted (ignore pages with only whitespace)
    if not any(text and text.strip() for text in page_texts):
        print("No substantial text found using PyMuPDF. Attempting OCR...")
        page_texts = extract_text_with_ocr(pdf_path)
        # Check if OCR returned expected number of pages
        if len(page_texts) != page_count and page_count > 0:
             print(f"Warning: OCR returned {len(page_texts)} pages, expected {page_count}. Results might be misaligned.")
             # Pad OCR results if necessary, though alignment might still be off
             if len(page_texts) < page_count:
                 page_texts.extend([""] * (page_count - len(page_texts)))
             else: # OCR found more pages? Trim to expected count? Or use OCR count?
                  # Let's trust the initial page_count from fitz for now
                  page_texts = page_texts[:page_count]
        elif not page_texts and page_count == 0:
             print("Error: Could not determine page count and OCR failed.")
             return []


    # 3. Extract tables using pdfplumber and append to corresponding page text
    processed_page_texts = [""] * page_count # Initialize final list
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Ensure pdfplumber page count matches fitz page count
            if len(pdf.pages) != page_count:
                print(f"Warning: pdfplumber found {len(pdf.pages)} pages, expected {page_count}. Table alignment might be affected.")
                # Adjust loop range if necessary, or decide on a primary page count
                # For simplicity, we'll iterate up to the minimum of the two counts
                iter_count = min(len(pdf.pages), page_count)
            else:
                iter_count = page_count

            for i in range(iter_count):
                # Start with the text extracted by fitz or OCR
                current_page_content = page_texts[i] if i < len(page_texts) else ""

                # Extract tables from the current page
                page = pdf.pages[i]
                tables = page.extract_tables() # Returns list of tables found on page

                if tables:
                    table_text = "\n\n--- Extracted Tables on Page {} ---\n".format(i + 1)
                    for table_num, table in enumerate(tables):
                        if table: # Ensure table is not empty
                             table_text += f"\n[Table {table_num + 1}]\n"
                             # Simple formatting: join cells with tab, rows with newline
                             table_text += "\n".join(["\t".join(filter(None, cell if cell is not None else '')) for cell in row]) + "\n"
                        else:
                             table_text += f"\n[Table {table_num + 1} (empty or extraction failed)]\n"
                    current_page_content += table_text

                # Store the combined text (fitz/ocr + tables)
                processed_page_texts[i] = current_page_content

    except Exception as e:
        print(f"Error during table extraction with pdfplumber: {e}")
        # If tables fail, continue with the text we already have
        for i in range(page_count):
             if i < len(page_texts):
                processed_page_texts[i] = page_texts[i]


    # 4. Clean and structure text for each page
    final_structured_texts = []
    for i in range(page_count):
        cleaned_structured_text = clean_and_structure_text(processed_page_texts[i], i)
        final_structured_texts.append(cleaned_structured_text)

    return final_structured_texts

# --- Example Usage ---
if __name__ == "__main__":
    pdf_file_path = 'example.pdf' # Replace with your PDF file path

    # Create a dummy multi-page PDF for testing if you don't have one
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch

        def create_dummy_pdf(filename="example.pdf"):
            c = canvas.Canvas(filename, pagesize=letter)
            width, height = letter

            # Page 1: Basic Text and Patient Info
            textobject = c.beginText(inch, height - inch)
            textobject.textLine("Page 1 of 2")
            textobject.textLine("Health Report - Confidential")
            textobject.textLine("")
            textobject.textLine("Patient Name: John Doe")
            textobject.textLine("Age: 45")
            textobject.textLine("Gender: Male")
            textobject.textLine("")
            textobject.textLine("### Observations")
            textobject.textLine("Initial assessment shows stable vital signs.")
            c.drawText(textobject)
            c.showPage() # End Page 1

            # Page 2: Biomarkers (like a table) and Recommendations
            textobject = c.beginText(inch, height - inch)
            textobject.textLine("Page 2 of 2")
            textobject.textLine("")
            textobject.textLine("### Biomarkers / Test Results")
            textobject.textLine("Test Name\tValue\tUnit\tReference") # Simulate table header
            textobject.textLine("-------------\t-----\t----\t----------") # Simulate separator
            textobject.textLine("Glucose\t95\tmg/dL\t70-100")
            textobject.textLine("Cholesterol\t210\tmg/dL\t<200")
            textobject.textLine("Hemoglobin A1c:\t5.5\t%\t<5.7") # Example of slightly different format
            textobject.textLine("")
            textobject.textLine("### Recommendations")
            textobject.textLine("Follow up in 6 months.")
            textobject.textLine("Consider dietary adjustments for cholesterol.")
            c.drawText(textobject)
            c.showPage() # End Page 2

            c.save()
            print(f"Created dummy PDF: {filename}")

        create_dummy_pdf(pdf_file_path)

    except ImportError:
        print("ReportLab not installed. Cannot create dummy PDF. Please provide your own PDF.")
        # pdf_file_path = 'path/to/your/actual/multi-page.pdf' # Set path here if needed

    except Exception as e:
        print(f"Error creating dummy PDF: {e}")
        # pdf_file_path = 'path/to/your/actual/multi-page.pdf' # Set path here if needed


    # --- Run Extraction ---
    if pdf_file_path and fitz.exists(pdf_file_path): # Check if path is set and file exists
         print(f"\n--- Extracting data from: {pdf_file_path} ---")
         structured_pages = extract_text_from_pdf(pdf_file_path)

         if structured_pages:
             print(f"\n--- Extracted and Structured Content ({len(structured_pages)} pages) ---")
             for page_content in structured_pages:
                 print(page_content)
                 print("\n" + "="*80 + "\n") # Separator between pages
         else:
             print("No content extracted.")
    else:
         print(f"PDF file not found or path not set: {pdf_file_path}")