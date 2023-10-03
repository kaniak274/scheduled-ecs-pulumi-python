import os

import pulumi
import pulumi_aws as aws


RESOURCES_PREFIX = "example"
AWS_REGION = os.environ["AWS_REGION"]
AWS_ACCOUNT_ID = os.environ["AWS_ACCOUNT_ID"]


def create_ecs_cluster():
    return aws.ecs.Cluster(f"{RESOURCES_PREFIX}-cluster", name=f"{RESOURCES_PREFIX}-cluster")


def setup_ecs_execution_role():
    execution_role_assumed_policy = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=["sts:AssumeRole"],
                principals=[
                    aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                        type="Service",
                        identifiers=["ecs-tasks.amazonaws.com"],
                    )
                ],
            )
        ]
    )

    execution_role = aws.iam.Role(
        f"{RESOURCES_PREFIX}-ecs-execution-role",
        assume_role_policy=execution_role_assumed_policy.json,
    )

    aws.iam.RolePolicyAttachment(
        f"{RESOURCES_PREFIX}-ecs-task-execution-policy-attachment",
        role=execution_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
    )

    aws.iam.RolePolicyAttachment(
        f"{RESOURCES_PREFIX}-ec2-container-registry-policy-attachment",
        role=execution_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    )

    return execution_role


def setup_ecs_task(execution_role):
    repository = aws.ecr.Repository(f"{RESOURCES_PREFIX}-image")
    log_group = aws.cloudwatch.LogGroup(f"{RESOURCES_PREFIX}-logs-group", name=f"{RESOURCES_PREFIX}-logs-group")

    return aws.ecs.TaskDefinition(
        f"{RESOURCES_PREFIX}-task",
        family=RESOURCES_PREFIX,
        cpu=256,
        memory=512,
        execution_role_arn=execution_role.arn,
        requires_compatibilities=["FARGATE"],
        network_mode="awsvpc",
        container_definitions=pulumi.Output.json_dumps(
            [
                {
                    "name": "schedule-task",
                    "image": repository.repository_url,
                    "cpu": 0,
                    "memory": 256,
                    "essential": True,
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-stream-prefix": RESOURCES_PREFIX,
                            "awslogs-region": AWS_REGION,
                            "awslogs-group": log_group.name,
                        },
                    },
                }
            ]
        ),
    )


def setup_execution_role_for_scheduled_task(ecs_execution_role):
    cloudwatch_events_role_assume_policy = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=["sts:AssumeRole"],
                principals=[
                    aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                        type="Service",
                        identifiers=["events.amazonaws.com"],
                    )
                ],
            )
        ]
    )

    ecs_task_role_assume_policy = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=["sts:AssumeRole"],
                principals=[
                    aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                        type="Service",
                        identifiers=["ecs-tasks.amazonaws.com"],
                    )
                ],
            )
        ]
    )

    cloudwatch_events_role_run_task_policy = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=["ecs:RunTask"],
                resources=[
                    f"arn:aws:ecs:{AWS_REGION}:{AWS_ACCOUNT_ID}:task-definition/example:*"
                ],
                conditions=[
                    aws.iam.GetPolicyDocumentStatementConditionArgs(
                        test="StringLike",
                        variable="ecs:cluster",
                        values=[cluster.arn],
                    )
                ],
            )
        ]
    )

    ecs_task_role = aws.iam.Role(
        f"{RESOURCES_PREFIX}-ecs-task-role",
        name=f"{RESOURCES_PREFIX}-ecs-task-role",
        assume_role_policy=ecs_task_role_assume_policy.json,
    )

    cloudwatch_events_role = aws.iam.Role(
        f"{RESOURCES_PREFIX}-schedule-event-role",
        name=f"{RESOURCES_PREFIX}-schedule-event-role",
        assume_role_policy=cloudwatch_events_role_assume_policy.json,
    )

    aws.iam.RolePolicy(
        f"{RESOURCES_PREFIX}-events-ecs",
        name=f"{RESOURCES_PREFIX}-events-ecs",
        role=cloudwatch_events_role.id,
        policy=cloudwatch_events_role_run_task_policy.json,
    )

    cloudwatch_events_role_pass_role_policy = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                effect="Allow",
                actions=["iam:PassRole"],
                resources=[
                    ecs_execution_role.arn,
                    ecs_task_role.arn,
                ],
            )
        ]
    )

    aws.iam.RolePolicy(
        f"{RESOURCES_PREFIX}-events-ecs-pass-role",
        name=f"{RESOURCES_PREFIX}-events-ecs-pass-role",
        role=cloudwatch_events_role.id,
        policy=cloudwatch_events_role_pass_role_policy.json,
    )

    return cloudwatch_events_role


def schedule_ecs_task(scheduler_execution_role, cluster, task_definition):
    scheduler = aws.cloudwatch.EventRule(
        f"{RESOURCES_PREFIX}-scheduler",
        name=f"{RESOURCES_PREFIX}-scheduler",
        schedule_expression="cron(0/5 * * * ? *)",
    )

    return aws.cloudwatch.EventTarget(
        f"{RESOURCES_PREFIX}-event-target",
        rule=scheduler.name,
        target_id=task_definition.family,
        arn=cluster.arn,
        role_arn=scheduler_execution_role.arn,
        ecs_target=aws.cloudwatch.EventTargetEcsTargetArgs(
            launch_type="FARGATE",
            task_count=1,
            task_definition_arn=task_definition.arn,
            network_configuration=aws.cloudwatch.EventTargetEcsTargetNetworkConfigurationArgs(
                subnets=[
                    "subnet-0777a552681a1ec29",
                    "subnet-0c40de75363b4f171",
                    "subnet-0dd74048e8c527393",
                ],
                assign_public_ip=True,
            ),
        ),
    )


if __name__ == "__main__":
    cluster = create_ecs_cluster()
    ecs_execution_role = setup_ecs_execution_role()
    task_definition = setup_ecs_task(execution_role=ecs_execution_role)
    scheduler_execution_role = setup_execution_role_for_scheduled_task(
        ecs_execution_role=ecs_execution_role,
    )
    schedule_ecs_task(
        scheduler_execution_role=scheduler_execution_role,
        cluster=cluster,
        task_definition=task_definition,
    )
