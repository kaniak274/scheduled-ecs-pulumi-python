## scheduled-ecs-pulumi-python

Example pulumi Python setup to schedule task on the ECS.

## Requirements
* Python3 + pip + venv

## Running Pulumi on AWS

To start creating AWS resources I encourage you to try
[Get Started](https://www.pulumi.com/docs/clouds/aws/get-started/begin/) guide for AWS
which is very well made.

## Adjusting the example

Keep in mind that this is just an example. You will need to adjust the code for your case.

### Adjusting network settings

You will need to adjust the subnets and VPC settings which are not added here as
I used default VPC and my subnets.

### Adjusting Resource Names

I provided `RESOURCES_PREFIX` which should change the prefix for each resource that the example will create.

### Adjusting AWS configuration

You will need to set `AWS_REGION` & `AWS_ACCOUNT_ID` env variables in order to run the example. The `AWS_REGION` is a region where you want to create the containers and `AWS_ACCOUNT_ID` is your aws account id without hypens.
