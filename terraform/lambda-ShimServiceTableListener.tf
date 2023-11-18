resource "aws_iam_role" "shim_service_table_listener" {
  name = "lambda-ShimServiceTableListener"

  assume_role_policy = jsonencode({
   "Version": "2012-10-17",
   "Statement": [
    {
     "Effect": "Allow",
     "Principal": {
      "Service": "lambda.amazonaws.com"
     },
     "Action": "sts:AssumeRole"
    }
   ]
  })
}

data "aws_iam_policy_document" "shim_service_table_listener" {
  statement {
    effect    = "Allow"
    resources = [ "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/ShimServiceTableListener:*" ]
    actions   = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_sns_topic.shim_error.arn ]
    actions   = [
      "sns:Publish",
      "sns:ListSubscriptionsByTopic",
      "sns:GetSubscriptionAttributes",
      "sns:Subscribe",
      "sns:Unsubscribe"
    ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_dynamodb_table.shim_service_virtual_range_table.arn ]
    actions   = [ "dynamodb:BatchWriteItem" ]
  }

  statement {
    effect    = "Allow"
    resources = [ aws_dynamodb_table.shim_service_session.stream_arn ]
    actions   = [
      "dynamodb:GetRecords",
      "dynamodb:GetShardIterator",
      "dynamodb:DescribeStream",
      "dynamodb:ListStreams"
    ]
  }
}

resource "aws_iam_policy" "shim_service_table_listener" {
  policy = data.aws_iam_policy_document.shim_service_table_listener.json
}

resource "aws_iam_role_policy_attachment" "shim_service_table_listener" {
  policy_arn = aws_iam_policy.shim_service_table_listener.arn
  role       = aws_iam_role.shim_service_table_listener.name
}

resource "aws_lambda_function" "shim_service_table_listener" {
  function_name    = "ShimServiceTableListener"
  description      = "Shim Service Table Listener"
  handler          = "app.handler"
  timeout          = 90
  memory_size      = var.table_listener_lambda_memory_size
  filename         = "${path.module}/aws/resources/ShimServiceTableListener.zip"
  source_code_hash = filebase64sha256("${path.module}/aws/resources/ShimServiceTableListener.zip")
  layers           = [ aws_lambda_layer_version.common_layer.arn ]
  runtime          = "python3.11"
  role             = aws_iam_role.shim_service_table_listener.arn

  environment {
    variables = {
      ACTIVE_PROFILES = "table-listener"
      ERROR_TOPIC_ARN = "${aws_sns_topic.shim_error.arn}"
    }
  }
  depends_on = [ aws_iam_role_policy_attachment.shim_service_table_listener ]
}

resource "aws_cloudwatch_log_group" "shim_service_table_listener" {
  name              = "/aws/lambda/${aws_lambda_function.shim_service_table_listener.function_name}"
  retention_in_days = 30
}

resource "aws_lambda_event_source_mapping" "shim_service_table_listener_shim_service_session" {
  event_source_arn                   = aws_dynamodb_table.shim_service_session.stream_arn
  function_name                      = "ShimServiceTableListener"
  batch_size                         = 100
  maximum_batching_window_in_seconds = 60
  starting_position                  = "LATEST"
  maximum_retry_attempts             = 10
  depends_on = [ aws_lambda_function.shim_service_table_listener ]
}
