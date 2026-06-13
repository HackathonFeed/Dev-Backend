import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export interface HackathonFeedStackProps extends cdk.StackProps {
  /** Comma-separated CORS origins for the API */
  readonly corsOrigins?: string;
}

export class HackathonFeedStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: HackathonFeedStackProps) {
    super(scope, id, props);

    const corsOrigins =
      props?.corsOrigins ??
      this.node.tryGetContext('corsOrigins') ??
      'http://localhost:3000,http://localhost:5173';

    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 2,
      natGateways: 1,
    });

    const appSecret = new secretsmanager.Secret(this, 'AppSecret', {
      description: 'HackathonFeed API runtime secrets',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({
          DATABASE_URL: 'postgresql+asyncpg://postgres:CHANGE_ME@db.example.supabase.co:5432/postgres',
          SUPABASE_URL: 'https://example.supabase.co',
          SUPABASE_SERVICE_KEY: 'CHANGE_ME',
          GOOGLE_CLIENT_ID: 'CHANGE_ME',
          GEMINI_API_KEY: '',
          RAZORPAY_KEY_ID: '',
          RAZORPAY_KEY_SECRET: '',
          SMTP_EMAIL: '',
          SMTP_PASSWORD: '',
        }),
        generateStringKey: 'JWT_SECRET_KEY',
        excludeCharacters: '"@/\\',
      },
    });

    const cluster = new ecs.Cluster(this, 'Cluster', { vpc });

    const logGroup = new logs.LogGroup(this, 'ApiLogGroup', {
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const service = new ecsPatterns.ApplicationLoadBalancedFargateService(this, 'ApiService', {
      cluster,
      cpu: 512,
      memoryLimitMiB: 1024,
      desiredCount: 1,
      publicLoadBalancer: true,
      assignPublicIp: false,
      taskSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      healthCheckGracePeriod: cdk.Duration.seconds(90),
      circuitBreaker: { rollback: true },
      taskImageOptions: {
        image: ecs.ContainerImage.fromAsset('..', { file: 'Dockerfile' }),
        containerPort: 8000,
        environment: {
          ENVIRONMENT: 'production',
          DEBUG: 'false',
          API_PREFIX: '/api/v1',
          AWS_REGION: this.region,
          BEDROCK_MODEL_ID: 'amazon.nova-micro-v1:0',
          PREFER_SUPABASE_REST: 'true',
          USE_SUPABASE_HACKATHONS: 'true',
          CORS_ORIGINS: corsOrigins,
        },
        secrets: {
          JWT_SECRET_KEY: ecs.Secret.fromSecretsManager(appSecret, 'JWT_SECRET_KEY'),
          DATABASE_URL: ecs.Secret.fromSecretsManager(appSecret, 'DATABASE_URL'),
          SUPABASE_URL: ecs.Secret.fromSecretsManager(appSecret, 'SUPABASE_URL'),
          SUPABASE_SERVICE_KEY: ecs.Secret.fromSecretsManager(appSecret, 'SUPABASE_SERVICE_KEY'),
          GOOGLE_CLIENT_ID: ecs.Secret.fromSecretsManager(appSecret, 'GOOGLE_CLIENT_ID'),
          GEMINI_API_KEY: ecs.Secret.fromSecretsManager(appSecret, 'GEMINI_API_KEY'),
          RAZORPAY_KEY_ID: ecs.Secret.fromSecretsManager(appSecret, 'RAZORPAY_KEY_ID'),
          RAZORPAY_KEY_SECRET: ecs.Secret.fromSecretsManager(appSecret, 'RAZORPAY_KEY_SECRET'),
          SMTP_EMAIL: ecs.Secret.fromSecretsManager(appSecret, 'SMTP_EMAIL'),
          SMTP_PASSWORD: ecs.Secret.fromSecretsManager(appSecret, 'SMTP_PASSWORD'),
        },
        logDriver: ecs.LogDrivers.awsLogs({
          streamPrefix: 'hackathonfeed-api',
          logGroup,
        }),
      },
    });

    appSecret.grantRead(service.taskDefinition.taskRole);

    service.taskDefinition.taskRole.addToPrincipalPolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: [`arn:aws:bedrock:${this.region}::foundation-model/*`],
      }),
    );

    service.targetGroup.configureHealthCheck({
      path: '/health',
      healthyHttpCodes: '200',
      interval: cdk.Duration.seconds(30),
      timeout: cdk.Duration.seconds(5),
    });

    const scaling = service.service.autoScaleTaskCount({
      minCapacity: 1,
      maxCapacity: 2,
    });
    scaling.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.seconds(60),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    new cdk.CfnOutput(this, 'LoadBalancerUrl', {
      value: `http://${service.loadBalancer.loadBalancerDnsName}`,
      description: 'Public API base URL (health check at /health)',
    });

    new cdk.CfnOutput(this, 'ApiDocsUrl', {
      value: `http://${service.loadBalancer.loadBalancerDnsName}/docs`,
      description: 'Swagger UI',
    });

    new cdk.CfnOutput(this, 'AppSecretArn', {
      value: appSecret.secretArn,
      description: 'Update secret values before first traffic (see scripts/setup-aws-secrets.sh)',
    });

    new cdk.CfnOutput(this, 'EcsClusterName', {
      value: cluster.clusterName,
    });

    new cdk.CfnOutput(this, 'EcsServiceName', {
      value: service.service.serviceName,
    });
  }
}
