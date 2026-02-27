# Cross-account, cross-region backups with AWS Backup and EventBridge
# github.com/sqlxpert/backup-events-aws  GPLv3  Copyright Paul Marcelin

data "aws_region" "current" {}
locals {
  region = coalesce(
    var.backup_events_region,
    data.aws_region.current.region
  )
  # data.aws_region.region added,
  # data.aws_region.name marked deprecated
  # in Terraform AWS provider v6.0.0

  cloudformation_path = "${path.module}/cloudformation"

  module_directory = basename(path.module)
  backup_events_tags = merge(
    {
      terraform = "1"
      # CloudFormation stack tag values must be at least 1 character long!
      # https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_Tag.html#API_Tag_Contents

      source = "https://github.com/sqlxpert/backup-events-aws/blob/main/${local.module_directory}"
    },
    var.backup_events_tags,
  )
}


