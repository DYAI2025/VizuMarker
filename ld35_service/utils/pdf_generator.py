import weasyprint
from io import BytesIO
from typing import Optional

def generate_pdf_from_html(html_content: str, stylesheets: Optional[list] = None) -> bytes:
    """
    Generate PDF from HTML content using WeasyPrint
    """
    # Create a basic CSS if none provided
    if not stylesheets:
        stylesheets = []
        # Add default styling for annotations
        default_css = """
        .hl {
            background-color: yellow;
            padding: 1px 2px;
        }
        
        .legend {
            margin-top: 20px;
            padding: 10px;
            border: 1px solid #ccc;
            background-color: #f9f9f9;
        }
        
        .marker-chip {
            background-color: #007bff;
            color: white;
            border-radius: 10px;
            padding: 1px 5px;
            font-size: 0.8em;
            margin-left: 2px;
        }
        """
        stylesheets.append(weasyprint.CSS(string=default_css))
    
    # Generate the PDF
    html_doc = weasyprint.HTML(string=html_content)
    pdf_bytes = html_doc.write_pdf(stylesheets=stylesheets)
    
    # Return the PDF content as bytes
    return pdf_bytes