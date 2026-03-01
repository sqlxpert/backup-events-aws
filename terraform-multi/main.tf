# Cross-account, cross-region backups with AWS Backup and EventBridge
# github.com/sqlxpert/backup-events-aws  GPLv3  Copyright Paul Marcelin



data "aws_region" "backup_events_stackset" {
  for_each = toset(coalescelist(
    var.backup_events_stackset_regions,
    [local.region]
  ))

  region = each.key
}



data "aws_organizations_organization" "current" {}
data "aws_organizations_organizational_unit" "backup_events_stackset" {
  for_each = toset(var.backup_events_stackset_organizational_unit_names)

  parent_id = data.aws_organizations_organization.current.roots[0].id
  name      = each.key
}



resource "aws_s3_bucket" "backup_events_cloudformation" {
  force_destroy = true

  region = local.region

  tags = local.backup_events_tags
}

resource "aws_s3_bucket_versioning" "backup_events_cloudformation" {
  bucket = aws_s3_bucket.backup_events_cloudformation.bucket
  region = local.region

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "backup_events_cloudformation" {
  bucket = aws_s3_bucket.backup_events_cloudformation.bucket
  region = local.region

  ignore_public_acls = true
  block_public_acls  = true

  restrict_public_buckets = true
  block_public_policy     = true
}

resource "aws_s3_bucket_ownership_controls" "backup_events_cloudformation" {
  bucket = aws_s3_bucket.backup_events_cloudformation.bucket
  region = local.region

  rule {
    object_ownership = "BucketOwnerEnforced" # Disable S3 ACLs
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backup_events_cloudformation" {
  bucket = aws_s3_bucket.backup_events_cloudformation.bucket
  region = local.region

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # S3-managed keys
    }
  }
}

resource "aws_s3_object" "backup_events_cloudformation" {
  bucket = aws_s3_bucket.backup_events_cloudformation.bucket
  region = local.region

  depends_on = [
    aws_s3_bucket_versioning.backup_events_cloudformation,
    aws_s3_bucket_public_access_block.backup_events_cloudformation,
    aws_s3_bucket_ownership_controls.backup_events_cloudformation,
    aws_s3_bucket_server_side_encryption_configuration.backup_events_cloudformation,
  ]

  key = "backup_events_aws.yaml"

  source = "${local.cloudformation_path}/backup_events_aws.yaml"
  etag   = filemd5("${local.cloudformation_path}/backup_events_aws.yaml")
  # A template change will yield a new S3 object version.

  tags = local.backup_events_tags
}



# Both aws_cloudformation_stack_set_instance and aws_cloudformation_stack_set
# need operation_preferences . Updating aws_cloudformation_stack_set.parameters
# affects all StackSet instances.

resource "aws_cloudformation_stack_set" "backup_events" {
  name = "BackupEvents${var.backup_events_stackset_name_suffix}"

  template_url = join("", [
    "https://${aws_s3_bucket.backup_events_cloudformation.bucket_regional_domain_name}/",
    aws_s3_object.backup_events_cloudformation.key,
    "?versionId=${aws_s3_object.backup_events_cloudformation.version_id}"
  ])

  region = local.region

  call_as          = var.backup_events_stackset_call_as
  permission_model = "SERVICE_MANAGED"
  capabilities     = ["CAPABILITY_IAM"]

  operation_preferences {
    region_order            = sort(keys(data.aws_region.backup_events_stackset))
    region_concurrency_type = "PARALLEL"
    max_concurrent_count    = 2
    failure_tolerance_count = 2
  }

  auto_deployment {
    enabled = false
  }

  parameters = var.backup_events_stackset_params

  tags = local.backup_events_tags

  timeouts {
    update = "4h"
  }

  lifecycle {
    ignore_changes = [
      administration_role_arn,
      operation_preferences[0].region_order,
    ]
  }
}

resource "aws_cloudformation_stack_set_instance" "backup_events" {
  for_each = data.aws_region.backup_events_stackset

  stack_set_name = aws_cloudformation_stack_set.backup_events.name

  call_as = var.backup_events_stackset_call_as

  operation_preferences {
    region_order            = sort(keys(data.aws_region.backup_events_stackset))
    region_concurrency_type = "PARALLEL"
    max_concurrent_count    = 2
    failure_tolerance_count = 2
  }

  stack_set_instance_region = each.value.region
  deployment_targets {
    organizational_unit_ids = sort(
      var.backup_events_stackset_organizational_unit_ids
    )
  }
  retain_stack = false

  timeouts {
    create = "4h"
    update = "4h"
    delete = "4h"
  }

  lifecycle {
    ignore_changes = [
      operation_preferences[0].region_order,
    ]
  }
}
