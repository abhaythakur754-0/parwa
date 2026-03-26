# APAC Region Main Terraform Configuration
# Region: ap-southeast-1 (Singapore)
# Compliance: Asian Data Laws

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "parwa-terraform-state-apac"
    key            = "ap-southeast-1/terraform.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    dynamodb_table = "parwa-terraform-locks-apac"
  }
}

# APAC Provider Configuration
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "PARWA"
      Environment = var.environment
      Region      = "APAC"
      Compliance  = "APAC-DATA-LAWS"
      ManagedBy   = "Terraform"
    }
  }
}

# APAC VPC Configuration
resource "aws_vpc" "apac_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.project_name}-apac-vpc"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
  }
}

# APAC Public Subnets
resource "aws_subnet" "apac_public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.apac_vpc.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.apac_azs.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name        = "${var.project_name}-apac-public-${count.index + 1}"
    Type        = "Public"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
  }
}

# APAC Private Subnets
resource "aws_subnet" "apac_private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.apac_vpc.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.apac_azs.names[count.index]

  tags = {
    Name        = "${var.project_name}-apac-private-${count.index + 1}"
    Type        = "Private"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
  }
}

# APAC Database Subnets
resource "aws_subnet" "apac_database" {
  count             = length(var.database_subnet_cidrs)
  vpc_id            = aws_vpc.apac_vpc.id
  cidr_block        = var.database_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.apac_azs.names[count.index]

  tags = {
    Name        = "${var.project_name}-apac-database-${count.index + 1}"
    Type        = "Database"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
  }
}

# Availability Zones Data
data "aws_availability_zones" "apac_azs" {
  state = "available"
}

# APAC Internet Gateway
resource "aws_internet_gateway" "apac_igw" {
  vpc_id = aws_vpc.apac_vpc.id

  tags = {
    Name        = "${var.project_name}-apac-igw"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
  }
}

# APAC NAT Gateway EIP
resource "aws_eip" "apac_nat_eip" {
  count  = var.enable_nat_gateway ? 1 : 0
  domain = "vpc"

  tags = {
    Name        = "${var.project_name}-apac-nat-eip"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
  }
}

# APAC NAT Gateway
resource "aws_nat_gateway" "apac_nat" {
  count         = var.enable_nat_gateway ? 1 : 0
  allocation_id = aws_eip.apac_nat_eip[0].id
  subnet_id     = aws_subnet.apac_public[0].id

  tags = {
    Name        = "${var.project_name}-apac-nat"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
  }

  depends_on = [aws_internet_gateway.apac_igw]
}

# APAC Public Route Table
resource "aws_route_table" "apac_public" {
  vpc_id = aws_vpc.apac_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.apac_igw.id
  }

  tags = {
    Name        = "${var.project_name}-apac-public-rt"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
  }
}

# APAC Private Route Table
resource "aws_route_table" "apac_private" {
  count  = var.enable_nat_gateway ? 1 : 0
  vpc_id = aws_vpc.apac_vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.apac_nat[0].id
  }

  tags = {
    Name        = "${var.project_name}-apac-private-rt"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
  }
}

# Route Table Associations - Public
resource "aws_route_table_association" "apac_public" {
  count          = length(var.public_subnet_cidrs)
  subnet_id      = aws_subnet.apac_public[count.index].id
  route_table_id = aws_route_table.apac_public.id
}

# Route Table Associations - Private
resource "aws_route_table_association" "apac_private" {
  count          = var.enable_nat_gateway ? length(var.private_subnet_cidrs) : 0
  subnet_id      = aws_subnet.apac_private[count.index].id
  route_table_id = aws_route_table.apac_private[0].id
}

# APAC Security Group - Application
resource "aws_security_group" "apac_app_sg" {
  name        = "${var.project_name}-apac-app-sg"
  description = "Security group for APAC application servers"
  vpc_id      = aws_vpc.apac_vpc.id

  ingress {
    description = "HTTPS from ALB"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "HTTP redirect"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-apac-app-sg"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
  }
}

# APAC Security Group - Database
resource "aws_security_group" "apac_db_sg" {
  name        = "${var.project_name}-apac-db-sg"
  description = "Security group for APAC database"
  vpc_id      = aws_vpc.apac_vpc.id

  ingress {
    description     = "PostgreSQL from app"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.apac_app_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-apac-db-sg"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
  }
}

# APAC Security Group - Redis
resource "aws_security_group" "apac_redis_sg" {
  name        = "${var.project_name}-apac-redis-sg"
  description = "Security group for APAC Redis"
  vpc_id      = aws_vpc.apac_vpc.id

  ingress {
    description     = "Redis from app"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.apac_app_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-apac-redis-sg"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
    DataClass   = "APAC-RESTRICTED"
  }
}

# VPC Flow Logs for Audit
resource "aws_flow_log" "apac_vpc_flow_log" {
  iam_role_arn    = aws_iam_role.vpc_flow_log_role.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow_log.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.apac_vpc.id

  tags = {
    Name        = "${var.project_name}-apac-vpc-flow-log"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
  }
}

resource "aws_cloudwatch_log_group" "vpc_flow_log" {
  name              = "/aws/vpc-flow-logs/apac"
  retention_in_days = 90

  tags = {
    Name        = "${var.project_name}-apac-vpc-flow-log-group"
    Region      = "APAC"
    Compliance  = "APAC-DATA-LAWS"
  }
}

resource "aws_iam_role" "vpc_flow_log_role" {
  name = "${var.project_name}-apac-vpc-flow-log-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "vpc_flow_log_policy" {
  name = "${var.project_name}-apac-vpc-flow-log-policy"
  role = aws_iam_role.vpc_flow_log_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# Outputs
output "apac_vpc_id" {
  description = "APAC VPC ID"
  value       = aws_vpc.apac_vpc.id
}

output "apac_public_subnet_ids" {
  description = "APAC public subnet IDs"
  value       = aws_subnet.apac_public[*].id
}

output "apac_private_subnet_ids" {
  description = "APAC private subnet IDs"
  value       = aws_subnet.apac_private[*].id
}

output "apac_database_subnet_ids" {
  description = "APAC database subnet IDs"
  value       = aws_subnet.apac_database[*].id
}

output "apac_app_security_group_id" {
  description = "APAC application security group ID"
  value       = aws_security_group.apac_app_sg.id
}

output "apac_db_security_group_id" {
  description = "APAC database security group ID"
  value       = aws_security_group.apac_db_sg.id
}

output "apac_redis_security_group_id" {
  description = "APAC Redis security group ID"
  value       = aws_security_group.apac_redis_sg.id
}
