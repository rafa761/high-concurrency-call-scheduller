data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ingestion" {
  name               = "ingestion-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_lambda_function" "ingestion" {
  function_name    = "ingestion"
  role             = aws_iam_role.ingestion.arn
  runtime          = "python3.13"
  handler          = "ingestion.handler.handler"
  filename         = "${path.module}/build/ingestion.zip"
  source_code_hash = filebase64sha256("${path.module}/build/ingestion.zip")
  timeout          = 300
  memory_size      = 1024

  environment {
    variables = {
      DATABASE_URL     = "postgresql://scheduler:scheduler@postgres:5432/scheduler"
      AWS_ENDPOINT_URL = "http://localstack:4566"
    }
  }
}

resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.campaign_uploads.arn
}

resource "aws_s3_bucket_notification" "campaign_uploads" {
  bucket = aws_s3_bucket.campaign_uploads.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.ingestion.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "campaigns/"
    filter_suffix       = ".csv"
  }

  depends_on = [aws_lambda_permission.allow_s3]
}
