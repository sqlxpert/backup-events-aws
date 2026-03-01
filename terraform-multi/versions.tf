# Cross-account, cross-region backups with AWS Backup and EventBridge
# github.com/sqlxpert/backup-events-aws  GPLv3  Copyright Paul Marcelin

terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0.0"
    }
  }
}
