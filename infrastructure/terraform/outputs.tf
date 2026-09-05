output "worker_ecr_repository_url" {
  description = "ECR repository URL for the FIR worker."
  value       = aws_ecr_repository.worker.repository_url
}

output "worker_queue_url" {
  description = "SQS queue URL for the FIR worker."
  value       = aws_sqs_queue.worker.url
}

output "worker_queue_arn" {
  description = "SQS queue ARN for the FIR worker."
  value       = aws_sqs_queue.worker.arn
}

output "worker_vpc_id" {
  description = "VPC ID for the FIR worker."
  value       = aws_vpc.worker.id
}

output "worker_subnet_ids" {
  description = "Public subnet IDs for the FIR worker."
  value       = aws_subnet.worker[*].id
}

output "worker_dlq_url" {
  description = "Dead letter queue URL for failed FIR jobs."
  value       = aws_sqs_queue.worker_dlq.url
}

output "worker_dlq_arn" {
  description = "Dead letter queue ARN for failed FIR jobs."
  value       = aws_sqs_queue.worker_dlq.arn
}