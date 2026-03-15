"""Whois lookup utility."""

import logging
from typing import Dict, Any, Optional

try:
    from ipwhois import IPWhois
except ImportError:
    IPWhois = None

logger = logging.getLogger(__name__)

def get_whois_info(ip_address: str) -> Optional[Dict[str, Any]]:
    """
    Perform a WHOIS lookup for the given IP address.
    
    Args:
        ip_address: The IP address to look up.
        
    Returns:
        Dictionary containing WHOIS information (asn, asn_description, asn_country_code, emails, etc.)
        or None if the lookup fails or ipwhois is not installed.
    """
    if IPWhois is None:
        logger.error("ipwhois library is not installed. Cannot perform WHOIS lookup.")
        return None
        
    try:
        obj = IPWhois(ip_address)
        # using lookup_rdap which provides structured data
        results = obj.lookup_rdap(depth=1)
        
        # Extract relevant fields
        info = {
            "asn": results.get("asn", "N/A"),
            "asn_description": results.get("asn_description", "N/A"),
            "asn_country_code": results.get("asn_country_code", "N/A"),
            "network_name": results.get("network", {}).get("name", "N/A"),
        }
        
        # Extract abuse emails if available
        emails = []
        objects = results.get("objects")
        if objects:
            for obj_key, obj_val in objects.items():
                contact = obj_val.get("contact")
                if contact and "email" in contact:
                    email_list = contact.get("email")
                    if isinstance(email_list, list):
                        for email_info in email_list:
                            if isinstance(email_info, dict):
                                email = email_info.get("value")
                                if email and email not in emails:
                                    emails.append(email)
                        
        info["abuse_emails"] = emails
        
        # Add Reputation Insight
        desc = info.get("asn_description", "").lower()
        net = info.get("network_name", "").lower()
        dc_keywords = ["hetzner", "digitalocean", "amazon", "aws", "google", "ovh", "linode", "vultr", "hosting", "cloud", "server", "datacenter"]
        
        is_dc = any(kw in desc or kw in net for kw in dc_keywords)
        info["reputation"] = "Rechenzentrum (Hosting)" if is_dc else "ISP (Privat/Business)"
        info["is_datacenter"] = is_dc
        
        return info
    except Exception as e:
        logger.error(f"WHOIS lookup failed for IP {ip_address}: {e}")
        return None
