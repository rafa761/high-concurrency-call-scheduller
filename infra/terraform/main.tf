resource "aws_s3_bucket" "campaign_uploads" {
  bucket = "campaign-uploads"
}

resource "aws_s3_bucket" "call_artifacts" {
  bucket = "call-artifacts"
}

resource "aws_sqs_queue" "crm_dlq" {
  name = "crm-dlq"
}

resource "aws_sqs_queue" "dispatch" {
  name                       = "dispatch"
  visibility_timeout_seconds = 10
}

resource "aws_sqs_queue" "outcome_delivery" {
  name                       = "outcome-delivery"
  visibility_timeout_seconds = 5

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.crm_dlq.arn
    maxReceiveCount     = 4
  })
}
