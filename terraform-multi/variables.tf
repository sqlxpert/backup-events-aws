# Cross-account, cross-region backups with AWS Backup and EventBridge
# github.com/sqlxpert/backup-events-aws  GPLv3  Copyright Paul Marcelin


variable "backup_events_stackset_name_suffix" {
  type        = string
  description = "Optional CloudFormation StackSet name suffix, for blue/green deployments or other scenarios in which multiple StackSets created from the same template are needed."

  default = ""
}



locals {
  backup_events_stackset_call_as_values = [
    "SELF",
    "DELEGATED_ADMIN"
  ]

  backup_events_stackset_call_as_values_string = join(
    " , ",
    local.backup_events_stackset_call_as_values
  )
}

variable "backup_events_stackset_call_as" {
  type        = string
  description = "The purpose of the AWS account from which the CloudFormation StackSet is being created: DELEGATED_ADMIN , or SELF for the management account."

  default = "SELF"

  validation {
    error_message = "value must be one of: ${local.backup_events_stackset_call_as_values_string} ."

    condition = contains(
      local.backup_events_stackset_call_as_values,
      var.backup_events_stackset_call_as
    )
  }
}



variable "backup_events_stackset_params" {
  type = object({
    BackupAccountId       = string
    BackupRegion          = string
    BackupRegionAlternate = string

    EnableCopy            = optional(bool, true)
    EnableUpdateLifecycle = optional(bool, true)

    NewDeleteAfterDays = optional(number, 7)

    CreateSampleVault = optional(bool, true)
    VaultCustomKmsKey = optional(string, "")
    VaultName         = optional(string, "BackupEvents-Sample")

    CopyRoleName = optional(string, "service-role/AWSBackupDefaultServiceRole")

    LogLevel                             = optional(string, "ERROR")
    LogRetentionInDays                   = optional(number, 7)
    ErrorQueueMessageRetentionPeriodSecs = optional(number, 604800)
    ErrorQueueAdditionalPolicyStatements = optional(string, "")
    UniqueNamePrefix                     = optional(string, "BackupEvents")
    CloudWatchLogsKmsKey                 = optional(string, "")
    SqsKmsKey                            = optional(string, "")

    CopyLambdaFnMemoryMB               = optional(number, 128)
    CopyLambdaFnTimeoutSecs            = optional(number, 30)
    UpdateLifecycleLambdaFnMemoryMB    = optional(number, 128)
    UpdateLifecycleLambdaFnTimeoutSecs = optional(number, 60)

    PlaceholderSuggestedStackName           = optional(string, "")
    PlaceholderSuggestedStackSetDescription = optional(string, "")
    PlaceholderHelp                         = optional(string, "")
    PlaceholderAdvancedParameters           = optional(string, "")

    # Repeat defaults from cloudformation/backup_events_aws.yaml

    # For a StackSet, we must cover all parameters here or in
    # aws_cloudformation_stack_set.lifecycle.ignore_changes
  })

  description = "Backup Events CloudFormation StackSet parameter map. Keys are parameter names from cloudformation/backup_events_aws.yaml ; parameters are described there. You must set BackupAccountId , BackupRegion and BackupRegionAlternate . CloudFormation and Terraform data types match, except for Boolean parameters. Terraform converts bool values to CloudFormation String values automatically. Follow Terraform string escape rules for double quotation marks, etc. inside ErrorQueueAdditionalPolicyStatements ."
}

variable "backup_events_tags" {
  type        = map(string)
  description = "Tag map for CloudFormation StackSet and other AWS resources. Keys, all optional, are tag keys. Values are tag values. This takes precedence over the Terraform AWS provider's default_tags and over tags attributes defined by the module. To remove tags defined by the module, set the terraform and source tags to null . Warnings: Each AWS service may have different rules for tag key and tag value lengths, characters, and disallowed tag key or tag value contents. CloudFormation propagates StackSet tags to stack instances and to resources. CloudFormation requires StackSet tag values to be at least 1 character long; empty tag values are not allowed."

  default = {}

  validation {
    error_message = "CloudFormation requires StackSet tag values to be at least 1 character long; empty tag values are not allowed."

    condition = alltrue([
      for value in values(var.backup_events_tags) : try(length(value) >= 1, true)
    ])
    # Use try to guard against length(null) . Allowing null is necessary here
    # as a means of preventing the setting of a given tag. The more explicit:
    #   (value == null) || (length(value) >= 1)
    # does not work with versions of Terraform released before 2024-12-16.
    # Error: Invalid value for "value" parameter: argument must not be null.
    # https://github.com/hashicorp/hcl/pull/713
  }
}



# You may wish to customize this interface. Beyond simply targeting a list of
# organizational units and a list of regions, CloudFormation supports a rich
# set of inputs for determining which AWS accounts to exclude and include, and
# lets you override StackSet parameters as necessary. See
# https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_CreateStackInstances.html
# https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_DeploymentTargets.html
# https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudformation_stack_set_instance#parameter_overrides-1

variable "backup_events_stackset_organizational_unit_names" {
  type        = list(string)
  description = "List of the names (not the IDs) of the organizational units in which to create instances of the CloudFormation StackSet. At least one is required. The organizational units must exist. Within a region, deployments will always proceed in alphabetical order by OU ID (not by name)."

  validation {
    error_message = "At least one organizational unit name is required."

    condition = length(var.backup_events_stackset_organizational_unit_names) >= 1
  }
}

variable "backup_events_stackset_regions" {
  type        = list(string)
  description = "List of region codes for the regions in which to create instances of the CloudFormation StackSet. The empty list causes the module to use backup_events_region . Initial deployment will proceed in alphabetical order by region code."

  default = []
}



variable "backup_events_region" {
  type        = string
  description = "Region code for the region from which to create the CloudFormation StackSet and in which to create supporting AWS resources such as an S3 bucket to hold the template. The empty string causes the module to use the default region configured for the Terraform AWS provider."

  default = ""
}
