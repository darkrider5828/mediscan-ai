# --- START OF FILE save_table.py ---

import re
import csv
import os
import traceback # Import traceback for better error logging

def extract_table_from_response(response):
    """
    Extracts the table section from the Gemini API response more robustly.

    Args:
        response (str): The full response from the Gemini API.

    Returns:
        list: A list of rows, where each row is a list of columns (including header).
              Returns an empty list if the table cannot be found or parsed.
    """
    if not isinstance(response, str):
        print("Error: Invalid input to extract_table_from_response (expected string).")
        return []
    print("\n--- Attempting Table Extraction ---")

    # Locate the start of the table using the specific title
    # Use regex for case-insensitivity and optional surrounding markdown/whitespace
    table_title_pattern = r"^\s*(?:#+\s*)?Table Format with Color-Coded Risk Levels\s*$"
    match = re.search(table_title_pattern, response, re.IGNORECASE | re.MULTILINE)

    table_start_index = -1 # Initialize

    if not match:
        print("Warning: Could not find the exact table title marker:")
        print(f"Searched for pattern: '{table_title_pattern}'")
        # Fallback: Try finding common table header patterns
        # Check for header row like | Test | Value | ... | or Test \t Value \t ...
        header_patterns = [
            r"^\s*\|?\s*Test\s*\|?\s*Value\s*\|?\s*Reference Range", # Pipe separated, optional leading/trailing pipes
            r"^\s*Test\s+(?:Value|Result)\s+Reference Range",       # Space separated (less reliable)
            r"^\s*Test\s*\t(?:Value|Result)\s*\tReference Range"     # Tab separated
        ]
        for pattern in header_patterns:
             header_match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
             if header_match:
                  # Start search from the beginning of the header line
                  table_start_index = header_match.start()
                  print(f"Found fallback table header pattern: '{pattern}' at index {table_start_index}")
                  break
        else: # If no title and no header patterns found
            print("No table start marker or header pattern found. Cannot extract table.")
            return []
    else:
        # Start searching for table content *after* the title line
        table_start_index = match.end()
        print(f"Table title marker found. Starting search after index {table_start_index}.")

    # Extract the content *after* the found marker
    table_content_search_area = response[table_start_index:].strip()
    # print(f"Raw content search area after marker:\n---\n{table_content_search_area[:300]}...\n---") # Debug

    # Find the end of the table. Look for:
    # 1. Double newlines (common paragraph break)
    # 2. Start of a new markdown heading (e.g., ###, **)
    # 3. End of the string
    # 4. Common concluding remarks like "Disclaimer:"
    end_match = re.search(r'\n\s*\n|\n\s*(?:#+\s*|\*{2,})[A-Za-z]|\n\s*Disclaimer:|\Z', table_content_search_area, re.IGNORECASE | re.MULTILINE)
    end_index = end_match.start() if end_match else len(table_content_search_area)

    table_content = table_content_search_area[:end_index].strip()

    if not table_content:
        print("Warning: Found table start marker, but no subsequent content identified as table.")
        return []

    print(f"Potential raw table content extracted:\n---\n{table_content}\n---")

    # --- Parsing the Table Content ---
    rows = table_content.split("\n")
    parsed_rows = []
    header_found = False # Flag to check if we've captured a header-like row

    for row_num, row in enumerate(rows):
        stripped_row = row.strip()
        if not stripped_row: # Skip empty lines
            continue

        # Skip markdown separator lines (e.g., |---|---| or ------)
        # Allow for variations in separators like ':', '=', etc. used in markdown tables
        if re.match(r'^\|?[-|=:\s]{5,}\|?$', stripped_row.replace('|', '')):
            print(f"Skipping separator line: {stripped_row}")
            continue

        # Try parsing based on delimiters, prioritizing pipe
        columns = []
        if '|' in stripped_row:
            # Handle leading/trailing pipes and split
            columns = [col.strip() for col in stripped_row.strip('|').split('|')]
        elif '\t' in stripped_row:
             columns = [col.strip() for col in stripped_row.split('\t')]
        else:
             # Fallback: Split by multiple spaces (at least 2)
             # This is less reliable if values or units contain spaces
             columns = [col.strip() for col in re.split(r'\s{2,}', stripped_row)]

        # Clean up empty strings potentially resulting from split
        columns = [col for col in columns if col]

        if columns:
            # Basic validation: Expect at least 3-4 columns for a valid data row
            # Adjust threshold based on expected table structure (6 columns expected here)
            if len(columns) >= 4:
                # If this is the first valid row captured, assume it's the header
                if not header_found:
                     print(f"Assuming Header: {columns}")
                     header_found = True
                parsed_rows.append(columns)
            # else: # Optional: Log skipped rows
            #    print(f"Skipping row with insufficient columns ({len(columns)} found): {columns}")

    if not parsed_rows:
        print("Warning: Table content found but could not parse into valid rows/columns.")
        return []

    # Heuristic: Ensure the first row captured actually looks like a header
    if header_found:
        header_keywords = ["test", "value", "range", "units", "level", "note"]
        first_row_lower = [str(col).lower() for col in parsed_rows[0]]
        # Check if at least 2 common header words are present
        if sum(keyword in ' '.join(first_row_lower) for keyword in header_keywords) < 2:
            print("Warning: The first parsed row doesn't strongly resemble the expected header. Table parsing might be inaccurate.")
            # Decide whether to proceed or return empty list if header is critical
            # For robustness, we'll proceed but log the warning.
            # return [] # Stricter: uncomment to require a good header
    elif parsed_rows: # If no header was flagged, but rows exist
         print("Warning: No clear header row identified during parsing.")
    else: # Should not happen if parsed_rows is not empty, but as a safeguard
        print("Warning: No header found and no data rows parsed.")
        return []


    print(f"Successfully extracted {len(parsed_rows)} rows (including potential header).")
    # print(f"Extracted Table Data:\n{parsed_rows}") # Debug: Print parsed data
    print("--- Table Extraction Complete ---")
    return parsed_rows # Return the list of lists


