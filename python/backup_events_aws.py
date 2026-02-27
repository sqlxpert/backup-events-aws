#!/usr/bin/env python3
"""Cross-account, cross-region backups with AWS Backup and EventBridge

github.com/sqlxpert/backup-events-aws  GPLv3  Copyright Paul Marcelin
"""

import os
import logging
import time
import json
import datetime
import botocore
import boto3

logger = logging.getLogger()
# Skip "credentials in environment" INFO message, unavoidable in AWS Lambda:
logging.getLogger("botocore").setLevel(logging.WARNING)

os.environ["TZ"] = "UTC"
time.tzset()
# See get_update_lifecycle_kwargs and lambda_handler_update_lifecycle

VAULT_NAME = os.environ["VAULT_NAME"]
COPY_ROLE_ARN = os.environ.get("COPY_ROLE_ARN", "")
AWS_PARTITION = os.environ.get("AWS_PARTITION", "")
BACKUP_ACCOUNT_ID = os.environ.get("BACKUP_ACCOUNT_ID", "")


def log(entry_type, entry_value, log_level=logging.INFO):
  """Emit a JSON-format log entry
  """
  entry_value_out = json.loads(json.dumps(entry_value, default=str))
  # Avoids "Object of type datetime is not JSON serializable" in
  # https://github.com/aws/aws-lambda-python-runtime-interface-client/blob/2e3d4b4/awslambdaric/lambda_runtime_log_utils.py#L110-L139
  #
  # The JSON encoder in the AWS Lambda Python runtime isn't configured to
  # serialize datatime values in responses returned by AWS's own Python SDK!
  #
  # Alternative considered:
  # https://docs.powertools.aws.dev/lambda/python/latest/core/logger

  logger.log(
    log_level, "", extra={"type": entry_type, "value": entry_value_out}
  )


class Backup():
  """AWS Backup recovery point
  """

  def __init__(self, from_event):
    self._from_event = from_event

  _action_kwargs_base = {
    "start_copy_job": {
      "SourceBackupVaultName": VAULT_NAME,
      "IamRoleArn": COPY_ROLE_ARN,
    },
    "DEFAULT": {
      "BackupVaultName": VAULT_NAME,
    },
  }

  _boto3_client = None

  @classmethod
  def get_boto3_client(cls):
    """Create (if needed) and return a boto3 client for the AWS Backup service

    boto3 method references can only be resolved at run-time, against an
    instance of an AWS service's Client class.
    http://boto3.readthedocs.io/en/latest/guide/events.html#extensibility-guide

    Alternatives considered:
    https://github.com/boto/boto3/issues/3197#issue-1175578228
    https://github.com/aws-samples/boto-session-manager-project
    """
    if cls._boto3_client is None:
      cls._boto3_client = boto3.client(
        "backup", config=botocore.config.Config(retries={"mode": "standard"})
      )
    return cls._boto3_client

  @property
  def from_event(self):  # pylint: disable=missing-function-docstring
    return self._from_event

  @property
  def arn(self):  # pylint: disable=missing-function-docstring
    return self._from_event.get("originalEvent", {}).get("resources", [""])[0]

  def validate(self):
    """Return True if all required attributes are non-empty

    A cursory validation, but EventBridge filters in CloudFormation allow only
    acceptable events, which come from AWS Backup.
    """
    if not bool(self.arn):
      raise ValueError("Could not find recoveryPoint ARN in event input")

  def log_action(self, action_name, action_kwargs, result):
    """Log the AWS Lambda event and the outcome of an action on a backup
    """
    if isinstance(result, Exception):
      log_level = logging.ERROR
      entry_type = "EXCEPTION"
    else:
      log_level = logging.INFO
      entry_type = "AWS_RESPONSE"

    log("LAMBDA_EVENT", self.from_event, log_level)
    log(f"{action_name.upper()}_KWARGS", action_kwargs, log_level)
    log(entry_type, result, log_level)

  def do_action(
    self, action_name, kwargs_add={}, validate_backup=True
  ):  # pylint: disable=dangerous-default-value
    """Take an AWS Backup method and kwargs, log outcome, and return response
    """
    action_kwargs = self._action_kwargs_base.get(
      action_name, self._action_kwargs_base["DEFAULT"]
    ) | {"RecoveryPointArn": self.arn} | kwargs_add  # Copy, don't update!
    result = None

    try:
      if validate_backup:
        self.validate()
      action_method = getattr(self.get_boto3_client(), action_name)
      result = action_method(**action_kwargs)
    except Exception as misc_exception:  # pylint: disable=broad-exception-caught
      result = misc_exception
    self.log_action(action_name, action_kwargs, result)
    if isinstance(result, Exception):
      raise result

    return result


