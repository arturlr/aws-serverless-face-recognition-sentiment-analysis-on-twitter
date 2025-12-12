# Product Overview

## AWS Serverless Face Recognition Sentiment Analysis on X (Twitter)

This is a serverless application that analyzes emotions in selfie photos posted on X (formerly Twitter) using Amazon Rekognition. The app:

- Polls X API v2 for tweets containing "selfie" 
- Downloads and analyzes images using Amazon Rekognition for face detection and emotion analysis
- Stores results in DynamoDB and S3 (Parquet format via Kinesis Firehose)
- Provides a Vue.js web dashboard showing emotion rankings and statistics
- Uses AWS X-Ray for tracing and CloudWatch Embedded Metric Format for monitoring

## Key Features

- **Content Moderation**: Uses Rekognition's moderation features to filter inappropriate content
- **Emotion Analysis**: Detects and ranks emotions (happy, sad, etc.) from facial expressions
- **Real-time Dashboard**: Vue.js frontend with charts showing emotion statistics
- **Data Lifecycle**: Automatic cleanup with S3 lifecycle policies (2 days) and DynamoDB TTL (15 days)
- **Serverless Architecture**: Fully serverless using Lambda, Step Functions, and managed AWS services

## Authentication

Requires X API v2 Bearer Token stored in SSM Parameter Store under configurable prefix (default: `twitter-event-source`).