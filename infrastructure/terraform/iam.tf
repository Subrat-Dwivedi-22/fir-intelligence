# -----------------------------------------------------------------------------
# Allow ECS to retrieve secrets from SSM Parameter Store
# -----------------------------------------------------------------------------

resource "aws_iam_policy" "ecs_secrets" {
  name        = "fir-intelligence-ecs-secrets"
  description = "Allows ECS tasks to retrieve FIR worker secrets from SSM"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "ssm:GetParameters",
          "ssm:GetParameter"
        ]

        Resource = [
          aws_ssm_parameter.mongodb_uri.arn,
          aws_ssm_parameter.person_id_hmac_secret.arn,
          aws_ssm_parameter.gemini_api_key.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_secrets" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.ecs_secrets.arn
}

# -----------------------------------------------------------------------------
# ECS Task Execution Role
# Used by ECS/Fargate itself to:
# - Pull the container image from ECR
# - Send container logs to CloudWatch
# -----------------------------------------------------------------------------

resource "aws_iam_role" "ecs_execution" {
  name = "fir-intelligence-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}


# -----------------------------------------------------------------------------
# ECS Task Role
# This is the identity of our actual worker application.
# -----------------------------------------------------------------------------

resource "aws_iam_role" "worker" {
  name = "fir-intelligence-worker"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}


# -----------------------------------------------------------------------------
# Worker Permissions
# -----------------------------------------------------------------------------

resource "aws_iam_policy" "worker" {
  name        = "fir-intelligence-worker"
  description = "Permissions required by the FIR ingestion Fargate worker"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [

      # Read uploaded FIR documents from the existing S3 bucket.
      {
        Effect = "Allow"

        Action = [
          "s3:GetObject"
        ]

        Resource = "arn:aws:s3:::fir-intelligence-documents/cases/*"
      },

      # Read basic bucket information if required by the application.
      {
        Effect = "Allow"

        Action = [
          "s3:GetBucketLocation"
        ]

        Resource = "arn:aws:s3:::fir-intelligence-documents"
      },

      # Consume messages from our NEW Terraform-managed queue.
      {
        Effect = "Allow"

        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes"
        ]

        Resource = aws_sqs_queue.worker.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "worker" {
  role       = aws_iam_role.worker.name
  policy_arn = aws_iam_policy.worker.arn
}