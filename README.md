# Backup Events

- Automatically:

  - Copy AWS Backup backups to a different account ("Central Backup" if you
    use
    [Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/enable-backup.html)
    or follow
    [multi-account best practices](https://docs.aws.amazon.com/whitepapers/latest/organizing-your-aws-environment/infrastructure-ou-and-accounts.html#backup-account)).

  - Delete original backups after they've been copied -- _but_ wait to save
    money with
    [incremental backups](https://docs.aws.amazon.com/aws-backup/latest/devguide/creating-a-backup.html#incremental-backup-works).

  - Copy backups to a second region, whether for compliance, disaster
    recovery preparedness, or just peace-of-mind.

- Get started quickly, or customize.

  - Try sample vaults, or "bring your own vaults" (BYOV).

  - Try the default `aws/backup` KMS key, which lets you experiment by backing
    up unencrypted EFS file systems -- or "bring your own key" (BYOK).

  - Create 3 CloudFormation stacks from the same template for a minimum
    installation, or deploy across multiple accounts and regions by creating a
    CloudFormation StackSet.

Jump to:
[Quick Start](#quick-start)
&bull;
[Minimum Layout](#minimum-installation-layout)
&bull;
[Multi-Account, Multi-Region](#multi-account-multi-region-cloudformation-stackset)
&bull;
[Security](#security)

## Quick Start

 1. Check the prerequisites:

    - AWS Organizations is configured, and your main and backup AWS accounts
      are in your organization.
    - In the management account, under
      [AWS Organizations &rarr; Services &rarr; AWS Backup](https://console.aws.amazon.com/organizations/v2/home/services/AWS%20Backup),
      "Trusted access" is enabled. Note your organization ID, which starts with
     `o-` and appears at the lower left.
    - Under
      [AWS Organizations &rarr; Policies](https://console.aws.amazon.com/organizations/v2/home/policies),
      "Service control policies" are enabled. (This solution does not create any
      SCPs.)
    - Under
      [AWS Backup &rarr; My account &rarr; Settings &rarr; Cross-account management](https://console.aws.amazon.com/backup/home#/settings),
      all options are enabled, including "Cross-account monitoring" and
      "Cross-account backup".
    - Under "Service opt-in" (scroll up), EFS (for this quick-start) and any
      other relevant services are enabled.
    - [Service Quotas &rarr; AWS services &rarr; AWS Lambda &rarr; Concurrent executions](https://console.aws.amazon.com/servicequotas/home/services/lambda/quotas/L-B99A9384)
      has an "Applied account-level quota value" of 1,000 or more, not 10.
      Request and wait for an increase, if necessary. Repeat this check in each
      account where you intend to install Backup Events.

 2. Log in to the AWS Console as an administrator, in the AWS account where
    you would like your backups to be stored.

 3. Switch to your main region, that is, the region where most of your
    resources (in another account) are. Your main region doubles as the
    _alternate_ for your backup region.

 4. Create a
    [CloudFormation stack](https://console.aws.amazon.com/cloudformation/home)
    "With new resources". Under "Specify template", select "Upload a template
    file", then select "Choose file" and navigate to a locally-saved copy of
    [backup_events_aws.yaml](/backup_events_aws.yaml?raw=true)
    [right-click to save as...]. On the next page, set:

     - Stack name _(Copy and paste this from "For Reference")_
     - AWS organization ID
     - Backup AWS account _(From Step 2)_
     - Backup region _(A different region that you do not use much)_
     - Alternate for backup region _(From Step 3)_
  
 5. Stay in the same AWS account but switch to your backup region.
 
 6. Create a stack from the same template. Set **exactly the same parameter
    values** from Step 4.
 
 7. Switch to your main AWS account.

 8. Switch to your main region, from Step 3.
 
 9. Create a stack from the same template. Set **exactly the same parameter
    values** from Step 4.

10. Create an
    [EFS file system](https://console.aws.amazon.com/efs/home#/file-systems).
    Give your file system a name that you will recognize. Select "Customize",
    then "One Zone". Change "Transition into Archive" to None. Deselect
    "Enable automatic backups" and deselect "Enable encryption of data at
    rest" **(important for this quick-start)**. Select "Bursting".

11. When your EFS file system is ready, go to
    [AWS Backup &rarr; My account &rarr; Create on-demand backup](https://console.aws.amazon.com/backup/home#/dashboard).
    Change the "Resource type" to EFS and select your file system. Change the
    "Backup vault" to "BackupEvents-Sample" **(important)**.

12. Watch for completion of the backup job, and then creation and completion
    of a copy job. At that point, the original backup should show a "Retention
    period" of 8 days (instead of the initial 35 days).

    Switch to the backup AWS account and check for copies of your backup in
    the main region and the backup region.

13. In case of trouble, check:

    - The
      [BackupEvents CloudWatch log groups](https://console.aws.amazon.com/cloudwatch/home#logsV2:log-groups$3FlogGroupNameFilter$3DBackupEvents)
      in both accounts.

    - The `BackupEvents-ErrorTarget`
      [SQS queue](https://console.aws.amazon.com/sqs/v3/home#/queues)
      in the main account.

    - [CloudTrail &rarr; Event history](https://console.aws.amazon.com/cloudtrailv2/home#/events)
      in both accounts. Tips: Change "Read-only" to `true` to see more events.
      Select the gear icon at the right to add the "Error code" column.

14. Delete the EFS file system and all of its AWS Backup backups.

## Accounts and Regions

### Minimum Installation Layout

|Region&rarr;<br>&darr;Account||Main|Backup|
|:---|:---|:---:|:---:|
||Region code&rarr;<br>&darr;Account number|`us-east-1`|`us-west-2`|
|Main|`000022224444`|All resources||
|Backup|`999977775555`|All backups|All copies of backups|

- A minimum layout requires 2 regions, 2 AWS accounts, and 3 CloudFormation
  StackSet member instances (or 3 ordinary CloudFormation stacks, created from
  the same template).
  - There is nothing to install in the backup region of the only resource
    account, if you don't keep any resources there.

### Typical Installation Layout - Extra Region

|Region&rarr;<br>&darr;Account||USA East Coast|USA West Coast|Backup|
|:---|:---|:---:|:---:|:---:|
||Region code&rarr;<br>&darr;Account number|`us-east-1`|`us-west-1`|`us-west-2`|
|Web server|`000022224444`|Resources|Resources||
|API layer|`111133335555`|Resources|Resources||
|Database|`888866664444`|Resources|Resources||
|Backup|`999977775555`|Backups from this region|Backups from this region|Copies of backups from other regions|

- It would also be OK to keep resources in `us-west-2`.
  - Second copies of any backups from that region would go to an alternate
    second region that you specify, such as `us-east-1`.

## Advanced Installation

### Multi-Account, Multi-Region (CloudFormation StackSet)

1. Delete any standalone Backup Events CloudFormation _stacks_ in the target
   AWS accounts and regions.

2. Complete the prerequisites for creating a _StackSet_ with
   [service-managed permissions](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-orgs-enable-trusted-access.html).

3. In the management account (or a delegated administrator account), create a
   [CloudFormation StackSet](https://console.aws.amazon.com/cloudformation/home#/stacksets).
   Select "Upload a template file", then select "Choose file" and upload a
   locally-saved copy of
   [backup_events_aws.yaml](/backup_events_aws.yaml?raw=true)
   [right-click to save as...]. On the next page, copy and paste to set:

   - StackSet name
   - StackSet description
   
   Then, set the other paramaters as indicated in Step 4 of the
   [quick-start](#quick-start).

4. Deploy to your resource account(s) and backup account, in your
   main/resource region(s) (including the alternate for your backup region)
   and your backup region.

### Installation with Terraform

Terraform users are often willing to wrap a CloudFormation stack in HashiCorp
Configuration Language, because AWS supplies tools in the form of
CloudFormation templates. See
[aws_cloudformation_stack](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudformation_stack)
. Paul favored CloudFormation for this project because all AWS users have
access, and the setup effort is minimal.

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

- Least-privilege roles for the AWS Lambda function.

- A least-privilege queue policy for the "dead letter" queue.

- Readable IAM policies, formatted as CloudFormation YAML rather than JSON,
  and broken down into discrete statements by service, resource or principal.

- Optional encryption at rest with the AWS Key Management System (KMS), for
  Lambda function logs.

- Tolerance for slow operations and clock drift in a distributed system.
  The function to schedule original backups for deletion adds a full-day
  margin.

### Security Steps You Can Take

- Prevent people from modifying components, most of which can be identified by
  `BackupEvents` in ARNs and in the automatic `aws:cloudformation:stack-name`
  tag.

- Prevent people from directly invoking the AWS Lambda function and from
  passing the function role to arbitrary functions.

- Log infrastructure changes using AWS CloudTrail, and set up alerts.

</details>

## Advice

- Test Backup Events in your AWS environment. Please
  [report bugs](https://github.com/sqlxpert/backup-events-aws/issues).

- Test your backups! Can they be restored?
  [AWS Backup restore testing](https://docs.aws.amazon.com/aws-backup/latest/devguide/restore-testing.html)
  can help.

- Be aware of AWS charges including but not limited to: data transfer,
  encryption and decryption, backup storage, and early deletion from cold
  storage. AWS Backup relies on other AWS services, each with their own
  charges.

## Licenses

|Scope|Link|Included Copy|
|:---|:---:|:---:|
|Source code files, and source code embedded in documentation files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[LICENSE-CODE.md](/LICENSE-CODE.md)|
|Documentation files (including this readme file)|[GNU Free Documentation License (FDL) 1.3](http://www.gnu.org/licenses/fdl-1.3.html)|[LICENSE-DOC.md](/LICENSE-DOC.md)|

Copyright Paul Marcelin

Contact: `marcelin` at `cmu.edu` (replace "at" with `@`)