def save_table_to_csv(table_data, file_name_base, output_dir):
    """
    Saves the extracted table data to a CSV file in the specified directory.

    Args:
        table_data (list): A list of rows (list of columns), including header.
        file_name_base (str): The base name for the file (e.g., sessionid_original).
        output_dir (str): The directory to save the file in.

    Returns:
        str: Full path to the saved CSV file, or None if saving fails.
    """
    if not table_data:
        print("No table data provided to save_table_to_csv.")
        return None
    if not output_dir:
        print("Error: Output directory not specified for saving CSV.")
        return None
    if not file_name_base:
        print("Error: File name base not specified for saving CSV.")
        return None

    csv_file_path = None # Initialize
    try:
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Construct the full CSV file path
        # Ensure file_name_base doesn't have problematic extensions already
        safe_file_name_base = file_name_base.replace(".pdf", "").replace(".txt", "")
        csv_file_path = os.path.join(output_dir, f"{safe_file_name_base}_table.csv")

        # Write the table data to the CSV file
        with open(csv_file_path, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(table_data)

        print(f"Table data successfully saved to: {csv_file_path}")
        return csv_file_path

    except IOError as e:
        print(f"Error writing CSV file to {csv_file_path or 'path construction failed'}: {e}")
        traceback.print_exc()
        return None
    except Exception as e:
         print(f"An unexpected error occurred during CSV saving: {e}")
         traceback.print_exc()
         return None


def save_table(response, file_name_base, output_dir="processed_data/tables"):
    """
    Extracts the table from the Gemini API response and saves it as a CSV file
    in the specified directory.

    Args:
        response (str): The full response from the Gemini API.
        file_name_base (str): The base name for the file (e.g., sessionid_original).
        output_dir (str): The directory to save the file in. Defaults to "processed_data/tables".

    Returns:
        str: Path to the saved CSV file, or None if extraction or saving fails.
    """
    print(f"Attempting to extract and save table for base name: {file_name_base} in dir: {output_dir}")
    try:
        # Step 1: Extract the table from the response
        table_data = extract_table_from_response(response)

        if not table_data:
            # If no table found, don't treat as error, just return None
            print("No table data extracted from response. CSV not saved.")
            return None

        # Step 2: Save the extracted table to a CSV file
        # Pass the received output_dir to the inner saving function
        csv_file_path = save_table_to_csv(table_data, file_name_base, output_dir=output_dir)

        return csv_file_path # Return path if successful, None otherwise

    except Exception as e:
        print(f"An unexpected error occurred in save_table function: {e}")
        traceback.print_exc()
        return None
# --- END OF FILE save_table.py ---