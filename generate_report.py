from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import inch # Use inch for spacing
import io
import traceback # Import traceback for better error logging
import os

def export_to_pdf(analysis_text, filename):
    """
    Generates a PDF report from the analysis text.

    Args:
        analysis_text (str): The text content of the analysis.
        filename (str or io.BytesIO): Path to save the PDF or a BytesIO buffer.

    Returns:
        bool: True if PDF generation was successful, False otherwise.
    """
    doc = None # Initialize doc to None
    try:
        if isinstance(filename, str):
            # Ensure the directory exists if saving to file path
            dir_name = os.path.dirname(filename)
            if dir_name: # Only create if dirname is not empty (i.e., not saving in current dir)
                 os.makedirs(dir_name, exist_ok=True)
            doc = SimpleDocTemplate(filename, pagesize=letter,
                                    leftMargin=inch, rightMargin=inch,
                                    topMargin=inch, bottomMargin=inch)
        elif isinstance(filename, io.BytesIO):
            doc = SimpleDocTemplate(filename, pagesize=letter,
                                    leftMargin=inch, rightMargin=inch,
                                    topMargin=inch, bottomMargin=inch)
        else:
            print(f"Error: Invalid filename/buffer type for PDF export: {type(filename)}")
            return False

        styles = getSampleStyleSheet()
        story = []

        # Title Style
        title_style = ParagraphStyle(
            name='TitleStyle',
            parent=styles['h1'],
            alignment=TA_LEFT, # Align title left
            spaceAfter=0.3*inch # Add space after title
        )
        title = Paragraph("MediScan AI Analysis Report", title_style)
        story.append(title)
        # story.append(Spacer(1, 0.3*inch)) # Space added via style

        # Body Style - Using Preformatted to preserve structure (like Markdown)
        # Using 'Code' style preserves whitespace and approximates monospace
        body_style = ParagraphStyle(
            name='BodyStyle',
            parent=styles['Code'], # Base on Code style
            fontSize=9,
            leading=12, # Line spacing
            wordWrap='CJK', # Better word wrapping for potentially long lines in analysis/tables
            leftIndent=0, # No indent for body
            # Allow hyphenation if needed:
            # allowWidows=1,
            # allowOrphans=1,
            # splitLongWords=1,
        )

        # Ensure analysis_text is a string
        if not isinstance(analysis_text, str):
            analysis_text = str(analysis_text)

        # Create Preformatted object - this handles line breaks and respects whitespace
        # Useful for rendering the Markdown-like output from Gemini
        analysis_content = Preformatted(analysis_text, body_style)
        story.append(analysis_content)

        # Build the PDF
        doc.build(story)
        # print(f"PDF report generated successfully: {'in-memory buffer' if isinstance(filename, io.BytesIO) else filename}")
        return True

    except Exception as e:
        print(f"Error generating PDF report: {e}")
        print("Traceback:")
        traceback.print_exc() # Print detailed traceback
        return False

# Example Usage (Only runs when script is executed directly)
if __name__ == '__main__':
    print("Running generate_report.py directly for testing...")
    # More realistic dummy analysis with Markdown table
    dummy_analysis = """
**Overall Summary:**
Patient shows borderline high cholesterol (210 mg/dL vs <200 mg/dL). Glucose levels are within the normal range.

**Explanation:**
The cholesterol level is slightly elevated compared to the reference range, indicating potential borderline hypercholesterolemia. Glucose is normal.

**Potential Diagnoses:**
None explicitly mentioned in context.

**Medical Recommendations:**
None explicitly mentioned in context.

**Table Format with Color-Coded Risk Levels**
| Test        | Value   | Reference Range   | Units   | Risk Level   | Note       |
|-------------|---------|-------------------|---------|--------------|------------|
| Glucose     | 95      | 70-100            | mg/dL   | 🟢           | Normal     |
| Cholesterol | 210     | <200              | mg/dL   | 🟡           | Borderline |
| Sodium      | 140     | 135-145           | mmol/L  | 🟢           | Normal     |
    """
    output_filename = "test_dummy_report.pdf" # Use a different name for testing
    buffer = io.BytesIO()

    print("\nTesting PDF generation to file:")
    if export_to_pdf(dummy_analysis, output_filename):
        print(f"Test PDF saved to {output_filename}")
    else:
        print("Failed to create test PDF file.")

    print("\nTesting PDF generation to buffer:")
    if export_to_pdf(dummy_analysis, buffer):
        print(f"Test PDF generated in buffer (size: {buffer.tell()} bytes)")
        # Optionally save buffer to file for verification
        try:
            with open("test_dummy_report_from_buffer.pdf", "wb") as f:
                f.write(buffer.getvalue())
            print("Saved buffer content to test_dummy_report_from_buffer.pdf")
        except Exception as e:
             print(f"Could not save buffer to file: {e}")
    else:
        print("Failed to create test PDF in buffer.")
