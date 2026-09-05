# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------

resource "aws_vpc" "worker" {
  cidr_block           = "10.50.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "fir-intelligence-worker-vpc"
  }
}


# -----------------------------------------------------------------------------
# Internet Gateway
# -----------------------------------------------------------------------------

resource "aws_internet_gateway" "worker" {
  vpc_id = aws_vpc.worker.id

  tags = {
    Name = "fir-intelligence-worker-igw"
  }
}


# -----------------------------------------------------------------------------
# Availability Zones
# -----------------------------------------------------------------------------

data "aws_availability_zones" "available" {
  state = "available"
}


# -----------------------------------------------------------------------------
# Public Subnets
# -----------------------------------------------------------------------------

resource "aws_subnet" "worker" {
  count = 3

  vpc_id                  = aws_vpc.worker.id
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  cidr_block              = cidrsubnet("10.50.0.0/16", 8, count.index)
  map_public_ip_on_launch = true

  tags = {
    Name = "fir-worker-public-${count.index + 1}"
  }
}


# -----------------------------------------------------------------------------
# Public Route Table
# -----------------------------------------------------------------------------

resource "aws_route_table" "worker_public" {
  vpc_id = aws_vpc.worker.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.worker.id
  }

  tags = {
    Name = "fir-worker-public-rt"
  }
}


# -----------------------------------------------------------------------------
# Associate Subnets with Route Table
# -----------------------------------------------------------------------------

resource "aws_route_table_association" "worker_public" {
  count = 3

  subnet_id      = aws_subnet.worker[count.index].id
  route_table_id = aws_route_table.worker_public.id
}


# -----------------------------------------------------------------------------
# Security Group
# -----------------------------------------------------------------------------

resource "aws_security_group" "worker" {
  name        = "fir-intelligence-worker"
  description = "Security group for FIR intelligence Fargate workers"
  vpc_id      = aws_vpc.worker.id

  # Worker only needs outbound connectivity to:
  # - SQS
  # - S3
  # - MongoDB Atlas
  # - Gemini API
  egress {
    description = "Allow outbound internet traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "fir-intelligence-worker-sg"
  }
}