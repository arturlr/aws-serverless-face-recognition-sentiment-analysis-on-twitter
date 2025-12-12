# Technology Stack

## Backend Infrastructure

- **AWS SAM (Serverless Application Model)**: Infrastructure as Code using CloudFormation
- **Python 3.13**: Runtime for all Lambda functions
- **AWS Lambda**: Serverless compute with layers for shared dependencies
- **AWS Step Functions**: Orchestrates image processing workflow
- **Amazon Rekognition**: Face detection, emotion analysis, and content moderation
- **DynamoDB**: NoSQL database with TTL for temporary data storage
- **S3**: Object storage with lifecycle policies for data retention
- **Kinesis Data Firehose**: Streaming data to S3 in Parquet format
- **AWS Glue**: Data catalog for Athena queries
- **Amazon Athena**: SQL queries on S3 data
- **CloudFront**: CDN for web app distribution
- **API Gateway (HTTP API)**: REST API endpoints

## Frontend

- **Vue.js 3**: Progressive JavaScript framework
- **Vite**: Build tool and dev server
- **PrimeVue**: UI component library
- **Chart.js**: Data visualization
- **Axios**: HTTP client for API calls

## Key Dependencies

### Lambda Layers
- **Core Layer**: `requests`, `aws_xray_sdk`, `aws_embedded_metrics`
- **Pandas Layer**: `pandas`, `numpy` (for data processing)

### Lambda-specific Dependencies
- **Poller**: `tweepy>=4.14.0` for X API v2 integration
- **Other functions**: Use core layer + boto3 (included in Lambda runtime)

## Common Build Commands

```bash
# Build SAM application
sam build

# Build with containers (requires Docker)
sam build --use-container --build-image amazon/aws-sam-cli-build-image-python3.13

# Deploy with guided setup
sam deploy --guided --capabilities CAPABILITY_NAMED_IAM

# Deploy Vue.js app to S3/CloudFront
./appDeploy.sh

# Local development (webapp)
cd webapp
npm install
npm run dev

# Build webapp for production
npm run build
```

## Monitoring & Observability

- **AWS X-Ray**: Distributed tracing (enabled on all Lambda functions)
- **CloudWatch Embedded Metrics**: Custom metrics for tweet processing, image moderation, face detection
- **CloudWatch Logs**: Centralized logging with structured log format
- **Step Functions**: Visual workflow monitoring and error handling