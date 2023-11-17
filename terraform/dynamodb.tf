resource "aws_dynamodb_table" "shim_service_session" {
  name             = "ShimServiceSession"
  hash_key         = "tenantId"
  billing_mode     = "PAY_PER_REQUEST"
  range_key        = "sessionId"
  stream_enabled   = true
  stream_view_type = "KEYS_ONLY"

  attribute {
    name = "tenantId"
    type = "N"
  }

  attribute {
    name = "sessionId"
    type = "S"
  }

  ttl {
    attribute_name = "expireTime"
    enabled        = true
  }

}

resource "aws_dynamodb_table" "shim_service_virtual_range_table" {
  name         = "ShimServiceVirtualRangeTable"
  hash_key     = "hashKey"
  billing_mode = "PAY_PER_REQUEST"
  range_key    = "rangeKey"

  attribute {
    name = "hashKey"
    type = "S"
  }

  attribute {
    name = "rangeKey"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  global_secondary_index {
    name            = "scan-index"
    projection_type = "KEYS_ONLY"
    hash_key        = "sk"
    write_capacity  = 0
    read_capacity   = 0
  }

  ttl {
    attribute_name = "expireTime"
    enabled        = true
  }

}

resource "aws_dynamodb_table" "shim_service_event" {
  name         = "ShimServiceEvent"
  hash_key     = "tenantId"
  billing_mode = "PAY_PER_REQUEST"
  range_key    = "seqNo"

  attribute {
    name = "tenantId"
    type = "N"
  }

  attribute {
    name = "seqNo"
    type = "N"
  }
}

resource "aws_dynamodb_table" "shim_service_virtual_table" {
  name         = "ShimServiceVirtualTable"
  hash_key     = "hashKey"
  billing_mode = "PAY_PER_REQUEST"

  attribute {
    name = "hashKey"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  global_secondary_index {
    name            = "scan-index"
    projection_type = "KEYS_ONLY"
    hash_key        = "sk"
    write_capacity  = 0
    read_capacity   = 0
  }

  ttl {
    attribute_name = "expireTime"
    enabled        = true
  }

}
