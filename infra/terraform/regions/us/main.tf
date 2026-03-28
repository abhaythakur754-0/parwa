# US Region Main Terraform Configuration
# Region: us-east-1 (N. Virginia)
# Compliance: CCPA

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "parwa-terraform-state-us"
    key            = "us-east-1/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "parwa-terraform-locks-us"
  }
}

# US Provider Configuration
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "PARWA"
      Environment = var.environment
      Region      = "US"
      Compliance  = "CCPA"
      ManagedBy   = "Terraform"
    }
  }
}

# US VPC Configuration
resource "aws_vpc" "us_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.project_name}-us-vpc"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
  }
}

# US Public Subnets
resource "aws_subnet" "us_public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.us_vpc.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.us_azs.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name        = "${var.project_name}-us-public-${count.index + 1}"
    Type        = "Public"
    Region      = "US"
    Compliance  = "CCPA"
  }
}

# US Private Subnets
resource "aws_subnet" "us_private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.us_vpc.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.us_azs.names[count.index]

  tags = {
    Name        = "${var.project_name}-us-private-${count.index + 1}"
    Type        = "Private"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
  }
}

# US Database Subnets
resource "aws_subnet" "us_database" {
  count             = length(var.database_subnet_cidrs)
  vpc_id            = aws_vpc.us_vpc.id
  cidr_block        = var.database_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.us_azs.names[count.index]

  tags = {
    Name        = "${var.project_name}-us-database-${count.index + 1}"
    Type        = "Database"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
  }
}

# Availability Zones Data
data "aws_availability_zones" "us_azs" {
  state = "available"
}

# US Internet Gateway
resource "aws_internet_gateway" "us_igw" {
  vpc_id = aws_vpc.us_vpc.id

  tags = {
    Name        = "${var.project_name}-us-igw"
    Region      = "US"
    Compliance  = "CCPA"
  }
}

# US NAT Gateway EIP
resource "aws_eip" "us_nat_eip" {
  count  = var.enable_nat_gateway ? 1 : 0
  domain = "vpc"

  tags = {
    Name        = "${var.project_name}-us-nat-eip"
    Region      = "US"
    Compliance  = "CCPA"
  }
}

# US NAT Gateway
resource "aws_nat_gateway" "us_nat" {
  count         = var.enable_nat_gateway ? 1 : 0
  allocation_id = aws_eip.us_nat_eip[0].id
  subnet_id     = aws_subnet.us_public[0].id

  tags = {
    Name        = "${var.project_name}-us-nat"
    Region      = "US"
    Compliance  = "CCPA"
  }

  depends_on = [aws_internet_gateway.us_igw]
}

# US Public Route Table
resource "aws_route_table" "us_public" {
  vpc_id = aws_vpc.us_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.us_igw.id
  }

  tags = {
    Name        = "${var.project_name}-us-public-rt"
    Region      = "US"
    Compliance  = "CCPA"
  }
}

# US Private Route Table
resource "aws_route_table" "us_private" {
  count  = var.enable_nat_gateway ? 1 : 0
  vpc_id = aws_vpc.us_vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.us_nat[0].id
  }

  tags = {
    Name        = "${var.project_name}-us-private-rt"
    Region      = "US"
    Compliance  = "CCPA"
  }
}

# Route Table Associations - Public
resource "aws_route_table_association" "us_public" {
  count          = length(var.public_subnet_cidrs)
  subnet_id      = aws_subnet.us_public[count.index].id
  route_table_id = aws_route_table.us_public.id
}

# Route Table Associations - Private
resource "aws_route_table_association" "us_private" {
  count          = var.enable_nat_gateway ? length(var.private_subnet_cidrs) : 0
  subnet_id      = aws_subnet.us_private[count.index].id
  route_table_id = aws_route_table.us_private[0].id
}

# US Security Group - Application
resource "aws_security_group" "us_app_sg" {
  name        = "${var.project_name}-us-app-sg"
  description = "Security group for US application servers (CCPA compliant)"
  vpc_id      = aws_vpc.us_vpc.id

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
    Name        = "${var.project_name}-us-app-sg"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
  }
}

# US Security Group - Database
resource "aws_security_group" "us_db_sg" {
  name        = "${var.project_name}-us-db-sg"
  description = "Security group for US database (CCPA compliant)"
  vpc_id      = aws_vpc.us_vpc.id

  ingress {
    description     = "PostgreSQL from app"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.us_app_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-us-db-sg"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
  }
}

# US Security Group - Redis
resource "aws_security_group" "us_redis_sg" {
  name        = "${var.project_name}-us-redis-sg"
  description = "Security group for US Redis (CCPA compliant)"
  vpc_id      = aws_vpc.us_vpc.id

  ingress {
    description     = "Redis from app"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.us_app_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-us-redis-sg"
    Region      = "US"
    Compliance  = "CCPA"
    DataClass   = "US-RESTRICTED"
  }
}

# VPC Flow Logs for CCPA Audit
resource "aws_flow_log" "us_vpc_flow_log" {
  iam_role_arn    = aws_iam_role.vpc_flow_log_role.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow_log.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.us_vpc.id

  tags = {
    Name        = "${var.project_name}-us-vpc-flow-log"
    Region      = "US"
    Compliance  = "CCPA"
  }
}

resource "aws_cloudwatch_log_group" "vpc_flow_log" {
  name              = "/aws/vpc-flow-logs/us"
  retention_in_days = 90

  tags = {
    Name        = "${var.project_name}-us-vpc-flow-log-group"
    Region      = "US"
    Compliance  = "CCPA"
  }
}

resource "aws_iam_role" "vpc_flow_log_role" {
  name = "${var.project_name}-us-vpc-flow-log-role"

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
  name = "${var.project_name}-us-vpc-flow-log-policy"
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
output "us_vpc_id" {
  description = "US VPC ID"
  value       = aws_vpc.us_vpc.id
}

output "us_public_subnet_ids" {
  description = "US public subnet IDs"
  value       = aws_subnet.us_public[*].id
}

output "us_private_subnet_ids" {
  description = "US private subnet IDs"
  value       = aws_subnet.us_private[*].id
}

output "us_database_subnet_ids" {
  description = "US database subnet IDs"
  value       = aws_subnet.us_database[*].id
}

output "us_app_security_group_id" {
  description = "US application security group ID"
  value       = aws_security_group.us_app_sg.id
}

output "us_db_security_group_id" {
  description = "US database security group ID"
  value       = aws_security_group.us_db_sg.id
}

output "us_redis_security_group_id" {
  description = "US Redis security group ID"
  value       = aws_security_group.us_redis_sg.id
}
