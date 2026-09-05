# -----------------------------------------------------------------------------
# ECS Application Auto Scaling Target
# -----------------------------------------------------------------------------

resource "aws_appautoscaling_target" "worker" {
  max_capacity       = 1
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.worker.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# -----------------------------------------------------------------------------
# Scale OUT Policy
# -----------------------------------------------------------------------------

resource "aws_appautoscaling_policy" "worker_scale_out" {
  name               = "fir-worker-scale-out"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 1
    }
  }
}

# -----------------------------------------------------------------------------
# Scale IN Policy
# -----------------------------------------------------------------------------

resource "aws_appautoscaling_policy" "worker_scale_in" {
  name               = "fir-worker-scale-in"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 120
    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = -1
    }
  }
}

# -----------------------------------------------------------------------------
# Scale OUT Alarm
# -----------------------------------------------------------------------------
#
# If at least one message is waiting in the queue, start one worker.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "worker_queue_has_messages" {
  alarm_name = "fir-worker-queue-has-messages"

  alarm_description = "Start FIR Fargate worker when messages are waiting."

  namespace   = "AWS/SQS"
  metric_name = "ApproximateNumberOfMessagesVisible"

  statistic = "Maximum"
  period    = 60

  evaluation_periods = 1

  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"

  dimensions = {
    QueueName = aws_sqs_queue.worker.name
  }

  alarm_actions = [
    aws_appautoscaling_policy.worker_scale_out.arn
  ]

  treat_missing_data = "notBreaching"
}

# -----------------------------------------------------------------------------
# Scale IN Alarm
# -----------------------------------------------------------------------------
#
# The queue is considered empty only when:
#
#   visible messages     = 0
#   in-flight messages   = 0
#
# This prevents ECS from scaling to zero while a worker is processing
# a message.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "worker_queue_empty" {
  alarm_name = "fir-worker-queue-empty"

  alarm_description = "Stop FIR Fargate worker when the SQS queue has no waiting or in-flight messages."

  comparison_operator = "LessThanOrEqualToThreshold"
  threshold           = 0

  evaluation_periods = 2

  # ---------------------------------------------------------------------------
  # Visible messages
  # ---------------------------------------------------------------------------

  metric_query {
    id          = "visible"
    return_data = false

    metric {
      metric_name = "ApproximateNumberOfMessagesVisible"
      namespace   = "AWS/SQS"

      period = 60
      stat   = "Maximum"

      dimensions = {
        QueueName = aws_sqs_queue.worker.name
      }
    }
  }

  # ---------------------------------------------------------------------------
  # In-flight messages
  # ---------------------------------------------------------------------------

  metric_query {
    id          = "not_visible"
    return_data = false

    metric {
      metric_name = "ApproximateNumberOfMessagesNotVisible"
      namespace   = "AWS/SQS"

      period = 60
      stat   = "Maximum"

      dimensions = {
        QueueName = aws_sqs_queue.worker.name
      }
    }
  }

  # ---------------------------------------------------------------------------
  # Total messages
  # ---------------------------------------------------------------------------
  #
  # Queue is empty only when:
  #
  #   visible + not_visible <= 0
  #
  # ---------------------------------------------------------------------------

  metric_query {
    id          = "total_messages"
    expression  = "visible + not_visible"
    label       = "Total SQS messages"
    return_data = true
  }

  alarm_actions = [
    aws_appautoscaling_policy.worker_scale_in.arn
  ]

  treat_missing_data = "notBreaching"
}