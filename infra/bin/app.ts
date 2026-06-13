#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { HackathonFeedStack } from '../lib/hackathonfeed-stack';

const app = new cdk.App();

new HackathonFeedStack(app, 'HackathonFeedApi', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? 'us-east-1',
  },
  description: 'HackathonFeed FastAPI backend on ECS Fargate',
});
