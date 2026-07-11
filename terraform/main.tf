# Alibaba Cloud Infrastructure — On-Call Autopilot
# Usage: terraform init && terraform apply -var="access_key=xxx" -var="secret_key=xxx"

terraform {
  required_version = ">= 1.0"
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.230"
    }
  }
}

provider "alicloud" {
  access_key = var.access_key
  secret_key = var.secret_key
  region     = var.region
}

variable "access_key" {
  type        = string
  sensitive   = true
}

variable "secret_key" {
  type        = string
  sensitive   = true
}

variable "region" {
  type    = string
  default = "ap-southeast-1"
}

variable "ecs_password" {
  type      = string
  sensitive = true
}

# ── VPC + VSwitch (auto-zone) ──
resource "alicloud_vpc" "main" {
  vpc_name   = "oncall-autopilot-vpc"
  cidr_block = "10.0.0.0/16"
}

data "alicloud_zones" "default" {
  available_resource_creation = "VSwitch"
}

resource "alicloud_vswitch" "main" {
  vpc_id       = alicloud_vpc.main.id
  cidr_block   = "10.0.1.0/24"
  zone_id      = data.alicloud_zones.default.zones[0].id
  vswitch_name = "oncall-vswitch"
}

# ── Security Group ──
resource "alicloud_security_group" "main" {
  security_group_name = "oncall-autopilot-sg"
  description          = "Security group for On-Call Autopilot"
  vpc_id              = alicloud_vpc.main.id
}

resource "alicloud_security_group_rule" "ssh" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "22/22"
  priority          = 1
  security_group_id = alicloud_security_group.main.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_security_group_rule" "agent" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "8080/8080"
  priority          = 1
  security_group_id = alicloud_security_group.main.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_security_group_rule" "demo" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "3000/3000"
  priority          = 1
  security_group_id = alicloud_security_group.main.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_security_group_rule" "http" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "80/80"
  priority          = 1
  security_group_id = alicloud_security_group.main.id
  cidr_ip           = "0.0.0.0/0"
}

# ── ECS Instance ──
data "alicloud_images" "ubuntu" {
  name_regex  = "^ubuntu_22"
  most_recent = true
  owners      = "system"
}

data "alicloud_instance_types" "default" {
  cpu_core_count       = 2
  memory_size          = 4
  availability_zone    = data.alicloud_zones.default.zones[0].id
  system_disk_category = "cloud_essd"
}

resource "alicloud_instance" "app" {
  instance_name              = "oncall-autopilot-ecs"
  host_name                  = "oncall-autopilot"
  instance_type              = data.alicloud_instance_types.default.instance_types[0].id
  image_id                   = data.alicloud_images.ubuntu.images[0].id
  vswitch_id                 = alicloud_vswitch.main.id
  security_groups            = [alicloud_security_group.main.id]
  internet_max_bandwidth_out = 10
  internet_charge_type       = "PayByTraffic"
  password                   = var.ecs_password
  system_disk_category       = "cloud_essd"
  system_disk_size           = 40

  user_data = base64encode(<<-EOF
    #!/bin/bash
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker && systemctl start docker
    apt-get update && apt-get install -y docker-compose-plugin git
  EOF
  )
}

# ── Outputs ──
output "ecs_public_ip" {
  value       = alicloud_instance.app.public_ip
  description = "ECS public IP"
}

output "dashboard_url" {
  value       = "http://${alicloud_instance.app.public_ip}:8080/dashboard"
  description = "Agent dashboard URL"
}

output "ssh_command" {
  value       = "ssh root@${alicloud_instance.app.public_ip}"
  description = "SSH into the instance"
}
