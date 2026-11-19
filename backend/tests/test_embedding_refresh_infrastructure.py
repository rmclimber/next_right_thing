"""Protect the worker's network, permission, cost, and deployment boundaries."""

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class CloudFormationLoader(yaml.SafeLoader):
    pass


def intrinsic(loader, tag, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)
    return {tag: value}


CloudFormationLoader.add_multi_constructor("!", intrinsic)


class EmbeddingRefreshInfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.template = yaml.load((ROOT / "infra/ingestion/ingestion.yaml").read_text(), Loader=CloudFormationLoader)
        self.resources = self.template["Resources"]
        self.workflow = yaml.safe_load((ROOT / ".github/workflows/deploy-stack.yml").read_text())

    def test_worker_uses_no_paid_network_resource_and_has_bounded_compute(self):
        worker = self.resources["EmbeddingRefreshFunction"]["Properties"]
        self.assertNotIn("VpcConfig", worker)
        self.assertNotIn("ProvisionedConcurrencyConfig", worker)
        self.assertEqual((worker["MemorySize"], worker["Timeout"], worker["ReservedConcurrentExecutions"]), (512, 300, 1))
        self.assertEqual(worker["Environment"]["Variables"]["DATABASE_CLUSTER_ARN"], {"Ref": "DatabaseClusterArn"})
        for resource in self.resources.values():
            self.assertNotIn(resource["Type"], {"AWS::EC2::NatGateway", "AWS::EC2::VPCEndpoint", "AWS::StepFunctions::StateMachine"})

    def test_schedule_is_two_hour_disableable_and_targets_only_the_worker(self):
        schedule = self.resources["EmbeddingRefreshSchedule"]["Properties"]
        self.assertEqual(schedule["ScheduleExpression"], "rate(2 hours)")
        self.assertEqual(schedule["FlexibleTimeWindow"], {"Mode": "OFF"})
        self.assertEqual(schedule["State"], {"If": ["EmbeddingRefreshEnabled", "ENABLED", "DISABLED"]})
        self.assertEqual(schedule["Target"]["Arn"], {"GetAtt": "EmbeddingRefreshFunction.Arn"})
        self.assertEqual(schedule["Target"]["Input"], "{}")
        self.assertEqual(self.resources["SourceDispatchSchedule"]["Properties"]["ScheduleExpression"], "rate(120 minutes)")
        policies = self.resources["EmbeddingRefreshScheduleRole"]["Properties"]["Policies"]
        statements = policies[0]["PolicyDocument"]["Statement"]
        self.assertEqual(statements, [{"Effect": "Allow", "Action": "lambda:InvokeFunction", "Resource": {"GetAtt": "EmbeddingRefreshFunction.Arn"}}])

    def test_role_scopes_database_secret_and_model_access_without_write_access_to_queues(self):
        statements = self.resources["EmbeddingRefreshFunctionRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        permissions = {}
        for statement in statements:
            actions = statement["Action"]
            for action in actions if isinstance(actions, list) else [actions]:
                permissions[action] = statement["Resource"]
        self.assertEqual(permissions["rds-data:ExecuteStatement"], {"Ref": "DatabaseClusterArn"})
        self.assertEqual(permissions["secretsmanager:GetSecretValue"], {"Ref": "DatabaseSecretArn"})
        self.assertEqual(permissions["bedrock:InvokeModel"], {"Sub": "arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/amazon.titan-embed-text-v2:0"})
        self.assertFalse(any(action.startswith(("sqs:", "ec2:")) for action in permissions))
        self.assertNotIn("*", permissions.values())

    def test_retries_log_retention_and_alarm_make_failures_visible(self):
        retries = self.resources["EmbeddingRefreshRetryConfig"]["Properties"]
        self.assertEqual((retries["MaximumRetryAttempts"], retries["MaximumEventAgeInSeconds"]), (2, 3600))
        self.assertEqual(self.resources["EmbeddingRefreshLogGroup"]["Properties"]["RetentionInDays"], 14)
        alarm = self.resources["EmbeddingRefreshErrorsAlarm"]["Properties"]
        self.assertEqual((alarm["Namespace"], alarm["MetricName"], alarm["Threshold"]), ("AWS/Lambda", "Errors", 1))
        self.assertEqual(alarm["Dimensions"], [{"Name": "FunctionName", "Value": {"Ref": "EmbeddingRefreshFunction"}}])

    def test_workflow_builds_and_passes_artifact_and_controls_under_database_gate(self):
        job = self.workflow["jobs"]["deploy"]
        steps = {step["name"]: step for step in job["steps"]}
        for name in ("Build Embedding Refresh Lambda Artifact", "Upload Embedding Refresh Lambda Artifact", "Deploy Ingestion Stack"):
            self.assertEqual(steps[name]["if"], "${{ vars.ENABLE_DATABASE_BACKEND == 'true' }}")
        build = steps["Build Embedding Refresh Lambda Artifact"]["run"]
        self.assertIn("lambda/embedding-refresh/${GITHUB_SHA}.zip", build)
        deploy = steps["Deploy Ingestion Stack"]["run"]
        self.assertIn('EmbeddingRefreshFunctionCodeS3Key="${EMBEDDING_REFRESH_ARTIFACT_KEY}"', deploy)
        self.assertIn('EnableEmbeddingRefresh="${ENABLE_EMBEDDING_REFRESH}"', deploy)
        self.assertIn("ENABLE_EMBEDDING_REFRESH", job["env"])
        names = [step["name"] for step in job["steps"]]
        self.assertLess(names.index("Build Embedding Refresh Lambda Artifact"), names.index("Deploy Ingestion Stack"))
        self.assertLess(names.index("Run Database Migrations"), names.index("Deploy Ingestion Stack"))


if __name__ == "__main__":
    unittest.main()
