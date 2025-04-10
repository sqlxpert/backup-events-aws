#!/usr/bin/env python3
"""Back up RDS/Aurora databases, etc. to a different AWS account and region

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

NEW_DELETE_AFTER_DAYS = int(os.environ["NEW_DELETE_AFTER_DAYS"])


def get_backup_action_kwargs_base():
  """Get base kwargs for AWS Backup methods, from environment variables
  """
  backup_vault_name = os.environ["BACKUP_VAULT_NAME"]
  return {
    "DEFAULT": {"BackupVaultName": backup_vault_name},
    "start_copy_job": {
      "IamRoleArn": os.environ["COPY_ROLE_ARN"],
      "SourceBackupVaultName": backup_vault_name,
      "DestinationBackupVaultArn": os.environ["DESTINATION_BACKUP_VAULT_ARN"],
    },
  }


def log(entry_type, entry_value, log_level=logging.INFO):
  """Emit a JSON-format log entry
  """
  entry_value_out = json.loads(json.dumps(entry_value, default=str))
  # Avoids "Object of type datetime is not JSON serializable" in
  # https://github.com/aws/aws-lambda-python-runtime-interface-client/blob/9efb462/awslambdaric/lambda_runtime_log_utils.py#L109-L135
  #
  # The JSON encoder in the AWS Lambda Python runtime isn't configured to
  # serialize datatime values in responses returned by AWS's own Python SDK!
  #
  # Alternative considered:
  # https://docs.powertools.aws.dev/lambda/python/latest/core/logger/

  logger.log(
    log_level, "", extra={"type": entry_type, "value": entry_value_out}
  )


def boto3_success(resp):
  """Take a boto3 response, return True if result was success

  Success means an AWS operation has started, not necessarily that it has
  completed. For example, it may take hours to copy a backup.
  """
  return (
    isinstance(resp, dict)
    and isinstance(resp.get("ResponseMetadata"), dict)
    and (resp["ResponseMetadata"].get("HTTPStatusCode") == 200)
  )


class Backup():
  """AWS Backup recovery point

  If the object is not also a subclass, then the recovery point is the
  original, from start_backup_job :
  https://docs.aws.amazon.com/aws-backup/latest/devguide/eventbridge.html#backup-job-state-change-completed
  """
  _boto3_client = None
  action_kwargs_base = get_backup_action_kwargs_base()

  _from_job_id_key = "backupJobId"

  def __init__(self, from_event):
    self._from_event = from_event

  @staticmethod
  def new(from_event):
    """Create a Backup or BackupCopy instance

    Takes a start_backup_job or start_copy_job state change COMPLETED event
    (EventBridge filters in CloudFormation allow only acceptable events)
    """
    new_object_class = (
      BackupCopy if from_event["detail-type"].startswith("Copy ") else Backup
    )
    return new_object_class(from_event)

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

  # pylint: disable=missing-function-docstring

  @property
  def _from_job_details(self):
    return self._from_event.get("detail", {})

  @property
  def from_event(self):
    return self._from_event

  @property
  def from_job_id(self):
    return self._from_job_details.get(self._from_job_id_key, "")

  @property
  def from_backup_arn(self):  # Reserve from_rsrc_arn for original backups
    return ""

  @property
  def arn(self):
    return self._from_event.get("resources", [""])[0]

  # pylint: enable=missing-function-docstring

  def valid(self):
    """Return True if all required attributes are non-empty

    A cursory validation, but EventBridge filters in CloudFormation allow only
    acceptable events, which come from AWS Backup.
    """
    return all([self.from_job_id, self.arn])  # More attributes coming!

  def log_action(self, action_name, action_kwargs, exception=None, resp=None):
    """Log the AWS Lambda event and the outcome of an action on a backup
    """
    log_level = logging.INFO if boto3_success(resp) else logging.ERROR

    log("LAMBDA_EVENT", self.from_event, log_level)
    log(f"{action_name.upper()}_KWARGS", action_kwargs, log_level)

    if exception is not None:
      log("EXCEPTION", exception, log_level)
    elif resp is not None:
      log("AWS_RESPONSE", resp, log_level)

  def do_action(
    self, action_name, kwargs_add={}, validate_backup=True
  ):  # pylint: disable=dangerous-default-value
    """Take an AWS Backup method and kwargs, log outcome, and return response
    """
    action_kwargs = self.action_kwargs_base.get(
      action_name, self.action_kwargs_base["DEFAULT"]
    ) | kwargs_add  # Copy, don't update!
    resp = None

    if validate_backup and not self.valid():
      self.log_action(action_name, action_kwargs)
    else:
      action_method = getattr(self.get_boto3_client(), action_name)
      try:
        resp = action_method(**action_kwargs)
      except Exception as misc_exception:
        self.log_action(action_name, action_kwargs, exception=misc_exception)
        raise
      self.log_action(action_name, action_kwargs, resp=resp)

    return resp


class BackupCopy(Backup):
  """AWS Backup recovery point copy, from start_copy_job

  https://docs.aws.amazon.com/aws-backup/latest/devguide/eventbridge.html#copy-job-state-change-completed

  Why didn't AWS use the same structure and keys for start_backup_job and the
  destination half of start_copy_job ? Both methods put a backup in a
  destination vault.
  """
  _from_job_id_key = "copyJobId"

  @property
  def from_backup_arn(self):  # Reserve from_rsrc_arn for original backups
    return self._from_event.get("resources", [""])[0]

  @property
  def arn(self):  # pylint: disable=missing-function-docstring
    return self._from_job_details.get("destinationRecoveryPointArn", "")


  def valid(self):
    """Return True if all required attributes are non-empty

    A cursory validation, but EventBridge filters in CloudFormation allow only
    acceptable events, which come from AWS Backup.
    """
    return all([self.from_job_id, self.from_backup_arn, self.arn])


def get_update_lifecycle_kwargs(describe_resp):
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
  today = datetime.date.today()
  days_old = (today - creation_date).days

  delete_after_days_minima = [days_old, 1, NEW_DELETE_AFTER_DAYS]
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
      # Has not yet transitioned cold storage, and is not scheduled to, today
      lifecycle.update({
        "OptInToArchiveForSupportedResources": False,
        "MoveToColdStorageAfterDays": -1,
      })
    else:
      # Has already transitioned cold storage, or is scheduled to, today
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
  """Copy a backup to a vault in another AWS account OR another region
  """
  backup = Backup.new(event)
  backup.do_action(
    "start_copy_job",
    {
      "RecoveryPointArn": backup.arn,
      "IdempotencyToken": backup.from_job_id,
    }
  )


def lambda_handler_update_lifecycle(event, context):  # pylint: disable=unused-argument
  """Schedule deletion of a backup that has been copied to another vault

  Warning:
  - Before calling describe_recovery_point , use tzset to set the local time
    zone to UTC, for correct results.
  """
  backup = Backup.new(event)
  describe_resp = backup.do_action(
    "describe_recovery_point",
    {"RecoveryPointArn": backup.from_backup_arn}
  )
  if boto3_success(describe_resp):
    kwargs_add = get_update_lifecycle_kwargs(describe_resp)
    if kwargs_add:
      backup.do_action(
        "update_recovery_point_lifecycle",
        kwargs_add | {"RecoveryPointArn": backup.from_backup_arn},
        validate_backup=False
      )
