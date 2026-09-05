# -----------------------------------------------------------------------------
# Dead Letter Queue
# -----------------------------------------------------------------------------

resource "aws_sqs_queue" "worker_dlq" {
  name = "fir-intelligence-worker-dlq"

  # Keep failed messages for 14 days.
  message_retention_seconds = 1209600

  receive_wait_time_seconds = 20

  tags = {
    Name = "fir-intelligence-worker-dlq"
  }
}


# -----------------------------------------------------------------------------
# FIR Worker Queue
# -----------------------------------------------------------------------------

resource "aws_sqs_queue" "worker" {
  name = "fir-intelligence-worker"

  # The FIR pipeline can be CPU/memory intensive.
  visibility_timeout_seconds = 960

  # Keep normal messages for 4 days.
  message_retention_seconds = 345600

  # Long polling reduces unnecessary SQS API calls.
  receive_wait_time_seconds = 20

  # After 3 failed processing attempts, move the message to the DLQ.
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.worker_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name = "fir-intelligence-worker"
  }
}