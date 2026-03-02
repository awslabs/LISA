# LISA Chat

This repository include an example chatbot web application. The react based web application can be optionally deployed to demonstrate the capabilities of LISA Serve. The chatbot consists of a static react based single page application hosted via API GW S3 proxy integration. The app connects to the LISA Serve REST API and an optional RAG API. The app integrates with an OIDC compatible IdP and allows users to interact directly with any of the textgen models hosted with LISA Serve. If the optional RAG stack is deployed then users can also leverage the embeddings models and AWS OpenSearch or PGVector to demonstrate chat with RAG. Chat sessions are maintained in dynamodb table and a number of parameters are exposed through the UI to allow experimentation with various parameters including prompt, temperature, top k, top p, max tokens, and more.

## Key Features

### Chat Assistant Stacks

When enabled by an administrator, the Chat UI shows a **Chat Assistants** section in the left pane (above History). Each assistant is a preconfigured stack of models, RAG repositories and collections, MCP servers and tools, and prompts. Clicking an assistant starts a new session with that configuration. Sessions appear in History and follow the same behavior as other chats (e.g. you can rename them; the model cannot be changed after selection). See [Chat Assistant Stacks](/config/chat-assistant-stacks) for administrator and user details.

### Document Summarization Feature

The Document Summarization feature enables efficient document processing through LISA's non-RAG context functionality. Users can streamline their workflow via an intuitive modal interface that facilitates document upload, LLM selection, and customized summarization template configuration. The system generates comprehensive document summaries tailored to specific requirements.

#### Core Components
- Document upload interface
- Environment-specific LLM integration
- Configurable summarization templates with customizable parameters
- Context-preserving file processing

#### Operational Workflow
1. Initiate summarization from active chat session
2. Upload target document for processing
3. Select appropriate LLM based on requirements
4. Configure summarization parameters via template selection/modification
5. Determine session continuity preference
6. Execute summarization request
7. Review generated summary in chat interface

#### Key Benefits
- Efficient information extraction and processing
- Flexible summarization parameters for diverse use cases
- Intuitive user interface optimized for accessibility
- Enhanced contextual accuracy through preserved document integrity

#### Administrative Configuration
LLM availability within the summarization modal requires summarization flagging and proper model configuration during initial setup. Selected LLMs must meet minimum requirements for:

- Context window capacity
- Token limit specifications
- Adequate hosting resource allocation

These parameters ensure optimal document parsing and request processing capabilities.

## Local development

### Configuring Pre-Commit Hooks

To ensure code quality and consistency, this project uses pre-commit hooks. These hooks are configured to perform checks, such as linting and formatting, helping to catch potential issues early. These hooks are run automatically on each push to a remote branch but if you wish to run them locally before each commit, follow these steps:

1. Install pre-commit: `pip install pre-commit`
2. Install the git hook scripts: `pre-commit install`

The hooks will now run automatically on changed files but if you wish to test them against all files, run the following command: `pre-commit run --all-files`.

### Run REST API locally

```
cd lib/serve/rest-api
pip install -r src/requirements.txt
export AWS_REGION=<Region where LISA is deployed>
export AUTHORITY=<IdP Endpoint>
export CLIENT_ID=<IdP Client Id>
export REGISTERED_MODELS_PS_NAME=<Models ParameterName>
export TOKEN_TABLE_NAME="<deployment prefix>/LISAApiTokenTable"
gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b "0.0.0.0:8080" "src.main:app"
```

### Run example chatbot locally

Create `lib/user-interface/react/public/env.js` file with the following contents:

```
window.env = {
  AUTHORITY: '<Your IdP URL here>',
  CLIENT_ID: '<Your IdP Client Id Here>',
  JWT_GROUPS_PROP: '<The full path (period delimited) to the property for the groups that a user is a member of in the JWT token. For Cognito: cognito:groups>',
  ADMIN_GROUP: '<The admin group you would like LISA to check the JWT token for>',
  CUSTOM_SCOPES:[<add your optional list of custom scopes to pull groups from your IdP here>],
  // Alternatively you can set this to be your REST api elb endpoint
  RESTAPI_URI: 'http://localhost:8080/',
  API_BASE_URL: 'https://${deployment_id}.execute-api.${regional_domain}/${deployment_stage}',
  RESTAPI_VERSION: 'v2',
  "MODELS": [
    {
      "model": "streaming-textgen-model",
      "streaming": true,
      "modelType": "textgen"
    },
    {
      "model": "non-streaming-textgen-model",
      "streaming": false,
      "modelType": "textgen"
    },
    {
      "model": "embedding-model",
      "streaming": null,
      "modelType": "embedding"
    }
  ]
}
```

Launch the Chat UI:

```
cd lib/user-interface/react/
npm run dev
```
