output "campaign_uploads_bucket" {
  value = aws_s3_bucket.campaign_uploads.bucket
}

output "call_artifacts_bucket" {
  value = aws_s3_bucket.call_artifacts.bucket
}

output "dispatch_queue_url" {
  value = aws_sqs_queue.dispatch.url
}

output "outcome_queue_url" {
  value = aws_sqs_queue.outcome_delivery.url
}

output "crm_dlq_url" {
  value = aws_sqs_queue.crm_dlq.url
}
