# VPN Module - Cross-Cloud VPN Connection
# Establishes secure VPN tunnel between AWS and GCP

variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_vpc_id" {
  type = string
}

variable "aws_subnet_id" {
  type = string
}

variable "gcp_vpc_name" {
  type = string
}

variable "gcp_project_id" {
  type = string
}

# AWS Customer Gateway
resource "aws_customer_gateway" "gcp" {
  bgp_asn    = 65000
  ip_address = google_compute_address.vpn_gateway.address
  type       = "ipsec.1"
  
  tags = {
    Name = "${var.project_name}-${var.environment}-gcp-cgw"
  }
}

# AWS Virtual Private Gateway
resource "aws_vpn_gateway" "main" {
  vpc_id = var.aws_vpc_id
  
  tags = {
    Name = "${var.project_name}-${var.environment}-vgw"
  }
}

# AWS VPN Connection
resource "aws_vpn_connection" "gcp" {
  vpn_gateway_id      = aws_vpn_gateway.main.id
  customer_gateway_id = aws_customer_gateway.gcp.id
  type                = "ipsec.1"
  static_routes_only  = true
  
  tags = {
    Name = "${var.project_name}-${var.environment}-vpn-to-gcp"
  }
}

# AWS VPN Connection Route
resource "aws_vpn_connection_route" "gcp" {
  destination_cidr_block = "10.1.0.0/16"  # GCP VPC CIDR
  vpn_connection_id      = aws_vpn_connection.gcp.id
}

# GCP VPN Gateway
resource "google_compute_vpn_gateway" "aws" {
  name    = "${var.project_name}-${var.environment}-vpn-gateway"
  network = var.gcp_vpc_name
  region  = "us-central1"
}

# GCP External IP for VPN
resource "google_compute_address" "vpn_gateway" {
  name   = "${var.project_name}-${var.environment}-vpn-ip"
  region = "us-central1"
}

# GCP Forwarding Rules for VPN
resource "google_compute_forwarding_rule" "esp" {
  name        = "${var.project_name}-${var.environment}-vpn-esp"
  ip_protocol = "ESP"
  ip_address  = google_compute_address.vpn_gateway.address
  target      = google_compute_vpn_gateway.aws.id
  region      = "us-central1"
}

resource "google_compute_forwarding_rule" "udp500" {
  name        = "${var.project_name}-${var.environment}-vpn-udp500"
  ip_protocol = "UDP"
  port_range  = "500"
  ip_address  = google_compute_address.vpn_gateway.address
  target      = google_compute_vpn_gateway.aws.id
  region      = "us-central1"
}

resource "google_compute_forwarding_rule" "udp4500" {
  name        = "${var.project_name}-${var.environment}-vpn-udp4500"
  ip_protocol = "UDP"
  port_range  = "4500"
  ip_address  = google_compute_address.vpn_gateway.address
  target      = google_compute_vpn_gateway.aws.id
  region      = "us-central1"
}

# GCP VPN Tunnels (2 for redundancy)
resource "google_compute_vpn_tunnel" "tunnel1" {
  name          = "${var.project_name}-${var.environment}-tunnel1"
  peer_ip       = aws_vpn_connection.gcp.tunnel1_address
  shared_secret = aws_vpn_connection.gcp.tunnel1_preshared_key
  
  target_vpn_gateway = google_compute_vpn_gateway.aws.id
  
  local_traffic_selector  = ["10.1.0.0/16"]
  remote_traffic_selector = ["10.0.0.0/16"]
  
  region = "us-central1"
  
  depends_on = [
    google_compute_forwarding_rule.esp,
    google_compute_forwarding_rule.udp500,
    google_compute_forwarding_rule.udp4500,
  ]
}

resource "google_compute_vpn_tunnel" "tunnel2" {
  name          = "${var.project_name}-${var.environment}-tunnel2"
  peer_ip       = aws_vpn_connection.gcp.tunnel2_address
  shared_secret = aws_vpn_connection.gcp.tunnel2_preshared_key
  
  target_vpn_gateway = google_compute_vpn_gateway.aws.id
  
  local_traffic_selector  = ["10.1.0.0/16"]
  remote_traffic_selector = ["10.0.0.0/16"]
  
  region = "us-central1"
  
  depends_on = [
    google_compute_forwarding_rule.esp,
    google_compute_forwarding_rule.udp500,
    google_compute_forwarding_rule.udp4500,
  ]
}

# GCP Routes for VPN
resource "google_compute_route" "vpn_route1" {
  name       = "${var.project_name}-${var.environment}-vpn-route1"
  network    = var.gcp_vpc_name
  dest_range = "10.0.0.0/16"  # AWS VPC CIDR
  priority   = 1000
  
  next_hop_vpn_tunnel = google_compute_vpn_tunnel.tunnel1.id
}

resource "google_compute_route" "vpn_route2" {
  name       = "${var.project_name}-${var.environment}-vpn-route2"
  network    = var.gcp_vpc_name
  dest_range = "10.0.0.0/16"  # AWS VPC CIDR
  priority   = 1001
  
  next_hop_vpn_tunnel = google_compute_vpn_tunnel.tunnel2.id
}

# Outputs
output "tunnel_status" {
  description = "VPN tunnel configuration"
  value = {
    aws_vpn_connection_id = aws_vpn_connection.gcp.id
    gcp_tunnel1_name      = google_compute_vpn_tunnel.tunnel1.name
    gcp_tunnel2_name      = google_compute_vpn_tunnel.tunnel2.name
    vpn_gateway_ip        = google_compute_address.vpn_gateway.address
  }
}

output "aws_vpn_connection_id" {
  value = aws_vpn_connection.gcp.id
}

output "gcp_vpn_gateway_id" {
  value = google_compute_vpn_gateway.aws.id
}
