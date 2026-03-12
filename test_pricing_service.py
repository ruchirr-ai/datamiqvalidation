#!/usr/bin/env python3
"""
Quick test for AWSPricingService - run on EC2 to verify live pricing works.
Usage: /opt/datamiq/backend/.venv/bin/python test_pricing_service.py
"""
import sys
sys.path.insert(0, 'backend')

from services.aws_pricing_service import AWSPricingService

svc = AWSPricingService(timeout=30)

print("=== Testing AWSPricingService (public bulk API) ===\n")

# Test all pricing in one call
print("Fetching all Redshift pricing for us-east-1...")
all_pricing = svc.get_all_redshift_pricing("us-east-1")

print("\nProvisioned node pricing:")
for nt, price in sorted(all_pricing.get('provisioned', {}).items()):
    monthly = price * 730
    print(f"  {nt}: ${price}/hr = ${monthly:,.2f}/mo")

svls = all_pricing.get('serverless_per_rpu_hour')
print(f"\nServerless RPU-hour: {'$' + str(svls) if svls else 'NOT FOUND (using fallback)'}")

storage = all_pricing.get('managed_storage_per_gb_month')
print(f"Managed Storage: {'$' + str(storage) + '/GB-mo' if storage else 'NOT FOUND (using fallback)'}")

# Expected values for validation
expected = {
    'ra3.xlplus': 1.086,
    'ra3.4xlarge': 3.26,
    'ra3.16xlarge': 13.04,
}
print("\n=== Validation ===")
for nt, exp_price in expected.items():
    actual = all_pricing.get('provisioned', {}).get(nt)
    if actual:
        match = "✓" if abs(actual - exp_price) < 0.01 else f"✗ (expected {exp_price})"
        print(f"  {nt}: ${actual}/hr {match}")
    else:
        print(f"  {nt}: NOT FOUND ✗")

# Test TCO engine integration
print("\n=== Testing TCO Engine Integration ===")
from services.tco_engine import TCOEngine
tco = TCOEngine(use_live_pricing=True)
pricing = tco._get_region_pricing('us-east-1', {'node_type': 'ra3.xlplus'})
print(f"TCO engine got pricing for us-east-1:")
for nt, price in sorted(pricing.get('provisioned', {}).items()):
    if 'ra3' in nt:
        print(f"  {nt}: ${price}/hr")
print(f"  Serverless: ${pricing.get('serverless_per_rpu_hour')}/RPU-hr")
print(f"  Storage: ${pricing.get('managed_storage_per_gb_month')}/GB-mo")

print("\nDone!")
