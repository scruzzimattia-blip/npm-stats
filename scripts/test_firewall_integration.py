#!/usr/bin/env python3
"""Integration test for Firewall Blocking."""

import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.firewall import get_iptables_manager


def run_test():
    print("--- NPM Monitor: Firewall Integration Test ---")

    manager = get_iptables_manager()

    if not manager.available:
        print("❌ FEHLER: iptables ist auf diesem System nicht verfügbar.")
        return

    print(f"Iptables verfügbar: {'✅' if manager.available else '❌'}")
    print(f"Berechtigungen vorhanden: {'✅' if manager.has_permissions else '❌ (Sudo wird benötigt)'}")

    test_ip = "1.2.3.4"
    test_reason = "Integration-Test-Sperre"

    try:
        # 1. Chain erstellen
        print("\n1. Erstelle/Prüfe NPM_MONITOR Chain...")
        if manager.create_chain():
            print("   ✅ Chain erfolgreich initialisiert.")
        else:
            print("   ❌ Fehler beim Erstellen der Chain. Bitte mit 'sudo' ausführen.")
            return

        # 2. IP blocken
        print(f"\n2. Blockiere Test-IP {test_ip}...")
        if manager.block_ip(test_ip, test_reason):
            print(f"   ✅ IP {test_ip} wurde blockiert.")
        else:
            print("   ❌ Fehler beim Blockieren der IP.")

        # 3. Verifizieren via CLI call
        print("\n3. Verifiziere Regel in iptables...")
        cmd = ["sudo", "iptables", "-L", "NPM_MONITOR", "-n"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if test_ip in result.stdout:
            print(f"   ✅ Bestätigt: IP {test_ip} steht in der iptables Liste.")
            print(f"      Regel-Details:\n      {result.stdout.strip().splitlines()[-1]}")
        else:
            print("   ❌ Fehler: IP wurde nicht in der iptables Liste gefunden.")

        # 4. IP wieder freigeben
        print(f"\n4. Gebe IP {test_ip} wieder frei...")
        if manager.unblock_ip(test_ip):
            print(f"   ✅ IP {test_ip} wurde erfolgreich entblockt.")
        else:
            print("   ❌ Fehler beim Entblocken.")

        # 5. Finale Prüfung
        result = subprocess.run(cmd, capture_output=True, text=True)
        if test_ip not in result.stdout:
            print("   ✅ Bestätigt: IP wurde aus iptables entfernt.")
        else:
            print("   ❌ Fehler: IP steht immer noch in iptables.")

    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")

    print("\n--- Test Abgeschlossen ---")

if __name__ == "__main__":
    run_test()
