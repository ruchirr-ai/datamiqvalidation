"""
AWS Pricing Service - Fetches real-time pricing from AWS Pricing API
"""
import boto3
import json
from typing import Dict, Optional
from functools import lru_cache


class AWSPricingService:
    """Service to fetch AWS pricing data using boto3 Pricing API"""
    
    def __init__(self):
        # AWS Pricing API is only available in us-east-1 and ap-south-1
        self.pricing_client = boto3.client('pricing', region_name='us-east-1')
    
    @lru_cache(maxsize=128)
    def get_redshift_node_pricing(
        self,
        instance_type: str,
        region: str = 'us-east-1',
        term_type: str = 'OnDemand'
    ) -> Optional[float]:
        """
        Get hourly pricing for a Redshift node type in a specific region.
        
        Args:
            instance_type: e.g., 'ra3.xlplus', 'ra3.4xlarge'
            region: AWS region code, e.g., 'us-east-1'
            term_type: 'OnDemand', 'Reserved1Yr', or 'Reserved3Yr'
        
        Returns:
            Hourly price in USD, or None if not found
        """
        try:
            # Map region codes to AWS Pricing API location names
            region_map = {
                'us-east-1': 'US East (N. Virginia)',
                'us-east-2': 'US East (Ohio)',
                'us-west-1': 'US West (N. California)',
                'us-west-2': 'US West (Oregon)',
                'eu-west-1': 'EU (Ireland)',
                'eu-central-1': 'EU (Frankfurt)',
                'ap-south-1': 'Asia Pacific (Mumbai)',
                'ap-southeast-1': 'Asia Pacific (Singapore)',
                'ap-southeast-2': 'Asia Pacific (Sydney)',
                'ap-northeast-1': 'Asia Pacific (Tokyo)',
            }
            
            location = region_map.get(region, 'US East (N. Virginia)')
            
            # Build filters for the pricing query
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonRedshift'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Compute Instance'},
            ]
            
            response = self.pricing_client.get_products(
                ServiceCode='AmazonRedshift',
                Filters=filters,
                MaxResults=10
            )
            
            if not response.get('PriceList'):
                return None
            
            # Parse the first matching product
            for price_item in response['PriceList']:
                product = json.loads(price_item)
                
                # Extract pricing based on term type
                if term_type == 'OnDemand':
                    on_demand = product.get('terms', {}).get('OnDemand', {})
                    for term_sku, term_data in on_demand.items():
                        price_dimensions = term_data.get('priceDimensions', {})
                        for dim_key, dim_data in price_dimensions.items():
                            price_per_unit = dim_data.get('pricePerUnit', {}).get('USD')
                            if price_per_unit:
                                return float(price_per_unit)
                
                elif term_type in ['Reserved1Yr', 'Reserved3Yr']:
                    reserved = product.get('terms', {}).get('Reserved', {})
                    lease_term = '1yr' if term_type == 'Reserved1Yr' else '3yr'
                    
                    for term_sku, term_data in reserved.items():
                        term_attrs = term_data.get('termAttributes', {})
                        if term_attrs.get('LeaseContractLength', '').lower() == lease_term:
                            price_dimensions = term_data.get('priceDimensions', {})
                            # Get hourly price (not upfront)
                            for dim_key, dim_data in price_dimensions.items():
                                if 'Hrs' in dim_data.get('unit', ''):
                                    price_per_unit = dim_data.get('pricePerUnit', {}).get('USD')
                                    if price_per_unit:
                                        return float(price_per_unit)
            
            return None
            
        except Exception as e:
            print(f"Error fetching AWS pricing: {e}")
            return None
    
    @lru_cache(maxsize=32)
    def get_redshift_serverless_pricing(self, region: str = 'us-east-1') -> Optional[float]:
        """
        Get Redshift Serverless RPU-hour pricing for a region.
        
        Args:
            region: AWS region code
        
        Returns:
            Price per RPU-hour in USD, or None if not found
        """
        try:
            region_map = {
                'us-east-1': 'US East (N. Virginia)',
                'us-east-2': 'US East (Ohio)',
                'us-west-1': 'US West (N. California)',
                'us-west-2': 'US West (Oregon)',
                'eu-west-1': 'EU (Ireland)',
                'eu-central-1': 'EU (Frankfurt)',
                'ap-south-1': 'Asia Pacific (Mumbai)',
                'ap-southeast-1': 'Asia Pacific (Singapore)',
                'ap-southeast-2': 'Asia Pacific (Sydney)',
                'ap-northeast-1': 'Asia Pacific (Tokyo)',
            }
            
            location = region_map.get(region, 'US East (N. Virginia)')
            
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonRedshift'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Serverless'},
            ]
            
            response = self.pricing_client.get_products(
                ServiceCode='AmazonRedshift',
                Filters=filters,
                MaxResults=10
            )
            
            if not response.get('PriceList'):
                return None
            
            for price_item in response['PriceList']:
                product = json.loads(price_item)
                on_demand = product.get('terms', {}).get('OnDemand', {})
                
                for term_sku, term_data in on_demand.items():
                    price_dimensions = term_data.get('priceDimensions', {})
                    for dim_key, dim_data in price_dimensions.items():
                        # Look for RPU-hour pricing
                        if 'RPU' in dim_data.get('description', ''):
                            price_per_unit = dim_data.get('pricePerUnit', {}).get('USD')
                            if price_per_unit:
                                return float(price_per_unit)
            
            return None
            
        except Exception as e:
            print(f"Error fetching Redshift Serverless pricing: {e}")
            return None
    
    @lru_cache(maxsize=32)
    def get_managed_storage_pricing(self, region: str = 'us-east-1') -> Optional[float]:
        """
        Get Redshift Managed Storage (RMS) pricing per GB-month.
        
        Args:
            region: AWS region code
        
        Returns:
            Price per GB-month in USD, or None if not found
        """
        try:
            region_map = {
                'us-east-1': 'US East (N. Virginia)',
                'us-east-2': 'US East (Ohio)',
                'us-west-1': 'US West (N. California)',
                'us-west-2': 'US West (Oregon)',
                'eu-west-1': 'EU (Ireland)',
                'eu-central-1': 'EU (Frankfurt)',
                'ap-south-1': 'Asia Pacific (Mumbai)',
                'ap-southeast-1': 'Asia Pacific (Singapore)',
                'ap-southeast-2': 'Asia Pacific (Sydney)',
                'ap-northeast-1': 'Asia Pacific (Tokyo)',
            }
            
            location = region_map.get(region, 'US East (N. Virginia)')
            
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonRedshift'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'},
            ]
            
            response = self.pricing_client.get_products(
                ServiceCode='AmazonRedshift',
                Filters=filters,
                MaxResults=10
            )
            
            if not response.get('PriceList'):
                return None
            
            for price_item in response['PriceList']:
                product = json.loads(price_item)
                on_demand = product.get('terms', {}).get('OnDemand', {})
                
                for term_sku, term_data in on_demand.items():
                    price_dimensions = term_data.get('priceDimensions', {})
                    for dim_key, dim_data in price_dimensions.items():
                        # Look for managed storage pricing
                        if 'Managed Storage' in dim_data.get('description', ''):
                            price_per_unit = dim_data.get('pricePerUnit', {}).get('USD')
                            if price_per_unit:
                                return float(price_per_unit)
            
            return None
            
        except Exception as e:
            print(f"Error fetching managed storage pricing: {e}")
            return None
