from confidentiality import anonymize_text
import os

def save_extracted_text(text_pages, file_name, output_dir="extracted_texts"):
    """
    Save the extracted text to two local files:
    - One with the raw text.
    - One with the anonymized text.
    Args:
        text_pages (list): List of page texts.
        file_name (str): The name of the file (without extension).
        output_dir (str): The directory to save the file in. Defaults to "extracted_texts".
    Returns:
        tuple: Paths of the raw text file and anonymized text file.
    """
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Replace .pdf with .txt in the file name
    if file_name.endswith(".pdf"):
        file_name = file_name.replace(".pdf", "")

    # Save raw text
    raw_file_path = os.path.join(output_dir, f"{file_name}_raw.txt")
    with open(raw_file_path, "w", encoding="utf-8") as f:
        f.write("\n--- PAGE BREAK ---\n".join(text_pages))

    # Anonymize each page
    anonymized_pages = []
    for page_text in text_pages:
        anonymized_page = anonymize_text(page_text)
        anonymized_pages.append(anonymized_page)

    # Combine anonymized pages
    anonymized_text = "\n--- PAGE BREAK ---\n".join(anonymized_pages)

    # Save anonymized text
    anonymized_file_path = os.path.join(output_dir, f"{file_name}_anonymized.txt")
    with open(anonymized_file_path, "w", encoding="utf-8") as f:
        f.write(anonymized_text)

    return raw_file_path, anonymized_file_path, anonymized_text