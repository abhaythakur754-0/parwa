# EU Region Main Terraform Configuration
# Region: eu-west-1 (Ireland)
# Compliance: GDPR

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "parwa-terraform-state-eu"
    key            = "eu-west-1/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "parwa-terraform-locks-eu"
  }
}

# EU Provider Configuration
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "PARWA"
      Environment = var.environment
      Region      = "EU"
      Compliance  = "GDPR"
      ManagedBy   = "Terraform"
    }
  }
}

# EU VPC Configuration
resource "aws_vpc" "eu_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.project_name}-eu-vpc"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
  }
}

# EU Public Subnets
resource "aws_subnet" "eu_public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.eu_vpc.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.eu_azs.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name        = "${var.project_name}-eu-public-${count.index + 1}"
    Type        = "Public"
    Region      = "EU"
    Compliance  = "GDPR"
  }
}

# EU Private Subnets
resource "aws_subnet" "eu_private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.eu_vpc.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.eu_azs.names[count.index]

  tags = {
    Name        = "${var.project_name}-eu-private-${count.index + 1}"
    Type        = "Private"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
  }
}

# EU Database Subnets
resource "aws_subnet" "eu_database" {
  count             = length(var.database_subnet_cidrs)
  vpc_id            = aws_vpc.eu_vpc.id
  cidr_block        = var.database_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.eu_azs.names[count.index]

  tags = {
    Name        = "${var.project_name}-eu-database-${count.index + 1}"
    Type        = "Database"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
  }
}

# Availability Zones Data
data "aws_availability_zones" "eu_azs" {
  state = "available"
}

# EU Internet Gateway
resource "aws_internet_gateway" "eu_igw" {
  vpc_id = aws_vpc.eu_vpc.id

  tags = {
    Name        = "${var.project_name}-eu-igw"
    Region      = "EU"
    Compliance  = "GDPR"
  }
}

# EU NAT Gateway EIP
resource "aws_eip" "eu_nat_eip" {
  count  = var.enable_nat_gateway ? 1 : 0
  domain = "vpc"

  tags = {
    Name        = "${var.project_name}-eu-nat-eip"
    Region      = "EU"
    Compliance  = "GDPR"
  }
}

# EU NAT Gateway
resource "aws_nat_gateway" "eu_nat" {
  count         = var.enable_nat_gateway ? 1 : 0
  allocation_id = aws_eip.eu_nat_eip[0].id
  subnet_id     = aws_subnet.eu_public[0].id

  tags = {
    Name        = "${var.project_name}-eu-nat"
    Region      = "EU"
    Compliance  = "GDPR"
  }

  depends_on = [aws_internet_gateway.eu_igw]
}

# EU Public Route Table
resource "aws_route_table" "eu_public" {
  vpc_id = aws_vpc.eu_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.eu_igw.id
  }

  tags = {
    Name        = "${var.project_name}-eu-public-rt"
    Region      = "EU"
    Compliance  = "GDPR"
  }
}

# EU Private Route Table
resource "aws_route_table" "eu_private" {
  count  = var.enable_nat_gateway ? 1 : 0
  vpc_id = aws_vpc.eu_vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.eu_nat[0].id
  }

  tags = {
    Name        = "${var.project_name}-eu-private-rt"
    Region      = "EU"
    Compliance  = "GDPR"
  }
}

# Route Table Associations - Public
resource "aws_route_table_association" "eu_public" {
  count          = length(var.public_subnet_cidrs)
  subnet_id      = aws_subnet.eu_public[count.index].id
  route_table_id = aws_route_table.eu_public.id
}

# Route Table Associations - Private
resource "aws_route_table_association" "eu_private" {
  count          = var.enable_nat_gateway ? length(var.private_subnet_cidrs) : 0
  subnet_id      = aws_subnet.eu_private[count.index].id
  route_table_id = aws_route_table.eu_private[0].id
}

# EU Security Group - Application
resource "aws_security_group" "eu_app_sg" {
  name        = "${var.project_name}-eu-app-sg"
  description = "Security group for EU application servers (GDPR compliant)"
  vpc_id      = aws_vpc.eu_vpc.id

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
    Name        = "${var.project_name}-eu-app-sg"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
  }
}

# EU Security Group - Database
resource "aws_security_group" "eu_db_sg" {
  name        = "${var.project_name}-eu-db-sg"
  description = "Security group for EU database (GDPR compliant)"
  vpc_id      = aws_vpc.eu_vpc.id

  ingress {
    description     = "PostgreSQL from app"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.eu_app_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-eu-db-sg"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
  }
}

# EU Security Group - Redis
resource "aws_security_group" "eu_redis_sg" {
  name        = "${var.project_name}-eu-redis-sg"
  description = "Security group for EU Redis (GDPR compliant)"
  vpc_id      = aws_vpc.eu_vpc.id

  ingress {
    description     = "Redis from app"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.eu_app_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-eu-redis-sg"
    Region      = "EU"
    Compliance  = "GDPR"
    DataClass   = "EU-RESTRICTED"
  }
}

# VPC Flow Logs for GDPR Audit
resource "aws_flow_log" "eu_vpc_flow_log" {
  iam_role_arn    = aws_iam_role.vpc_flow_log_role.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow_log.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.eu_vpc.id

  tags = {
    Name        = "${var.project_name}-eu-vpc-flow-log"
    Region      = "EU"
    Compliance  = "GDPR"
  }
}

resource "aws_cloudwatch_log_group" "vpc_flow_log" {
  name              = "/aws/vpc-flow-logs/eu"
  retention_in_days = 90

  tags = {
    Name        = "${var.project_name}-eu-vpc-flow-log-group"
    Region      = "EU"
    Compliance  = "GDPR"
  }
}

resource "aws_iam_role" "vpc_flow_log_role" {
  name = "${var.project_name}-eu-vpc-flow-log-role"

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
  name = "${var.project_name}-eu-vpc-flow-log-policy"
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
output "eu_vpc_id" {
  description = "EU VPC ID"
  value       = aws_vpc.eu_vpc.id
}

output "eu_public_subnet_ids" {
  description = "EU public subnet IDs"
  value       = aws_subnet.eu_public[*].id
}

output "eu_private_subnet_ids" {
  description = "EU private subnet IDs"
  value       = aws_subnet.eu_private[*].id
}

output "eu_database_subnet_ids" {
  description = "EU database subnet IDs"
  value       = aws_subnet.eu_database[*].id
}

output "eu_app_security_group_id" {
  description = "EU application security group ID"
  value       = aws_security_group.eu_app_sg.id
}

output "eu_db_security_group_id" {
  description = "EU database security group ID"
  value       = aws_security_group.eu_db_sg.id
}

output "eu_redis_security_group_id" {
  description = "EU Redis security group ID"
  value       = aws_security_group.eu_redis_sg.id
}
