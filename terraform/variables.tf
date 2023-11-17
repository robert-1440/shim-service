variable "rest_api_suffix" {
  type        = string
  default     = ""
  description = "Suffix to use for API Gateway name."
}

variable "aws_region" {
  type        = string
  default     = "us-west-1"
  description = "The AWS region"
}

variable "web_lambda_memory_size" {
  type        = number
  default     = 1024
  description = "Memory size to allocate for web lambda (in megabytes)"
}

variable "scheduler_lambda_memory_size" {
  type        = number
  default     = 512
  description = "Memory size to allocate for scheduler lambda (in megabytes)"
}

variable "table_listener_lambda_memory_size" {
  type        = number
  default     = 512
  description = "Memory size to allocate for table listener lambda (in megabytes)"
}

variable "live_agent_poller_lambda_memory_size" {
  type        = number
  default     = 1024
  description = "Memory size to allocate for the live agent poller lambda (in megabytes)"
}

variable "notification_publisher_lambda_memory_size" {
  type        = number
  default     = 1024
  description = "Memory size to allocate for the notification publisher lambda (in megabytes)"
}

variable "domain_name" {
  type        = string
  description = "The domain name to use."
}

variable "cert_arn" {
  type        = string
  description = "The ARN of the ACM certificate to use for API Gateway."
}
