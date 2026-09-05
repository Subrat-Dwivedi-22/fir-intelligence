variable "aws_region" {
  description = "AWS region where the FIR infrastructure will run."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
}