#!/usr/bin/env bash

set -euo pipefail

aws cloudformation deploy \
    --stack-name bootstrap \
    --template-file github-deploy-role.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
        GitHubOrg=rmclimber \
        GitHubRepo=next_right_thing