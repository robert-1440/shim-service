resource "aws_sqs_queue" "push_notification" {
  name                        = "mock-notification-queue.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
}

resource "aws_sqs_queue_policy" "push_notification" {
  queue_url = aws_sqs_queue.push_notification.id
  policy = <<POLICY
  {
   "Version": "2012-10-17",
   "Statement": [
    {
     "Effect": "Allow",
     "Principal": "*",
     "Sid": "First",
     "Action": [
      "sqs:DeleteMessage",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
      "sqs:SendMessage"
     ],
     "Resource": [
      "${aws_sqs_queue.push_notification.arn}"
     ]
    }
   ],
   "Id": "sqspolicy"
  }
  POLICY
}
