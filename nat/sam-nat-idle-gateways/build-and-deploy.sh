#!/bin/bash


set -e  # Exit on error
set -v  # Print command, with variables
set -x  # Print commands, with variables filled in

export AWS_PROFILE=ab
sam build
sam deploy --stack-name sjb-demo-nat-gateway-finder --resolve-s3
