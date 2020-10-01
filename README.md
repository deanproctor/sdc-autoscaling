# sdc-autoscaling
This repo demonstrates an approach to orchestrating StreamSets Data Collector for the purpose of autoscaling a logical cluster with Control Hub.  The implementation addresses the following requirements:
  1. No manual intervention required.
  2. Jobs are gracefully migrated between nodes.
  3. Access permissions are automatically applied to nodes.
  4. Is autoscaler agnostic.

## Implementation
Autoscaling Data Collector with Control Hub requires a series of steps be orchestrated in the correct order.  The steps are executed via an `autoscale` script, which provides functions for `pre_start`, `post_start`, and `pre_stop` activities.  The sdc.service definition is updated to execute these functions as part of the service start and service stop processes.

The systemd service definition file is augmented to look like this:

    ExecStartPre=/opt/streamsets-datacollector/bin/autoscale pre_start
    ExecStart=/opt/streamsets-datacollector/bin/streamsets dc –verbose
    ExecStartPost=/opt/streamsets-datacollector/bin/autoscale post_start
    ExecStop=/opt/streamsets-datacollector/bin/autoscale pre_stop

`pre_start`
  1. Generates a Control Hub auth token
  2. Persists the auth token locally
  3. Enables Control Hub locally
  4. Sets the SDC base URL to an appropriate value

`post_start`
  1. Sets labels on the SDC in Control Hub
  2. Sets group sharing settings (ACLs) on the SDC in Control Hub
  3. Initiates a rebalance for jobs matching the configured labels in Control Hub

`pre_stop`
  1. Removes all labels from the SDC in Control Hub
  2. Syncs the jobs running on the SDC in Control Hub (to gracefully migrate them to other nodes)
  3. Unregisters the SDC from Control Hub

## Flavors
Orchestration scripts in 2 flavors are provided:
  1. Bash
    - Ultra portable - can be used in any installation environment
    - Requires Control Hub Organization Administrator credentials be made available to the VM (on-disk, via credential managers, environment variables, etc.)
  2. Lambda
    - Externalizes the Control Hub API calls to a Lambda function
    - The VM only requires an API Gateway token or IAM role to authenticate to the Lambda function.
    
## Installation
An `install-for-image.sh` script is provided, which will install StreamSets Data Collector along with the autoscaling implementation on a Red Hat-based OS.

Edit the Config section at the top of the script to match your environment:

    SDC_VERSION=3.18.1
    SDC_ROOT=/opt
    SDC_HOME=$SDC_ROOT/streamsets-datacollector
    SDC_CONF=/etc/sdc
    SDC_LOG=/var/log/sdc
    SDC_DATA=/var/lib/sdc
    SDC_RESOURCES=/var/lib/sdc-resources
    SDC_USER=sdc
    SDC_GROUP=sdc
    SDC_PORT=18630
    SDC_TIMEZONE=UTC
    OS_PACKAGES="core aws-lib aws-secrets-manager-credentialstore-lib crypto-lib jdbc-lib jython_2_7-lib orchestrator-lib"
    ENT_PACKAGES="snowflake-lib-1.4.0"
    # bash or lambda
    AUTOSCALE=lambda
    
Then run the script (you must have `sudo` access): `bash install-for-image.sh`

Post-installation, edit `/etc/sdc/autoscale.conf` to set your Control Hub configuration.

If you wish to install the autoscaling scripts without using the `install-for-image.sh` script, see the READMEs for the [bash](autoscale/bash/README.md) and [lambda](autoscale/lambda/README.md) implementations.
