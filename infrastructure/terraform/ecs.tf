# -----------------------------------------------------------------------------
# ECS Cluster
# -----------------------------------------------------------------------------

resource "aws_ecs_cluster" "worker" {
  name = "fir-intelligence-worker"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "fir-intelligence-worker"
  }
}


# -----------------------------------------------------------------------------
# CloudWatch Log Group
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/fir-intelligence-worker"
  retention_in_days = 7

  tags = {
    Name = "fir-intelligence-worker"
  }
}


# -----------------------------------------------------------------------------
# Fargate Task Definition
# -----------------------------------------------------------------------------

resource "aws_ecs_task_definition" "worker" {
  family                   = "fir-intelligence-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  # 2 vCPU / 4 GB RAM
  #
  # We can increase this later if PaddleOCR requires more memory.
  cpu    = "2048"
  memory = "4096"

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.worker.arn

  container_definitions = jsonencode([
    {
      name      = "fir-worker"
      image     = "${aws_ecr_repository.worker.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "MONGODB_DATABASE"
          value = "criminal_intelligence"
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "S3_BUCKET"
          value = "fir-intelligence-documents"
        },
        {
          name  = "SQS_QUEUE_URL"
          value = aws_sqs_queue.worker.url
        },
        {
          name  = "MAX_FIR_SIZE_MB"
          value = "20"
        },
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
            name  = "GEMINI_MODEL"
            value = "gemini-3.5-flash-lite"
        },
      ]

      secrets = [
        {
          name      = "MONGODB_URI"
          valueFrom = aws_ssm_parameter.mongodb_uri.arn
        },
        {
          name      = "PERSON_ID_HMAC_SECRET"
          valueFrom = aws_ssm_parameter.person_id_hmac_secret.arn
        },
        {
          name      = "GEMINI_API_KEY"
          valueFrom = aws_ssm_parameter.gemini_api_key.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }

      # Give the worker time to gracefully finish/stop.
      stopTimeout = 120
    }
  ])

  tags = {
    Name = "fir-intelligence-worker"
  }
}


# -----------------------------------------------------------------------------
# ECS Service
# -----------------------------------------------------------------------------

resource "aws_ecs_service" "worker" {
  name            = "fir-intelligence-worker"
  cluster         = aws_ecs_cluster.worker.id
  task_definition = aws_ecs_task_definition.worker.arn

  # Start with zero workers.
  #
  # Autoscaling will later increase this to 1 when SQS contains work
  # and return it to 0 when the queue is empty.
  desired_count = 0

  launch_type = "FARGATE"

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  network_configuration {
    subnets          = aws_subnet.worker[*].id
    security_groups  = [aws_security_group.worker.id]
    assign_public_ip = true
  }

  # Autoscaling will control desired_count.
  lifecycle {
    ignore_changes = [
      desired_count
    ]
  }

  tags = {
    Name = "fir-intelligence-worker"
  }
}