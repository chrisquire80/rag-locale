from fpdf import FPDF
import datetime
import os
from typing import Any
from pathlib import Path

# Create reports directory
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

class PDFReport(FPDF):
    def header(self):
        # Logo placeholder or title
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, "RAG Locale - Executive Report", ln=True, align='R')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def generate_visual_report(insights_list: list[dict[str, Any]], report_title: str = "Report Analitico Documentale") -> str:
    """
    Generates a PDF report from a list of insights (text + image paths).
    
    Args:
        insights_list: List of dicts with keys:
            - 'source': Source document name
            - 'text': Synthesis/Analysis text
            - 'path': Path to the chart/image (str or Path)
        report_title: Title of the report
        
    Returns:
        Path to the generated PDF file.
    """
    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Title Page
    pdf.add_page()
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(0, 60, report_title, ln=True, align='C')
    
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Generato il: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
    pdf.ln(20)
    
    # Summary (if any generic synthesis is provided as first element without source/path)
    # Check if first element is a pure summary
    if insights_list and not insights_list[0].get('path') and not insights_list[0].get('source'):
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "Sintesi Esecutiva", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, insights_list[0]['text'])
        pdf.ln(20)
        insights_list = insights_list[1:]

    # Content Pages
    for i, insight in enumerate(insights_list):
        # Avoid orphan headers at bottom of page
        if pdf.get_y() > 250:
             pdf.add_page()

        # Source Title
        pdf.set_font("Arial", 'B', 14)
        source_text = f"Fonte: {insight.get('source', 'Analisi Interattiva')}"
        pdf.cell(0, 10, source_text, ln=True)
        
        # Image (Chart/Table)
        img_path = insight.get('path')
        if img_path and os.path.exists(img_path):
            try:
                # Calculate image dimensions to fit page width while maintaining aspect ratio
                # A4 width ~210mm, margins 10mm left/right -> 190mm usable
                pdf.image(img_path, x=15, w=180)
                pdf.ln(5)
            except Exception as e:
                pdf.set_font("Arial", 'I', 10)
                pdf.cell(0, 10, f"[Immagine non disponibile: {e}]", ln=True)
        
        # Text Analysis
        text = insight.get('text', '')
        if text:
            # Anomaly Detection Logic (FASE 23)
            # Check for [ANOMALIA] tag and format accordingly
            is_anomaly = "[ANOMALIA]" in text
            clean_text = text.replace("[ANOMALIA]", "⚠️ ATTENZIONE: ")

            if is_anomaly:
                pdf.set_text_color(200, 0, 0) # Red for anomalies
                pdf.set_font("Arial", 'B', 11)
            else:
                pdf.set_text_color(0, 0, 0) # Standard Black
                pdf.set_font("Arial", size=11)

            pdf.multi_cell(0, 8, clean_text)
            
            # Reset color
            pdf.set_text_color(0, 0, 0) 
        
        pdf.ln(10)
        
        # Separator line if not last item
        if i < len(insights_list) - 1:
            y = pdf.get_y()
            pdf.line(15, y, 195, y)
            pdf.ln(10)

    filename = f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    report_path = REPORTS_DIR / filename
    pdf.output(str(report_path))
    
    return str(report_path)
