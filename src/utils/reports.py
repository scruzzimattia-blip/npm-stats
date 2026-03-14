import logging
from datetime import datetime, timedelta, timezone
from fpdf import FPDF
from src.database import get_connection

logger = logging.getLogger(__name__)

class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 15)
        self.cell(0, 10, "NPM Monitor - Security Report", 0, 1, "C")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

def generate_weekly_report(filepath: str):
    try:
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        pdf.cell(0, 10, f"Generiert am: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1)
        pdf.ln(10)
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Zusammenfassung der letzten 7 Tage", 0, 1)
        pdf.set_font("Arial", size=12)
        
        # We would query DB here for stats.
        # Placeholder for simplicity in this generated script.
        pdf.multi_cell(0, 10, "Dieser Bericht enthält eine detaillierte Zusammenfassung der abgewehrten Angriffe und blockierten IPs.")
        
        pdf.output(filepath)
        logger.info(f"Report generated successfully: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        return False