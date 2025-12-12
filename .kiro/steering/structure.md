# Project Structure

## Root Level Files

- `template.yaml`: AWS SAM CloudFormation template defining all infrastructure
- `samconfig.toml`: SAM deployment configuration with stack parameters
- `appDeploy.sh`: Deployment script for Vue.js webapp to S3/CloudFront
- `package.json`: Root package.json (appears to be duplicate of webapp/package.json)

## Lambda Functions (`/lambdas/`)

Each Lambda function has its own directory with `index.py` and optional `requirements.txt`:

- **`poller/`**: Polls X API v2 for tweets, invokes parser in batches
- **`parser/`**: Processes tweet batches, extracts images, starts Step Function workflows
- **`rekognition/`**: Runs face detection and content moderation on images
- **`processFaces/`**: Processes Rekognition results, stores data via Firehose
- **`getStat/`**: API endpoint for dashboard statistics and metrics
- **`getImage/`**: API endpoint for retrieving processed images
- **`delImage/`**: API endpoint for deleting inappropriate images
- **`athenaQuery/`**: Executes Athena queries on S3 data
- **`glueDatabaseInit/`**: Custom resource for initializing Glue database

## Lambda Layers (`/layers/`)

Shared dependencies packaged as Lambda layers:

- **`core/`**: Common dependencies (requests, xray, metrics) with Makefile
- **`pandas/`**: Data processing libraries (pandas, numpy)

## Frontend Application (`/webapp/`)

Standard Vue.js 3 + Vite project structure:

- `src/App.vue`: Main application component with charts and image cards
- `src/components/`: Reusable Vue components (ImageCard, icons)
- `src/assets/`: Static assets (CSS, images)
- `package.json`: Frontend dependencies and build scripts
- `vite.config.js`: Vite build configuration

## Documentation (`/docs/`)

- `QUICK_START.md`: Fast deployment reference
- `MIGRATION_GUIDE.md`: X API v1.1 to v2 migration details
- `DEPLOYMENT_VERIFICATION.md`: Post-deployment verification steps
- `REKOGNITION_API_AUDIT.md`: Rekognition API usage documentation

## Architecture Patterns

### Lambda Function Structure
- All functions use `index.py` with `handler(event, context)` entry point
- AWS X-Ray tracing enabled with `@xray_recorder.capture` decorators
- CloudWatch Embedded Metrics using `@metric_scope` decorator
- Environment variables for configuration (table names, bucket names, etc.)
- Consistent error handling and logging patterns

### Data Flow
1. **Poller** → **Parser** (async invocation)
2. **Parser** → **Step Function** (Rekognition → ProcessFaces)
3. **ProcessFaces** → **Kinesis Firehose** → **S3** (Parquet)
4. **API Functions** ← **Frontend** (HTTP API calls)

### Configuration Management
- SSM Parameter Store for sensitive data (X API tokens)
- Environment variables for resource ARNs and names
- SAM template parameters for deployment customization