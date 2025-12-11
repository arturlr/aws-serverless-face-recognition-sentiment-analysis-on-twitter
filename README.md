## AWS Serverless face recognition sentiment analysis on X (formerly Twitter)

<img src="images/twitter-app.png" alt="app" width="1000"/>

In this Serverless app we show a rank of the happiest, saddest among other emotions [Amazon Rekognition](https://aws.amazon.com/rekognition/) can detect from posts on X (formerly Twitter) that have the word "selfie" in it. The app relies on lambda functions that extract, process, store and report the information from the X API v2.

The Amazon S3 bucket of this solution creates contains two [Object lifecycle management](https://docs.aws.amazon.com/AmazonS3/latest/dev/object-lifecycle-mgmt.html) for the folders where the reports and records files are stored, which expire the files 2 days after of its creation. Similarly, the dynamodb tables has a configured TTL that deletes content after 15 days of the item's creation automatically.

Below is the diagram for a depiction of the complete architecture.

<img src="images/twitter-rekognition.png" alt="architecture" width="800"/>

The solution also leverage the [Embedded Metric Format](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html) to create metrics for number of tweets that are being processed, number of images moderated and number of faces identified and processed by Amazon Rekognition and their emotions.

Another cool service used is [AWS X-Ray](https://aws.amazon.com/xray/) that allows you to understand how your application and its underlying services are performing to identify and troubleshoot the root cause of performance issues and errors.

## Initial environment setup

### Prerequisites

This app is deployed through AWS CloudFormation with an additional Vue.js application configuration. The following resources are required to be installed:

- [AWS SAM](https://aws.amazon.com/serverless/sam/) - The AWS Serverless Application Model (SAM) is an open-source framework for building serverless applications. It provides shorthand syntax to express functions, APIs, databases, and event source mappings.
- npm to be able to build the Vue.js app
- [AWS cli](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html) to be able to interact with the AWS resources
- AWS Account and permissition to create the resources.
- Python 3.8 or Docker installed in your local machine.

### Step 1: Create the X API v2 credentials

1. The solution requires X API v2 Bearer Token for authentication. The following steps walk you through obtaining these credentials from the X Developer Portal:
   - Create an X (Twitter) account if you do not already have one
   - Apply for a developer account at https://developer.x.com/
   - Create a Project in the X Developer Portal:
     - Go to https://developer.x.com/en/portal/dashboard
     - Click "Create Project" and follow the prompts
     - Provide a name and use case for your project
     - **Note**: X API v2 credentials must be associated with a Project
   - Create an App within your Project:
     - After creating a project, click "Add App" or "Create App"
     - Under Name, enter something descriptive (but unique), e.g., aws-serverless-x-sentiment-analysis
     - Enter a description for your app
   - (Optional, but recommended) Restrict the application permissions to read only:
     - From the detail page of your X application, click the "Settings" tab
     - Under "User authentication settings", ensure read-only access is configured
   - Generate a Bearer Token:
     - From your App page in the X Developer Portal, navigate to the "Keys and tokens" tab
     - Under "Bearer Token", click "Generate" to create a Bearer Token
     - **Important**: Save this token securely - you won't be able to see it again
     - This Bearer Token is used for OAuth 2.0 authentication with X API v2

2.  Store the Bearer Token as an encrypted SecureString value in SSM Parameter Store. You can setup the required parameter via the AWS Console or using the following AWS CLI command:
   
 ```bash
aws ssm put-parameter --name /twitter-event-source/bearer_token --value <your bearer token value> --type SecureString --overwrite
  ```

**Note**: The X API v2 uses OAuth 2.0 Bearer Token authentication, which is simpler than the OAuth 1.0a flow used by the deprecated v1.1 API. The old consumer key, consumer secret, access token, and access token secret parameters are no longer needed.

### Step 2: Build all the solution's libraries dependencies

1. The AWS Lambda functions requires libraries for their executions and SAM fetches and install them per each funtion. The *sam build* command creates a .aws-sam directory with the AWS SAM template, AWS Lambda function code, and any language-specific files and dependencies in a format ready to be deployed to AWS.
   
If you have Python 3.8 installed in your machine you can run:
   
```bash
sam build
```

Another option is to execute *sam build* using containers. It requires you to have docker installed :
```bash
sam build --use-container --build-image amazon/aws-sam-cli-build-image-python3.8
```

When the build finishes, you will receive a message like: 
```bash
Build Succeeded

Built Artifacts  : .aws-sam/build
Built Template   : .aws-sam/build/template.yaml

Commands you can use next
=========================
[*] Validate SAM template: sam validate
[*] Invoke Function: sam local invoke
[*] Test Function in the Cloud: sam sync --stack-name {{stack-name}} --watch
[*] Deploy: sam deploy --guided
```


### Step 3: Deploy the backend usins *sam deploy* 

1. Now it is time to deploy the solution to your AWS Account. The command will ask you a few questions. Below an example of the questions and answers you can provide. Make sure you selecte a region that [Amazon Rekognition](https://docs.aws.amazon.com/general/latest/gr/rekognition.html) supports *DetectFaces* and *DetectModerationLabels* operations (US East (N. Virginia), US West (Oregon), Asia Pacific (Mumbai), Europe (Frankfurt), Europe (Ireland)). If you try to deploy in regions where Amazon Rekognition doesn't support those operations, an error will be raised and the Stack won't be created. **Note**: Check if Amazon Rekognition supports all operations in the selected region.

```bash
sam deploy --guided --capabilities CAPABILITY_NAMED_IAM

Configuring SAM deploy
======================

        Looking for config file [samconfig.toml] :  Not found

        Setting default arguments for 'sam deploy'
        =========================================
        Stack Name [sam-app]: twitter-demo
        AWS Region [us-west-2]:
        Parameter GlueDatabaseName [twitter-db]:
        Parameter SearchText [selfie]:
        Parameter SSMParameterPrefix [twitter-event-source]:
        Parameter PollingFrequencyInMinutes [10]:
        Parameter BatchSize [15]:
        #Shows you resources changes to be deployed and require a 'Y' to initiate deploy
        Confirm changes before deploy [y/N]: y
        #SAM needs permission to be able to create roles to connect to the resources in your template
        Allow SAM CLI IAM role creation [Y/n]: y
        #Preserves the state of previously provisioned resources when an operation fails
        Disable rollback [y/N]: n
        GetStat may not have authorization defined, Is this okay? [y/N]: y
        GetImage may not have authorization defined, Is this okay? [y/N]: y
        DelImage may not have authorization defined, Is this okay? [y/N]: y
        Save arguments to configuration file [Y/n]: y
        SAM configuration file [samconfig.toml]:
        SAM configuration environment [default]:
```

Once AWS SAM deploy does it magic, all you need is to answer **Y** to proceed the deployment.

```bash
Previewing CloudFormation changeset before deployment
======================================================
Deploy this changeset? [y/N]: y
```

### Step 4: Deploy Vue.js app into S3

1. In this last step we will executes the script to publish the Vue.js application into your bucket that exposes it via Amazon Cloudfront. **The script requires the npm and aws cli installed**
```bash
./appDeploy.sh 
```

Once if finishes the script provides you the URL where the applicaton is running. Give it a few minutes so the solution can collect some data and transform it into parquet format. 

```bash
Site available at: https://<YourCloudFrontId>.cloudfront.net
```

:warning: **Important Note: Some Ad blocking apps can prevent the images to be shown.**

## Documentation

For detailed documentation about deployment, migration, and API usage, see the [docs](./docs) directory:

- [Quick Start Guide](./docs/QUICK_START.md) - Fast deployment reference
- [Migration Guide](./docs/MIGRATION_GUIDE.md) - Twitter API v1.1 to X API v2 migration details
- [Deployment Verification](./docs/DEPLOYMENT_VERIFICATION.md) - Post-deployment verification steps
- [Rekognition API Audit](./docs/REKOGNITION_API_AUDIT.md) - Amazon Rekognition API usage documentation 
