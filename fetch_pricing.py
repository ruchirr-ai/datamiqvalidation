#!/usr/bin/env python3
"""
Fetch Redshift pricing from AWS public bulk pricing API.
No IAM credentials needed - this is a public endpoint.
"""
import json
import urllib.request
import sys

# Step 1: Get the Redshift pricing index URL
print("Fetching AWS pricing index...")
index_url = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json"
with urllib.request.urlopen(index_url) as resp:
    index = json.loads(resp.read())

redshift_url = index["offers"]["AmazonRedshift"]["currentRegionIndexUrl"]
print(f"Redshift regional index: {redshift_url}")

# Step 2: Get the us-east-1 specific pricing
region_index_url = f"https://pricing.us-east-1.amazonaws.com{redshift_url}"
print(f"Fetching regional index from: {region_index_url}")
with urllib.request.urlopen(region_index_url) as resp:
    region_index = json.loads(resp.read())

# Find us-east-1 region URL
for region_key, region_data in region_index.get("regions", {}).items():
    if "us-east-1" in region_key.lower() or "US East" in str(region_data):
        print(f"Found region: {region_key} -> {region_data}")

# Get the direct pricing file for us-east-1
us_east_url = None
for region_key, region_data in region_index.get("regions", {}).items():
    if region_key == "us-east-1":
        us_east_url = region_data.get("currentVersionUrl")
        break

if not us_east_url:
    # Try the full offer file instead
    full_url = index["offers"]["AmazonRedshift"]["currentVersionUrl"]
    print(f"Using full pricing file: {full_url}")
    us_east_url = full_url

full_pricing_url = f"https://pricing.us-east-1.amazonaws.com{us_east_url}"
print(f"Fetching pricing data from: {full_pricing_url}")
print("(This may take a moment...)")

with urllib.request.urlopen(full_pricing_url) as resp:
    pricing_data = json.loads(resp.read())

# Step 3: Find Redshift node pricing for us-east-1
products = pricing_data.get("products", {})
terms = pricing_data.get("terms", {})

# Debug: list all product families and usage types
families = set()
usage_types = set()
sample_attrs = None
for sku, product in products.items():
    attrs = product.get("attributes", {})
    families.add(attrs.get("productFamily", ""))
    ut = attrs.get("usagetype", "")
    if "ra3" in ut.lower():
        usage_types.add(ut)
    if not sample_attrs and "ra3" in str(attrs).lower() and "Node" in ut:
        sample_attrs = attrs
print(f"Product families found: {sorted(families)}")
print(f"RA3 usage types: {sorted(usage_types)}")
if sample_attrs:
    print(f"Sample RA3 compute product: {json.dumps(sample_attrs, indent=2)}")

# Find ra3 node products in us-east-1
target_types = ["ra3.xlplus", "ra3.4xlarge", "ra3.16xlarge"]
found_products = {}

for sku, product in products.items():
    attrs = product.get("attributes", {})
    instance_type = attrs.get("instanceType", "")
    location = attrs.get("location", "")
    usage_type = attrs.get("usagetype", "")
    
    # Match compute node entries (not concurrency scaling, not free tier)
    if (instance_type in target_types 
        and "Virginia" in location 
        and "Node" in usage_type
        and "CS" not in usage_type
        and "Free" not in usage_type):
        found_products[instance_type] = {
            "sku": sku,
            "location": location,
            "usage_type": usage_type,
            "instance_type": instance_type,
            "vcpu": attrs.get("vcpu"),
            "memory": attrs.get("memory"),
        }

# Extract on-demand pricing
print("\n=== Redshift On-Demand Pricing (US East - N. Virginia) ===")
for instance_type in target_types:
    if instance_type not in found_products:
        print(f"{instance_type}: NOT FOUND")
        continue
    
    sku = found_products[instance_type]["sku"]
    on_demand = terms.get("OnDemand", {}).get(sku, {})
    
    for term_key, term_data in on_demand.items():
        for dim_key, dim_data in term_data.get("priceDimensions", {}).items():
            price = dim_data.get("pricePerUnit", {}).get("USD", "N/A")
            unit = dim_data.get("unit", "")
            desc = dim_data.get("description", "")
            print(f"{instance_type}: ${price}/hr ({desc})")
            found_products[instance_type]["on_demand_hourly"] = float(price) if price != "N/A" else None

# Also look for Serverless pricing
print("\n=== Redshift Serverless Pricing ===")
for sku, product in products.items():
    attrs = product.get("attributes", {})
    product_family = attrs.get("productFamily", "")
    location = attrs.get("location", "")
    usage_type = attrs.get("usagetype", "")
    
    if ("Serverless" in product_family and "Virginia" in location
        and "RPU" in usage_type):
        on_demand = terms.get("OnDemand", {}).get(sku, {})
        for term_key, term_data in on_demand.items():
            for dim_key, dim_data in term_data.get("priceDimensions", {}).items():
                price = dim_data.get("pricePerUnit", {}).get("USD", "N/A")
                desc = dim_data.get("description", "")
                unit = dim_data.get("unit", "")
                print(f"Serverless: ${price}/{unit} ({desc})")

# Also look for Managed Storage pricing
print("\n=== Redshift Managed Storage Pricing ===")
for sku, product in products.items():
    attrs = product.get("attributes", {})
    product_family = attrs.get("productFamily", "")
    location = attrs.get("location", "")
    usage_type = attrs.get("usagetype", "")
    
    if ("Storage" in product_family and "Virginia" in location
        and "RMS" in usage_type and "Redshift" in str(attrs)):
        on_demand = terms.get("OnDemand", {}).get(sku, {})
        for term_key, term_data in on_demand.items():
            for dim_key, dim_data in term_data.get("priceDimensions", {}).items():
                price = dim_data.get("pricePerUnit", {}).get("USD", "N/A")
                desc = dim_data.get("description", "")
                print(f"Storage: ${price}/GB-mo ({desc})")

# Summary
print("\n=== SUMMARY FOR HARDCODED PRICES ===")
for it in target_types:
    if it in found_products and found_products[it].get("on_demand_hourly"):
        p = found_products[it]["on_demand_hourly"]
        monthly = p * 730
        print(f"{it}: ${p}/hr = ${monthly:,.2f}/mo per node")