class BackupJobResult(Backup):
  """AWS Backup recovery point - start_backup_job result

  https://docs.aws.amazon.com/aws-backup/latest/devguide/eventbridge.html#backup-job-state-change-completed
  """

  def __init__(self, from_event):
    super().__init__(from_event)
    self._destination_region = self.from_event.get("destinationRegion", "")
    self._destination_vault_arn = ":".join([
      "arn",
      AWS_PARTITION,
      "backup",
      self._destination_region,
      BACKUP_ACCOUNT_ID,
      "backup-vault",
      VAULT_NAME
    ])

  @property
  def destination_vault_arn(self):  # pylint: disable=missing-function-docstring
    return self._destination_vault_arn

  def validate(self):
    super().validate()
    if not bool(self._destination_region):
      raise ValueError("Could not find destination region in event input")


class CopyJobSource(Backup):
  """AWS Backup recovery point copy - start_copy_job source

  https://docs.aws.amazon.com/aws-backup/latest/devguide/eventbridge.html#copy-job-state-change-completed
  """

  def __init__(self, from_event):
    super().__init__(from_event)
    self._new_delete_after_days_str = self.from_event.get(
      "newDeleteAfterDays", ""
    )

  @property
  def new_delete_after_days(self):  # pylint: disable=missing-function-docstring
    return int(self._new_delete_after_days_str)

  def validate(self):
    super().validate()
    try:
      self.new_delete_after_days
    except ValueError as value_err_exception:
      raise ValueError(
        "Could not find newDeleteAfterDays in event input, "
        "or could not convert string to integer."
      ) from value_err_exception
    if self.new_delete_after_days < 1:
      raise ValueError(
        "newDeleteAfterDays must be greater than or equal to 1."
      )


def get_update_lifecycle_kwargs(
  describe_resp, today_date, new_delete_after_days
):
  """Take a describe response, return update_recovery_point_lifecycle kwargs

  Sets/reduces DeleteAfterDays, so a backup that has been copied to another
  vault can be scheduled for deletion from the original vault. If the result
  dict is empty, no lifecycle update is needed.

  Warnings:
  - Before calling describe_recovery_point , use tzset to set the local time
    zone to UTC, for correct results.
  - For safety, this function works in UTC whole days, stripping time and
    leaving a whole-day margin ( +1 and strict < inequality ). AWS Backup
    measures lifecycles (MoveToColdStorageAfterDays, DeleteAfterDays) in whole
    days, but CreationDate -- misnamed -- includes a precise time, and then
    deletion occurs "at a randomly chosen point over the following 8 hours".
    https://docs.aws.amazon.com/aws-backup/latest/devguide/recov-point-create-on-demand-backup.html
  """
  kwargs_out = {}
  lifecycle = dict(describe_resp.get("Lifecycle", {}))  # Update the copy...

  creation_date = describe_resp["CreationDate"].date()
  days_old = (today_date - creation_date).days + 1

  delete_after_days_minima = [days_old, 1, new_delete_after_days]
  delete_after_days_maximum = lifecycle.get("DeleteAfterDays")  # Don't delay

  storage_class = describe_resp.get("StorageClass")
  cold_storage_after_days = (
    lifecycle.get("MoveToColdStorageAfterDays")
    if lifecycle.get("OptInToArchiveForSupportedResources", False) else
    None
  )

  if storage_class == "DELETED":
    delete_after_days_maximum = 0
  elif cold_storage_after_days is not None:
    if (storage_class == "WARM") and (days_old < cold_storage_after_days):
      # Has not yet transitioned cold storage, and is not scheduled to, soon
      lifecycle.update({
        "OptInToArchiveForSupportedResources": False,
        "MoveToColdStorageAfterDays": -1,
      })
    else:
      # Has already transitioned cold storage, or is scheduled to, soon
      delete_after_days_minima.append(cold_storage_after_days + 90)
  elif storage_class == "COLD":
    # In case AWS Backup someday supports creation in/non-scheduled move to
    # cold storage, could have entered cold storage as late as today
    delete_after_days_minima.append(days_old + 90)

  delete_after_days = max(delete_after_days_minima) + 1
  if (
    (delete_after_days_maximum is None)
    or (delete_after_days < delete_after_days_maximum)
  ):
    lifecycle["DeleteAfterDays"] = delete_after_days
    kwargs_out = {"Lifecycle": lifecycle}

  return kwargs_out


def lambda_handler_copy(event, context):  # pylint: disable=unused-argument
  """Copy a backup to a vault in another region and/or AWS account
  """
  backup = BackupJobResult(event)
  backup.do_action(
    "start_copy_job",
    {
      "DestinationBackupVaultArn": backup.destination_vault_arn,
      "IdempotencyToken": f"{backup.arn}-{backup.destination_vault_arn}",
    }
  )


def lambda_handler_update_lifecycle(event, context):  # pylint: disable=unused-argument
  """Schedule deletion of a backup that has been copied to another vault

  Warning:
  - Before calling describe_recovery_point , use tzset to set the local time
    zone to UTC, for correct results.
  """
  backup = CopyJobSource(event)
  describe_resp = backup.do_action("describe_recovery_point")
  kwargs_lifecycle = get_update_lifecycle_kwargs(
    describe_resp, datetime.date.today(), backup.new_delete_after_days
  )
  if kwargs_lifecycle:
    backup.do_action(
      "update_recovery_point_lifecycle",
      kwargs_lifecycle,
      validate_backup=False
    )
