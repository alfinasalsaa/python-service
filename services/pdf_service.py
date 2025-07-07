import fitz  # PyMuPDF
from PIL import Image

class PDFService:
    def add_qr_to_pdf(self, input_pdf_path, qr_image_path, output_pdf_path):
        """Add QR code to PDF document"""
        try:
            # Open PDF
            pdf_document = fitz.open(input_pdf_path)
            
            # Get first page
            page = pdf_document.load_page(0)
            
            # Get page dimensions
            page_rect = page.rect
            
            # Define QR code position (bottom right corner)
            qr_size = 100
            qr_rect = fitz.Rect(
                page_rect.width - qr_size - 20,  # x0
                page_rect.height - qr_size - 20,  # y0
                page_rect.width - 20,             # x1
                page_rect.height - 20             # y1
            )
            
            # Insert QR code image
            page.insert_image(qr_rect, filename=qr_image_path)
            
            # Add verification text
            text_rect = fitz.Rect(
                page_rect.width - 200,
                page_rect.height - qr_size - 40,
                page_rect.width - 20,
                page_rect.height - qr_size - 20
            )
            
            page.insert_textbox(
                text_rect,
                "Dokumen Tersertifikasi Digital\nScan QR untuk verifikasi",
                fontsize=8,
                color=(0, 0, 0),
                align=1  # Center align
            )
            
            # Save modified PDF
            pdf_document.save(output_pdf_path)
            pdf_document.close()
            
        except Exception as e:
            raise Exception(f"Error adding QR code to PDF: {str(e)}")