"""PDF report generation module for NPM Monitor."""

import logging
from datetime import datetime, timezone
from typing import Optional
import pandas as pd

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

logger = logging.getLogger(__name__)


class TrafficReport(FPDF if FPDF else object):
    def header(self):
        if not FPDF:
            return
        self.set_font("helvetica", "B", 15)
        self.cell(0, 10, "NPM Monitor - Traffic Report", 0, 1, "C")
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}", 0, 1, "R")
        self.ln(5)

    def footer(self):
        if not FPDF:
            return
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")


def generate_pdf_report(df: pd.DataFrame, title: str = "Traffic Analysis") -> Optional[bytes]:
    """Generate a PDF report from the traffic DataFrame."""
    if not FPDF:
        logger.error("fpdf2 not installed. Cannot generate PDF report.")
        return None

    try:
        pdf = TrafficReport()
        pdf.add_page()
        
        # Title
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 10, title, 0, 1, "L")
        pdf.ln(5)

        # Statistics summary
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "Summary Statistics", 0, 1, "L")
        pdf.set_font("helvetica", "", 10)
        
        total_requests = len(df)
        unique_ips = df["remote_addr"].nunique()
        total_bytes = df["response_length"].sum()
        error_rate = (len(df[df["status"] >= 400]) / total_requests * 100) if total_requests > 0 else 0
        
        pdf.cell(0, 8, f"Total Requests: {total_requests}", 0, 1)
        pdf.cell(0, 8, f"Unique IP Addresses: {unique_ips}", 0, 1)
        pdf.cell(0, 8, f"Total Bandwidth: {total_bytes / (1024*1024):.2f} MB", 0, 1)
        pdf.cell(0, 8, f"Error Rate: {error_rate:.2f}%", 0, 1)
        pdf.ln(10)

        # Top 10 IPs
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "Top 10 IP Addresses", 0, 1, "L")
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(60, 8, "IP Address", 1)
        pdf.cell(40, 8, "Requests", 1)
        pdf.cell(40, 8, "Country", 1)
        pdf.ln()
        
        pdf.set_font("helvetica", "", 10)
        top_ips = df["remote_addr"].value_counts().head(10)
        for ip, count in top_ips.items():
            country = df[df["remote_addr"] == ip]["country_code"].iloc[0] or "Unknown"
            pdf.cell(60, 8, str(ip), 1)
            pdf.cell(40, 8, str(count), 1)
            pdf.cell(40, 8, str(country), 1)
            pdf.ln()
            
        pdf.ln(10)

        # Status Code Distribution
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "Status Code Distribution", 0, 1, "L")
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(60, 8, "Status Code", 1)
        pdf.cell(40, 8, "Count", 1)
        pdf.cell(40, 8, "Percentage", 1)
        pdf.ln()
        
        pdf.set_font("helvetica", "", 10)
        status_counts = df["status"].value_counts().sort_index()
        for status, count in status_counts.items():
            percentage = (count / total_requests * 100)
            pdf.cell(60, 8, str(status), 1)
            pdf.cell(40, 8, str(count), 1)
            pdf.cell(40, 8, f"{percentage:.1f}%", 1)
            pdf.ln()

        return pdf.output(dest="S")

    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}")
        return None
