# Backup Events

- Automatically:

  - Copy AWS Backup backups to a different account ("Central Backup" if you
    use
    [Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/enable-backup.html)
    or follow
    [multi-account best practices](https://docs.aws.amazon.com/whitepapers/latest/organizing-your-aws-environment/infrastructure-ou-and-accounts.html#backup-account)).

  - Delete original backups after copying -- but _wait_ to save money with
    [incremental backups](https://docs.aws.amazon.com/aws-backup/latest/devguide/creating-a-backup.html#incremental-backup-works).

  - Copy backups to a second region, whether for compliance, disaster
    recovery preparedness, or just peace-of-mind.

- Get started quickly, or customize.

  - Try the sample backup vaults, or "bring your own vaults" (BYOV).

  - Try the default `aws/backup` KMS key, which lets you experiment by backing
    up unencrypted EFS file systems -- or "bring your own key" (BYOK).

  - Create 3 CloudFormation stacks from 1 template for a minimum installation,
    or deploy across many accounts and regions by creating a StackSet.

Jump to:
[Quick Start](#quick-start)
&bull;
[Minimum Account Layout](#minimum-account-layout)
&bull;
[Multi-Account, Multi-Region Install](#multi-account-multi-region-cloudformation-stackset)
&bull;
[Security](#security)

## Quick Start

 1. Check the prerequisites...

    If you have already used AWS Backup from the AWS Console, to make a backup
    in one AWS account (your "main account") and copy the backup to another
    account (your "backup account"), you are probably ready for the
    quick-start. Find your `o-` Organization ID in the lower left corner of
    the
    [AWS Organizations](https://us-east-1.console.aws.amazon.com/organizations/v2/home/accounts)
    console page.

    <details>
      <summary>For complex environments, or if you are new to AWS Backup...</summary>

    - AWS Organizations is configured.
    - Every AWS account where you intend to install Backup Events is in your
      organization.
    - In the management account, under
      [AWS Organizations &rarr; Services &rarr; AWS Backup](https://console.aws.amazon.com/organizations/v2/home/services/AWS%20Backup),
      "Trusted access" is enabled.
    - Under
      [AWS Organizations &rarr; Policies](https://console.aws.amazon.com/organizations/v2/home/policies),
      "Service control policies" are enabled.
    - Under
      [AWS Backup &rarr; My account &rarr; Settings &rarr; Cross-account management](https://console.aws.amazon.com/backup/home#/settings),
      all options are enabled, including "Cross-account monitoring" and
      "Cross-account backup".
    - Under "Service opt-in" (scroll up), EFS (for the quick-start) and any
      other relevant services are enabled.
    - In every AWS account where you intend to install Backup Events, the
      [AWSBackupDefaultServiceRole](https://console.aws.amazon.com/iam/home#/roles/details/AWSBackupDefaultServiceRole)
      exists. If you use the AWS Console, AWS Backup creates this role the
      first time you make an on-demand backup in a given AWS account.
      Otherwise, see
      [Default service role for AWS Backup](https://docs.aws.amazon.com/aws-backup/latest/devguide/iam-service-roles.html#default-service-roles).
    - Permissions are sufficient and service and resource control policies
      (SCPs and RCPs), permissions boundaries, or session policies do not
      interfere with the installation or operation of Backup Events. Check
      with your AWS administrator!

    </details>

 2. Log in to the AWS Console as an administrator, in the AWS account where
    you would like your backups to be stored.

    - You will need to paste you backup account number several times. Open the
      menu at the top right corner of the AWS Console and copy the Account ID.

 3. Switch to your main region, that is, the region where most of your
    resources (housed in another account) are.

    - Your main region will double as the _alternate_ for your backup region.

 4. Create a
    [CloudFormation stack](https://console.aws.amazon.com/cloudformation/home)
    "With new resources". Under "Specify template", select "Upload a template
    file", then select "Choose file" and navigate to a locally-saved copy of
    [backup_events_aws.yaml](/backup_events_aws.yaml?raw=true)
    [right-click to save as...]. On the next page, set:

    - Stack name - _Copy and paste from "For Reference"_
    - AWS Organization ID - _From quick-start Step 1_
    - Backup AWS account - _From quick-start Step 2_
    - Backup region - _Specify a different region that you do not use much_
    - Alternate for backup region - _From quick-start Step 3_
    - Days (from creation) to keep original backups - _Note, but do not change
      this for the quick-start. With incremental backups, aim to keep the
      previous one
      [long enough](https://docs.aws.amazon.com/aws-backup/latest/devguide/metering-and-billing.html)
      for the next scheduled backup to complete._
  
 5. Stay in the same AWS account but switch to your backup region.

 6. Create a stack from the same template. Set **exactly the same parameter
    values** as in quick-start Step 4.

 7. Note your backup account number before leaving (you will need it to create
    one more stack, but it will not be available to copy), then switch to your
    main AWS account.

 8. Switch to your main region (from quick-start Step 3).

 9. Create a stack from the same template. Set **exactly the same parameter
    values** as in quick-start Step 4.

10. Create a minimal
    [EFS file system](https://console.aws.amazon.com/efs/home#/file-systems).

    - Give it a name that you will recognize.
    - Select "Customize".
    - Select One Zone.
    - Deselect "Enable automatic backups".
    - Change "Transition into Archive" to None.
    - Deselect "Enable encryption of data at rest" **(important for this
      quick-start)**.
    - Change "Throughput mode" to Bursting.

11. When your file system is ready, go to
    [AWS Backup &rarr; My account &rarr; Dashboard &rarr; Create on-demand backup](https://console.aws.amazon.com/backup/home#/dashboard).

    - Change "Resource type" to EFS and select your new file system.
    - Change "Total retention period" to 14 days.
    - Change "Backup vault" to BackupEvents-Sample **(important)**.

12. Watch for completion of the backup job, and then creation and completion
    of a copy job. At that point, the original backup should show a "Retention
    period" of 8 days (instead of the initial 14 days).

    Switch to the backup AWS account and check for copies of your backup in
    the main region and the backup region.

13. In case of trouble, focus on the main region and check, in both accounts
    unless otherwise noted,

    - The [BackupEvents CloudWatch log group(s)](https://console.aws.amazon.com/cloudwatch/home#logsV2:log-groups$3FlogGroupNameFilter$3DBackupEvents)

    - The `BackupEvents`
      [SQS queue](https://console.aws.amazon.com/sqs/v3/home#/queues)
      (not in the backup account)

    - [CloudTrail &rarr; Event history](https://console.aws.amazon.com/cloudtrailv2/home#/events).
      Tips: Change "Read-only" to `true` to see more events. Select the gear
      icon at the right to add the "Error code" column.

14. Delete the EFS file system and all of its AWS Backup backups (or let the
    backups expire, at a small cost).

    - You will not be able to fully delete a Backup Events CloudFormation
      stack if backups remain in the stack's sample vault. This prevents the
      proliferation of unmanaged vaults.

## Accounts and Regions

The region codes are examples. Choose the regions you use, noting some
differences in AWS Backup
[Feature availability by Region](https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html#features-by-region).

### Minimum Account Layout

|Region&rarr;<br>Account<br>&darr;||Main|Backup|
|:---|:---|:---:|:---:|
||Region code&rarr;<br>Account ID<br>&darr;|`us-east-1`|`us-west-2`|
|Main|`000022224444`|All resources||
|Backup|`999977775555`|All backups|All copies of backups|

- There is nothing to install in the backup region of the only resource
  account, if you do not keep any resources there.

### Typical Account Layout - Extra Region

|Region&rarr;<br>Account<br>&darr;||USA East Coast|USA West Coast|Backup|
|:---|:---|:---:|:---:|:---:|
||Region code&rarr;<br>Account ID<br>&darr;|`us-east-1`|`us-west-1`|`us-west-2`|
|Web server|`000022224444`|Resources|Resources||
|API layer|`111133335555`|Resources|Resources||
|Database|`888866664444`|Resources|Resources||
|Backup|`999977775555`|Backups from this region|Backups from this region|Copies of backups from other regions|

- It would also be OK to keep resources in `us-west-2`. Second copies of any
  backups from the backup region go to an alternate that you configure, such
  as `us-east-1`.

## Advanced Installation

### Multi-Account, Multi-Region (CloudFormation StackSet)

 1. Delete any standalone Backup Events CloudFormation _stacks_ in the target
    AWS accounts and regions.

 2. Complete the CloudFormation prerequisites for creating a _StackSet_ with
    [service-managed permissions](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-orgs-enable-trusted-access.html).

 3. Review the Backup Events prerequisites in Step 1 of the
    [quick-start](#quick-start).

    - If the AWSBackupDefaultServiceRole is not present in every AWS account
      where you intend to install Backup Events, define and disseminate a
      custom role, perhaps by creating your own CloudFormation StackSet. (If
      you write a CloudFormation template, set `RoleName` for a consistent
      name.) The trust policy must allow
      `"Principal": { "Service": "backup.amazonaws.com" }` to
      to `"sts:AssumeRole"` . Attach the
      `arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup`
      AWS-managed IAM policy. Choose one region in which to deploy your role;
      roles are account-wide.

 4. In the management account (or a delegated administrator account), create a
    [CloudFormation StackSet](https://console.aws.amazon.com/cloudformation/home#/stacksets).
    Under "Specify template", select "Upload a template file", then select
    "Choose file" and upload a locally-saved copy of
    [backup_events_aws.yaml](/backup_events_aws.yaml?raw=true)
    [right-click to save as...].

    - Set parameters as in Step 4 of the [quick-start](#quick-start).
    - IAM role name for copying backups - _Change if you defined and
      disseminated a custom role, above._

 5. Deploy to your backup account and main/resource account(s), in your
    backup region and main/resource region(s) (including the alternate for
    your backup region).

### Installation with Terraform

Terraform users are often willing to wrap a CloudFormation stack in HashiCorp
Configuration Language, because AWS supplies tools in the form of
CloudFormation templates. See
[aws_cloudformation_stack](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudformation_stack)
. Paul favors CloudFormation because all AWS users have access, the setup
effort is minimal, and those with a support plan can get CloudFormation help
from AWS.

Wrapping a CloudFormation _StackSet_ in HCL is much easier than configuring
and using Terraform to deploy and maintain identical resources in multiple AWS
accounts and regions. See
[aws_cloudformation_stack_set](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudformation_stack_set)
.

## Security

_In accordance with the software license, nothing in this section creates a
warranty, an indemnification, an assumption of liability, etc. Use this
software at your own risk. You are encouraged to evaluate the source code._

<details>
  <summary>Security details...</summary>

### Security Design Goals

- Least-privilege roles for the AWS Lambda functions

- Readable IAM policies, formatted as CloudFormation YAML rather than JSON,
  and broken down into discrete statements by service, resource or principal

- Tolerance for slow operations and clock drift in a distributed system.
  The function to schedule original backups for deletion adds a full-day
  margin.

- Option to encrypt logs and queued event errors at rest, using the AWS Key
  Management System (KMS)

- Least-privilege SQS queue policy

- Option to use custom vaults (with custom KMS keys) and a custom role for
  AWS Backup

### Security Steps You Can Take

- Prevent modification of the components, most of which are identified by
  `BackupEvents` in ARNs and in the automatic `aws:cloudformation:stack-name`
  tag.

- Prevent arbitrary invokation of the AWS Lambda functions. See comments in
  the CloudFormation template, including an observation about the limitations
  of Lambda's AddPermission operation.

- Prevent use of the function roles with arbitrary functions. See comments.

- Log infrastructure changes using AWS CloudTrail, and set up alerts.

- Instead of relying on sample vaults, on default `aws/` KMS keys, and on the
  AWSBackupDefaultServiceRole , define custom equivalents with least-privilege
  resource- and/or identity-based policies tailored to your needs.

</details>

## Advice

- Test Backup Events in your AWS environment. Please
  [report bugs](https://github.com/sqlxpert/backup-events-aws/issues).

- Test your backups! Can they be restored?
  [AWS Backup restore testing](https://docs.aws.amazon.com/aws-backup/latest/devguide/restore-testing.html)
  can help.

- Compare backup storage costs over time to assess the success of your
  NewDeleteAfterDays setting (which is applied to original backups, after they
  have been copied to your backup account), of incremental backups (if
  applicable), and of the lifecycles you choose when creating backups (which
  apply to the two copies in your backup account).

- Be aware of other AWS charges including but not limited to: data transfer,
  encryption/decryption, key management, and early deletion from cold storage.
  AWS Backup relies on other AWS services, each with their own charges.

## Related

- ([Code](https://github.com/aws-samples/aws-blog-automate-amazon-rds-cross-account-backups))
  [Automate cross-account backups of RDS and Aurora databases with AWS Backup](https://aws.amazon.com/blogs/database/automate-cross-account-backups-of-amazon-rds-and-amazon-aurora-databases-with-aws-backup/)<br>
  Enrique Ramirez, AWS Database Blog, October 14, 2021

- ([Code](https://github.com/aws-samples/eventbridge-cross-account-targets))
  [Introducing cross-account targets for EventBridge Event Buses](https://aws.amazon.com/blogs/compute/introducing-cross-account-targets-for-amazon-eventbridge-event-buses/)<br>
  Chris McPeek, AWS Compute Blog, January 21, 2025

## Motivation

<details>
  <summary>What motivated this work? ...</summary>

Paul discovered the AWS Database blog post and sample code through a
colleague, who had used it to back up a fleet of RDS databases with default
KMS encryption. Thank you, Eugene, for always surveying the landscape first!

To back up a new Aurora database fleet, Paul wrote native Terraform and
adopted the sample AWS Lambda function Python source code. Given the
importance of the backups, Paul wrote least-privilege IAM policies for custom
roles. He had already created customer-managed, multi-region, cross-account
KMS keys for the new databases.

Later, he added a function to rewrite AWS Backup lifecycle objects, so that
backups could be deleted after they had been copied. Paul does not remember
what he put in that fuction, and he has moved on from the company, but he does
remember wishing for a simpler, self-documenting function.

So, Paul decided to write a new solution from scratch, on his own behalf. The
benefits?

- One CloudFormation template replaces three, so that advanced users can also
  use it to create a StackSet for deployment at scale. Whether the current AWS
  account and region match the backup account and backup region determines
  which AWS resources are created, and what the source and target strings are.

- Advanced users can provide a multi-region KMS key. For now, Paul is not
  publishing his test key definitions and key policies. The risk that an LLM
  will treat a general example as specific, and that the security of some
  important system will be compromised, is too great. If you need help with
  multi-region, cross-account KMS encryption keys, least-privilege IAM
  policies, etc., contact Paul!

- Object-oriented Python code interprets backup job completed events and
  copy job completed events. A superclass covers the many similarities and a
  subclass, the few differences. The same primitives serve for copying a
  backup to a different account, reducing the original backup's retention,
  and copying the copy to a different region.

- The function to reduce retention of backups that have been copied is simple.
  Minimum retention periods under various rules are added to a list. At the
  end, the highest minimum is applied.

- From resource accounts, EventBridge directly invokes a Lambda function in
  the backup account. Cross-account invokation, introduced in January, 2025,
  eliminates a custom event bus. Paul goes further than the AWS Compute blog
  post and sample code, restricting permissions as much as possible.

</details>

## Licenses

|Scope|Link|Included Copy|
|:---|:---:|:---:|
|Source code files, and source code embedded in documentation files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[LICENSE-CODE.md](/LICENSE-CODE.md)|
|Documentation files (including this readme file)|[GNU Free Documentation License (FDL) 1.3](http://www.gnu.org/licenses/fdl-1.3.html)|[LICENSE-DOC.md](/LICENSE-DOC.md)|

Copyright Paul Marcelin

Contact: `marcelin` at `cmu.edu` (replace "at" with `@`)
