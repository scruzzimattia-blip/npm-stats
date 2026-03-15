import logging
from datetime import datetime, timezone
from fpdf import FPDF
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)

class PDFReport(FPDF):
    def header(self):
        # Logo
        self.set_font("Arial", "B", 15)
        self.cell(0, 10, "NPM Monitor - Security Report", 0, 1, "C")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

def generate_pdf_report(df: pd.DataFrame, title: str) -> Optional[bytes]:
    """Generate a PDF report from the given traffic data and return as bytes."""
    try:
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, title, 0, 1)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, f"Generiert am: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", 0, 1)
        pdf.ln(5)
        
        # Summary
        total_requests = len(df)
        unique_ips = df["remote_addr"].nunique()
        errors = len(df[df["status"] >= 400])
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Zusammenfassung", 0, 1)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 8, f"Gesamt-Anfragen: {total_requests}", 0, 1)
        pdf.cell(0, 8, f"Eindeutige IPs: {unique_ips}", 0, 1)
        pdf.cell(0, 8, f"Fehler-Requests: {errors}", 0, 1)
        pdf.ln(5)
        
        # Top IPs
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Top 5 IP-Adressen", 0, 1)
        pdf.set_font("Arial", size=10)
        top_ips = df["remote_addr"].value_counts().head(5)
        for ip, count in top_ips.items():
            pdf.cell(0, 8, f"{ip}: {count} Requests", 0, 1)
        pdf.ln(5)
        
        # Top Hosts
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Top 5 Domains", 0, 1)
        pdf.set_font("Arial", size=10)
        top_hosts = df["host"].value_counts().head(5)
        for host, count in top_hosts.items():
            pdf.cell(0, 8, f"{host}: {count} Requests", 0, 1)
            
        # Output as bytes
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        return None

def generate_weekly_report(filepath: str):
    """Fallback / Batch version that saves to a file."""
    # This is a placeholder for the batch script
    try:
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, f"Generiert am: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1)
        pdf.output(filepath)
        return True
    except Exception as e:
        logger.error(f"Failed to generate weekly report: {e}")
        return False