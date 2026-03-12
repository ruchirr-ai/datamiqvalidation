#!/usr/bin/env python3
"""Test AWS Pricing API"""
import sys
sys.path.insert(0, 'backend')

from services.aws_pricing_service import AWSPricingService

try:
    svc = AWSPricingService()
    print("AWS Pricing Service initialized OK")
    
    xlplus = svc.get_redshift_node_pricing("ra3.xlplus", "us-east-1")
    print(f"ra3.xlplus: ${xlplus}/hr" if xlplus else "ra3.xlplus: FAILED")
    
    fourxl = svc.get_redshift_node_pricing("ra3.4xlarge", "us-east-1")
    print(f"ra3.4xlarge: ${fourxl}/hr" if fourxl else "ra3.4xlarge: FAILED")
    
    sixteenxl = svc.get_redshift_node_pricing("ra3.16xlarge", "us-east-1")
    print(f"ra3.16xlarge: ${sixteenxl}/hr" if sixteenxl else "ra3.16xlarge: FAILED")
    
    svls = svc.get_redshift_serverless_pricing("us-east-1")
    print(f"serverless: ${svls}/RPU-hr" if svls else "serverless: FAILED")
    
    storage = svc.get_managed_storage_pricing("us-east-1")
    print(f"storage: ${storage}/GB-mo" if storage else "storage: FAILED")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
