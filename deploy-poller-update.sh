#!/bin/bash

echo "Deploying improved X API polling system..."

# Build the SAM application
echo "Building SAM application..."
sam build

if [ $? -ne 0 ]; then
    echo "Build failed. Exiting."
    exit 1
fi

# Deploy the updated stack
echo "Deploying stack with twice-daily polling..."
sam deploy

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"
    echo "The poller will now run every 12 hours (twice daily) with improved rate limiting."
    echo "Check CloudWatch metrics for TweetsPolled, BatchesProcessed, and PollingErrors."
else
    echo "❌ Deployment failed."
    exit 1
fi
