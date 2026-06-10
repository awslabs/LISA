# v6.7.0

## Key Features

### Session Refactor: Dedicated Messages Table with Context Compaction
A major architectural refactor of the LISA sessions system introduces a dedicated DynamoDB Messages table, separating message storage from session metadata storage. Previously, all chat messages were stored directly within the Sessions DynamoDB table; messages are now stored as individual records in a separate Messages table, while the Sessions table is reserved exclusively for session-level metadata.

**Key capabilities:**
- **Message Storage**: Each message exists as its own independent record in the new Messages DynamoDB table, improving scalability and query flexibility
- **Context Window Compaction**: As a user approaches  utilization of a model's context window, sessions are automatically compacted and summarized to prevent context overflow
- **Summary Visibility**: Compaction summaries are visible directly in the UI and are appended to the end of the system prompt, giving users full transparency into context management
- **Session Metadata**: The Sessions table continues to serve as the authoritative store for session-level metadata, providing a clean separation of concerns between messages and sessions

---

### OpenSearch Hybrid RAG
Introduces hybrid search support for OpenSearch-backed RAG (Retrieval-Augmented Generation) pipelines, combining vector similarity search with keyword-based search to improve retrieval quality and relevance across a broader range of query types.

---

### Hybrid Search Support for Bedrock Knowledge Bases
Extends hybrid search capabilities to Amazon Bedrock Knowledge Base repositories, enabling both vector and keyword search to work in tandem when querying Bedrock KB-backed repositories.

**Key behaviors:**
- **Admin Gate**: The admin toggle acts as a hard gate — disabling hybrid search forces all sessions to use vector-only search, regardless of individual user selection
- **Conditional UI**: The search mode selector is displayed in the UI only when the repository supports hybrid search, keeping the interface clean for non-hybrid configurations
- **Automatic Fallback**: Unsupported knowledge bases automatically fall back to vector-only search, ensuring compatibility across all Bedrock KB configurations
- **Citation Display**: Citations are rendered correctly under both hybrid and vector-only search modes

---

### Image Generation with Context Fix
Resolves two related issues with image generation in the chat interface when contextual references are present:
- **Image Reference During Generation**: Fixed an issue where the chat was not correctly referencing an attached image during the image generation workflow
- **Reference Cleanup**: Fixed an issue where removing an image reference was not properly clearing other associated references, causing stale context to persist in subsequent interactions

---

### React Compiler Enabled
The React compiler has been enabled for the LISA frontend, providing automatic memoization and optimization of React component rendering without requiring manual , , or  annotations.

**Supporting changes:**
- **Linting Updates**: Updated linting configuration to align with React compiler requirements and enforce compatible coding patterns
- **LiteLLM Config Passthrough**: Updated the LiteLLM configuration passthrough logic to resolve compatibility issues surfaced during the compiler migration

---

### Lambda Refactor and Cleanup
A comprehensive cleanup and refactoring of the Lambda function implementation improves code organization, maintainability, and module resolution across the serverless backend.

**Component updates:**
- **Module Path Fix (Batch Ingestion)**: Updated the Batch ingestion job container command from  to  to align with the new module layout established by the lambda refactor
- **Python Path Resolution**: Added  to the Batch ingestion container environment so the shared  package is correctly importable at runtime
- **CDK Snapshots**: Updated CDK snapshot baselines for , , and  stacks to reflect the refactored module structure

---

### DynamoDB Decimal Serialization Fix
Resolves a bug in the session API where DynamoDB  values were being incorrectly serialized as strings in API responses instead of JSON numbers.

**Root cause and fix:**
- **Problem**: All numbers stored in DynamoDB are returned by boto3 as Python  objects. When Pydantic models with -typed fields (e.g., ) were serialized using , the  method would convert  values to strings
- **Fix**: Changed  to  at two call sites in , ensuring  values are properly represented as JSON numbers in all API responses

---

### MCP Server Deployment Fixes
Resolved multiple deployment and runtime issues affecting the MCP (Model Context Protocol) server:

- **CORS Allowed Origins**: Fixed the  configuration for MCP server deployments to ensure cross-origin requests are correctly permitted
- **MCP Workbench Error**: Fixed an error introduced during the MCP Workbench upgrade that was causing runtime failures
- **Client Issues**: Resolved various client-side issues identified during MCP integration testing and deployment validation

---

### AWS Credentials and Environment Variable Improvements
Enhancements to AWS credential parsing and environment configuration improve compatibility and flexibility for diverse deployment scenarios:

- **Export Block Credential Parsing**: Added support for parsing AWS credentials provided in declare -x ACCEPT_EULA="Y"
declare -x ACTIONS_ID_TOKEN_REQUEST_TOKEN="eyJhbGciOiJSUzI1NiIsImtpZCI6IjM4ODI2YjE3LTZhMzAtNWY5Yi1iMTY5LThiZWI4MjAyZjcyMyIsInR5cCI6IkpXVCIsIng1dCI6InlrTmFZNHFNX3RhNGsyVGdaT0NFWUxrY1lsQSJ9.eyJJZGVudGl0eVR5cGVDbGFpbSI6IlN5c3RlbTpTZXJ2aWNlSWRlbnRpdHkiLCJhYyI6Ilt7XCJTY29wZVwiOlwicmVmcy9oZWFkcy9kZXZlbG9wXCIsXCJQZXJtaXNzaW9uXCI6M30se1wiU2NvcGVcIjpcInJlZnMvaGVhZHMvbWFpblwiLFwiUGVybWlzc2lvblwiOjF9XSIsImFjc2wiOiIxMCIsImF1ZCI6InZzbzo2YjYxMzhiZi0wYjRhLTQ0NDgtYWUzMy0yMzFiY2Y3NDc5NTMiLCJiaWxsaW5nX293bmVyX2lkIjoiRV9rZ0ROQlFvIiwiZXhwIjoxNzgxMTQ1MjE2LCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3ByaW1hcnlzaWQiOiJkZGRkZGRkZC1kZGRkLWRkZGQtZGRkZC1kZGRkZGRkZGRkZGQiLCJodHRwOi8vc2NoZW1hcy54bWxzb2FwLm9yZy93cy8yMDA1LzA1L2lkZW50aXR5L2NsYWltcy9zaWQiOiJkZGRkZGRkZC1kZGRkLWRkZGQtZGRkZC1kZGRkZGRkZGRkZGQiLCJpYXQiOjE3ODExMjMwMTYsImlzcyI6Imh0dHBzOi8vdG9rZW4uYWN0aW9ucy5naXRodWJ1c2VyY29udGVudC5jb20iLCJqb2JfaWQiOiJkNzBiOGRhYy0zMjlhLTUzYTUtYmQwZi0zZjE4NjZhZWU1Y2QiLCJuYW1laWQiOiJkZGRkZGRkZC1kZGRkLWRkZGQtZGRkZC1kZGRkZGRkZGRkZGQiLCJuYmYiOjE3ODExMjI3MTYsIm9pZGNfZXh0cmEiOiJ7XCJhY3RvclwiOlwiZXN0b2hsbWFublwiLFwiYWN0b3JfaWRcIjpcIjE0MTAwOTcyXCIsXCJiYXNlX3JlZlwiOlwiXCIsXCJjaGVja19ydW5faWRcIjpcIjgwNjU2NzUwMTkxXCIsXCJlbnZpcm9ubWVudFwiOlwiZGV2XCIsXCJlbnZpcm9ubWVudF9ub2RlX2lkXCI6XCJFTl9rd0RPTDdrUUVzOEFBQUFCQ092SGxRXCIsXCJldmVudF9uYW1lXCI6XCJ3b3JrZmxvd19kaXNwYXRjaFwiLFwiaGVhZF9yZWZcIjpcIlwiLFwiam9iX3dvcmtmbG93X3JlZlwiOlwiYXdzbGFicy9MSVNBLy5naXRodWIvd29ya2Zsb3dzL2NvZGUucmVsZWFzZS5icmFuY2gueW1sQHJlZnMvaGVhZHMvZGV2ZWxvcFwiLFwiam9iX3dvcmtmbG93X3NoYVwiOlwiZDNlYzgyODI2NmNmZmY3ZmJkODk0Y2VlNmQ5OTE0YjUzZDBkYmJjY1wiLFwicmVmXCI6XCJyZWZzL2hlYWRzL2RldmVsb3BcIixcInJlZl9wcm90ZWN0ZWRcIjpcInRydWVcIixcInJlZl90eXBlXCI6XCJicmFuY2hcIixcInJlcG9zaXRvcnlcIjpcImF3c2xhYnMvTElTQVwiLFwicmVwb3NpdG9yeV9pZFwiOlwiODAwNjU3NDI2XCIsXCJyZXBvc2l0b3J5X293bmVyXCI6XCJhd3NsYWJzXCIsXCJyZXBvc2l0b3J5X293bmVyX2lkXCI6XCIzMjk5MTQ4XCIsXCJyZXBvc2l0b3J5X3Zpc2liaWxpdHlcIjpcInB1YmxpY1wiLFwicnVuX2F0dGVtcHRcIjpcIjJcIixcInJ1bl9pZFwiOlwiMjczMDM4MTE2NzNcIixcInJ1bl9udW1iZXJcIjpcIjY1XCIsXCJydW5uZXJfZW52aXJvbm1lbnRcIjpcImdpdGh1Yi1ob3N0ZWRcIixcInNoYVwiOlwiZDNlYzgyODI2NmNmZmY3ZmJkODk0Y2VlNmQ5OTE0YjUzZDBkYmJjY1wiLFwid29ya2Zsb3dcIjpcIk1ha2UgUmVsZWFzZSBCcmFuY2hcIixcIndvcmtmbG93X3JlZlwiOlwiYXdzbGFicy9MSVNBLy5naXRodWIvd29ya2Zsb3dzL2NvZGUucmVsZWFzZS5icmFuY2gueW1sQHJlZnMvaGVhZHMvZGV2ZWxvcFwiLFwid29ya2Zsb3dfc2hhXCI6XCJkM2VjODI4MjY2Y2ZmZjdmYmQ4OTRjZWU2ZDk5MTRiNTNkMGRiYmNjXCJ9Iiwib2lkY19zdWIiOiJyZXBvOmF3c2xhYnMvTElTQTplbnZpcm9ubWVudDpkZXYiLCJvcmNoX2lkIjoiZGU0ZGYwNzEtYmVmYS00ODJjLWI0M2MtYjhiYzZmYzVhNGIzLk1ha2VOZXdSZWxlYXNlQnJhbmNoLl9fZGVmYXVsdCIsIm93bmVyX2lkIjoiRV9rZ0ROQlFvIiwicGxhbl9pZCI6ImRlNGRmMDcxLWJlZmEtNDgyYy1iNDNjLWI4YmM2ZmM1YTRiMyIsInJlcG9zaXRvcnlfaWQiOiI4MDA2NTc0MjYiLCJyZXBvc2l0b3J5X293bmVyX2lkIjoiMzI5OTE0OCIsInJlcG9zaXRvcnlfdmlzaWJpbGl0eSI6InB1YmxpYyIsInJ1bl9pZCI6IjI3MzAzODExNjczIiwicnVuX251bWJlciI6IjY1IiwicnVuX3R5cGUiOiJmdWxsIiwicnVubmVyX2lkIjoiMTAyMDYxNzAyNSIsInJ1bm5lcl90eXBlIjoiaG9zdGVkIiwic2NwIjoiQWN0aW9ucy5SZXN1bHRzOmRlNGRmMDcxLWJlZmEtNDgyYy1iNDNjLWI4YmM2ZmM1YTRiMzpkNzBiOGRhYy0zMjlhLTUzYTUtYmQwZi0zZjE4NjZhZWU1Y2QgQWN0aW9ucy5SdW5uZXI6ZGU0ZGYwNzEtYmVmYS00ODJjLWI0M2MtYjhiYzZmYzVhNGIzOmQ3MGI4ZGFjLTMyOWEtNTNhNS1iZDBmLTNmMTg2NmFlZTVjZCBBY3Rpb25zLlVwbG9hZEFydGlmYWN0czpkZTRkZjA3MS1iZWZhLTQ4MmMtYjQzYy1iOGJjNmZjNWE0YjM6ZDcwYjhkYWMtMzI5YS01M2E1LWJkMGYtM2YxODY2YWVlNWNkIGdlbmVyYXRlX2lkX3Rva2VuOmRlNGRmMDcxLWJlZmEtNDgyYy1iNDNjLWI4YmM2ZmM1YTRiMzpkNzBiOGRhYy0zMjlhLTUzYTUtYmQwZi0zZjE4NjZhZWU1Y2QgQWN0aW9ucy5HZW5lcmljUmVhZDowMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDAiLCJzaGEiOiJkM2VjODI4MjY2Y2ZmZjdmYmQ4OTRjZWU2ZDk5MTRiNTNkMGRiYmNjIiwidHJ1c3RfdGllciI6IjEifQ.DlkT7ndCVBVVrFs9BEsl_r_b6V7HxL6bhY-TmYVW4wW9kDTZcAf-amdDueUBWp4sVTf5vM7Plmb2NxW9h3wxSbTZ-T6sH3rDW9LfbexZMBbM_OpZUQgsC2Pvex9QpNB0P82f34YxLS9ML2-_15_tXi9Qb3HIsoB6yXVM2_GaRGQ5eWko-AKUxS-_eXmGW-Lpa4uo0p4w_22n8o1dRt2VKby3XDhOk86IyQgxohZ4CVZ7pylvoT3T3idWVU3K3OeRgZk-_wPMojmvYgzxAwrENZ6GOSmtdFziIPOKwo6CzQVnI9J6e19DbZP8E5U7BvMFibPNiHLWRiZe6IwAIKL53w"
declare -x ACTIONS_ID_TOKEN_REQUEST_URL="https://run-actions-3-azure-eastus.actions.githubusercontent.com/213//idtoken/de4df071-befa-482c-b43c-b8bc6fc5a4b3/d70b8dac-329a-53a5-bd0f-3f1866aee5cd?api-version=2.0"
declare -x ACTIONS_ORCHESTRATION_ID="de4df071-befa-482c-b43c-b8bc6fc5a4b3.MakeNewReleaseBranch.__default"
declare -x ACTIONS_RUNNER_ACTION_ARCHIVE_CACHE="/opt/actionarchivecache"
declare -x ACTIONS_RUNNER_RETURN_JOB_RESULT_FOR_HOSTED="1"
declare -x AGENT_TOOLSDIRECTORY="/opt/hostedtoolcache"
declare -x ANDROID_HOME="/usr/local/lib/android/sdk"
declare -x ANDROID_NDK="/usr/local/lib/android/sdk/ndk/27.3.13750724"
declare -x ANDROID_NDK_HOME="/usr/local/lib/android/sdk/ndk/27.3.13750724"
declare -x ANDROID_NDK_LATEST_HOME="/usr/local/lib/android/sdk/ndk/29.0.14206865"
declare -x ANDROID_NDK_ROOT="/usr/local/lib/android/sdk/ndk/27.3.13750724"
declare -x ANDROID_SDK_ROOT="/usr/local/lib/android/sdk"
declare -x ANT_HOME="/usr/share/ant"
declare -x AWS_ACCESS_KEY_ID="ASIA3LET5VD6RMXUBWYS"
declare -x AWS_DEFAULT_REGION="us-east-1"
declare -x AWS_REGION="us-east-1"
declare -x AWS_SECRET_ACCESS_KEY="xK4BmRqLBDmtOD1JnF5CI3XeRO0N4bnmqWJbhBSq"
declare -x AWS_SESSION_TOKEN="IQoJb3JpZ2luX2VjECUaCXVzLWVhc3QtMSJIMEYCIQDGc46bgvhZYFO2P9w2PeZactS0+g6pX4YVSOZGZfeBJgIhAItB6XTlNt0IDbSK+5z8Bi05EvSKkezi217tZ9kaKx4yKvADCO7//////////wEQABoMNzc5ODQ2Nzg5MzczIgw/FBHlGFAASgksATkqxAPNTV9vi3va2fM1owbhlwBEM3E55O6yiGKL8z0iV3SdmO66i9NsCeMrsEB/N5Bf61XqAOY3CAWx1y7LWt/gCQrSUjv/e6uE+fdWridmAPEUgY2SS1tgRr0MRoiGwgLnK9WyC6EaPbO2+FMkIBQkJpk0woaOTM1uCW2mpNHiUkInloegrOAz4iMny3vkGkMdvjS5+w58hzXaJmQxe8MhAwXyLj4ec6KstiMuVZRZuguYOjgelD4zFEDYzPm3FueQ6IM553t8tlYBzvA/ELauUvFnFr+eG4TtXHr4bjPRTpIDMXwoHb1tw+5Zr02ghn/3TdXvTdButD00Pr0Kel9Q2pgHUg4Q0TyYCGZMLjVuypdAxdPhcjkTMNluTkfCn/UGWixfYfgmOUhb9s6YNnrNjrTlWsABZ52tJcx74NKY331zx4FOXbUrmGgiNoYRFIR23umPK4Ula9wFwRalg9rUfjuUxArch1oseCmoi/lhRcXLUDFEGswtjiLFGdA1VXirz9hsK9vo96d4EgGxXDhskl3rpoyqxQOdjKnLRXY5f9QUO7e4n3gxobbbqso+22w8qx290pyRnuGZYQghgUwtjhA5al6h3TDNj6fRBjqRAYaVAEWfkrjdPMTNpoB4ts2WCb6GifdhpmiqRKxPrBAHyPPDn+a6tlAGf4nRs11wSYWsgy/M9QKCY2sWe4UiZmrQX59hj8FjNsOlb1TtzroktMMa3qfXlKtg5/Fc4hAI2ictxRHJHTepH0ni3vMUeK/2tqIvDYKIJvMB6zgkOHLN/X4HfCWnGfzhMS8LnITAKGM="
declare -x AZURE_EXTENSION_DIR="/opt/az/azcliextensions"
declare -x BOOTSTRAP_HASKELL_NONINTERACTIVE="1"
declare -x CHROMEWEBDRIVER="/usr/local/share/chromedriver-linux64"
declare -x CHROME_BIN="/usr/bin/google-chrome"
declare -x CI="true"
declare -x CONDA="/usr/share/miniconda"
declare -x DEBIAN_FRONTEND="noninteractive"
declare -x DOTNET_MULTILEVEL_LOOKUP="0"
declare -x DOTNET_NOLOGO="1"
declare -x DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1"
declare -x EDGEWEBDRIVER="/usr/local/share/edge_driver"
declare -x ENABLE_RUNNER_TRACING="true"
declare -x GECKOWEBDRIVER="/usr/local/share/gecko_driver"
declare -x GHCUP_INSTALL_BASE_PREFIX="/usr/local"
declare -x GITHUB_ACTION="__run_2"
declare -x GITHUB_ACTIONS="true"
declare -x GITHUB_ACTION_REF=""
declare -x GITHUB_ACTION_REPOSITORY=""
declare -x GITHUB_ACTOR="estohlmann"
declare -x GITHUB_ACTOR_ID="14100972"
declare -x GITHUB_API_URL="https://api.github.com"
declare -x GITHUB_BASE_REF=""
declare -x GITHUB_ENV="/home/runner/work/_temp/_runner_file_commands/set_env_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_EVENT_NAME="workflow_dispatch"
declare -x GITHUB_EVENT_PATH="/home/runner/work/_temp/_github_workflow/event.json"
declare -x GITHUB_GRAPHQL_URL="https://api.github.com/graphql"
declare -x GITHUB_HEAD_REF=""
declare -x GITHUB_JOB="MakeNewReleaseBranch"
declare -x GITHUB_OUTPUT="/home/runner/work/_temp/_runner_file_commands/set_output_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_PATH="/home/runner/work/_temp/_runner_file_commands/add_path_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_REF="refs/heads/develop"
declare -x GITHUB_REF_NAME="develop"
declare -x GITHUB_REF_PROTECTED="true"
declare -x GITHUB_REF_TYPE="branch"
declare -x GITHUB_REPOSITORY="awslabs/LISA"
declare -x GITHUB_REPOSITORY_ID="800657426"
declare -x GITHUB_REPOSITORY_OWNER="awslabs"
declare -x GITHUB_REPOSITORY_OWNER_ID="3299148"
declare -x GITHUB_RETENTION_DAYS="90"
declare -x GITHUB_RUN_ATTEMPT="2"
declare -x GITHUB_RUN_ID="27303811673"
declare -x GITHUB_RUN_NUMBER="65"
declare -x GITHUB_SERVER_URL="https://github.com"
declare -x GITHUB_SHA="d3ec828266cfff7fbd894cee6d9914b53d0dbbcc"
declare -x GITHUB_STATE="/home/runner/work/_temp/_runner_file_commands/save_state_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_STEP_SUMMARY="/home/runner/work/_temp/_runner_file_commands/step_summary_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_TRIGGERING_ACTOR="estohlmann"
declare -x GITHUB_WORKFLOW="Make Release Branch"
declare -x GITHUB_WORKFLOW_REF="awslabs/LISA/.github/workflows/code.release.branch.yml@refs/heads/develop"
declare -x GITHUB_WORKFLOW_SHA="d3ec828266cfff7fbd894cee6d9914b53d0dbbcc"
declare -x GITHUB_WORKSPACE="/home/runner/work/LISA/LISA"
declare -x GOROOT_1_22_X64="/opt/hostedtoolcache/go/1.22.12/x64"
declare -x GOROOT_1_23_X64="/opt/hostedtoolcache/go/1.23.12/x64"
declare -x GOROOT_1_24_X64="/opt/hostedtoolcache/go/1.24.13/x64"
declare -x GOROOT_1_25_X64="/opt/hostedtoolcache/go/1.25.10/x64"
declare -x GRADLE_HOME="/usr/share/gradle-9.5.1"
declare -x HOME="/home/runner"
declare -x HOMEBREW_CLEANUP_PERIODIC_FULL_DAYS="3650"
declare -x HOMEBREW_NO_AUTO_UPDATE="1"
declare -x INVOCATION_ID="a62f0c9147f3428ea44c407352e6435a"
declare -x ImageOS="ubuntu24"
declare -x ImageVersion="20260525.161.1"
declare -x JAVA_HOME="/usr/lib/jvm/temurin-17-jdk-amd64"
declare -x JAVA_HOME_11_X64="/usr/lib/jvm/temurin-11-jdk-amd64"
declare -x JAVA_HOME_17_X64="/usr/lib/jvm/temurin-17-jdk-amd64"
declare -x JAVA_HOME_21_X64="/usr/lib/jvm/temurin-21-jdk-amd64"
declare -x JAVA_HOME_25_X64="/usr/lib/jvm/temurin-25-jdk-amd64"
declare -x JAVA_HOME_8_X64="/usr/lib/jvm/temurin-8-jdk-amd64"
declare -x JOURNAL_STREAM="9:13712"
declare -x LANG="C.UTF-8"
declare -x LOGNAME="runner"
declare -x MEMORY_PRESSURE_WATCH="/sys/fs/cgroup/system.slice/hosted-compute-agent.service/memory.pressure"
declare -x MEMORY_PRESSURE_WRITE="c29tZSAyMDAwMDAgMjAwMDAwMAA="
declare -x NVM_DIR="/home/runner/.nvm"
declare -x OLDPWD
declare -x PATH="/snap/bin:/home/runner/.local/bin:/opt/pipx_bin:/home/runner/.cargo/bin:/home/runner/.config/composer/vendor/bin:/usr/local/.ghcup/bin:/home/runner/.dotnet/tools:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin"
declare -x PIPX_BIN_DIR="/opt/pipx_bin"
declare -x PIPX_HOME="/opt/pipx"
declare -x POWERSHELL_DISTRIBUTION_CHANNEL="GitHub-Actions-Linux"
declare -x PSModulePath="/root/.local/share/powershell/Modules:/usr/local/share/powershell/Modules:/opt/microsoft/powershell/7/Modules:/usr/share/az_14.6.0"
declare -x PWD="/home/runner/work/LISA/LISA"
declare -x RUNNER_ARCH="X64"
declare -x RUNNER_ENVIRONMENT="github-hosted"
declare -x RUNNER_NAME="GitHub Actions 1020617025"
declare -x RUNNER_OS="Linux"
declare -x RUNNER_TEMP="/home/runner/work/_temp"
declare -x RUNNER_TOOL_CACHE="/opt/hostedtoolcache"
declare -x RUNNER_TRACKING_ID="github_d1c4cd78-6dc5-4007-8936-0e352760b785"
declare -x RUNNER_WORKSPACE="/home/runner/work/LISA"
declare -x SELENIUM_JAR_PATH="/usr/share/java/selenium-server.jar"
declare -x SGX_AESM_ADDR="1"
declare -x SHELL="/bin/bash"
declare -x SHLVL="1"
declare -x SWIFT_PATH="/usr/share/swift/usr/bin"
declare -x SYSTEMD_EXEC_PID="2092"
declare -x USER="runner"
declare -x USE_BAZEL_FALLBACK_VERSION="silent:"
declare -x VCPKG_INSTALLATION_ROOT="/usr/local/share/vcpkg"
declare -x XDG_CONFIG_HOME="/home/runner/.config"
declare -x XDG_RUNTIME_DIR="/run/user/1001" block format, broadening the range of credential input styles that LISA can process
- **ENV_VAR Helper Indentation Fix**: Corrected an indentation issue in the  ENV_VAR helper that was causing formatting and parsing inconsistencies
- **Default AWS Session Region**: Fixed the default AWS session region parameter to ensure correct region resolution when no explicit region is provided

---

### Default Hosted Instance Type Update
Updated the default hosted instance type to a more appropriate default, ensuring new deployments use an optimized instance configuration out of the box without requiring manual override.

---

### Automated PR Description Script Updates
Iterative improvements to the automated pull request description generation script, refining the tooling used to produce consistent and comprehensive release notes across LISA releases.

---

## Key Changes
- **Architecture**: Migrated chat message storage from the Sessions DynamoDB table to a dedicated Messages DynamoDB table, with the Sessions table now serving exclusively as a metadata store
- **Context Management**: Implemented automatic session compaction and summarization at  context window utilization, with summary visibility in the UI and system prompt
- **RAG**: Added hybrid search (vector + keyword) support for OpenSearch-backed RAG pipelines
- **RAG**: Added hybrid search support for Bedrock Knowledge Base repositories with admin-controlled gating, automatic fallback, and conditional UI rendering
- **Bug Fix**: Resolved image generation issue where attached images were not correctly referenced during generation and where removing image references left stale context
- **Bug Fix**: Fixed DynamoDB  values being serialized as strings in session API responses by switching from  to  in 
- **Bug Fix**: Updated Batch ingestion container module path from  to  following lambda refactor
- **Bug Fix**: Added  to Batch ingestion container environment to resolve shared package import failures
- **Bug Fix**: Fixed  configuration for MCP server deployments
- **Bug Fix**: Fixed MCP Workbench error introduced during upgrade
- **Bug Fix**: Corrected ENV_VAR helper indentation in 
- **Bug Fix**: Fixed default AWS session region parameter resolution
- **Frontend**: Enabled the React compiler for automatic component optimization and memoization
- **Frontend**: Updated linting rules to align with React compiler compatibility requirements
- **Frontend**: Fixed LiteLLM config passthrough behavior
- **Infrastructure**: Updated default hosted instance type for new deployments
- **Infrastructure**: Refactored and cleaned up Lambda function implementation for improved maintainability
- **Infrastructure**: Updated CDK snapshot baselines for , , and  stacks
- **Credentials**: Added support for parsing AWS credentials in declare -x ACCEPT_EULA="Y"
declare -x ACTIONS_ID_TOKEN_REQUEST_TOKEN="eyJhbGciOiJSUzI1NiIsImtpZCI6IjM4ODI2YjE3LTZhMzAtNWY5Yi1iMTY5LThiZWI4MjAyZjcyMyIsInR5cCI6IkpXVCIsIng1dCI6InlrTmFZNHFNX3RhNGsyVGdaT0NFWUxrY1lsQSJ9.eyJJZGVudGl0eVR5cGVDbGFpbSI6IlN5c3RlbTpTZXJ2aWNlSWRlbnRpdHkiLCJhYyI6Ilt7XCJTY29wZVwiOlwicmVmcy9oZWFkcy9kZXZlbG9wXCIsXCJQZXJtaXNzaW9uXCI6M30se1wiU2NvcGVcIjpcInJlZnMvaGVhZHMvbWFpblwiLFwiUGVybWlzc2lvblwiOjF9XSIsImFjc2wiOiIxMCIsImF1ZCI6InZzbzo2YjYxMzhiZi0wYjRhLTQ0NDgtYWUzMy0yMzFiY2Y3NDc5NTMiLCJiaWxsaW5nX293bmVyX2lkIjoiRV9rZ0ROQlFvIiwiZXhwIjoxNzgxMTQ1MjE2LCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3ByaW1hcnlzaWQiOiJkZGRkZGRkZC1kZGRkLWRkZGQtZGRkZC1kZGRkZGRkZGRkZGQiLCJodHRwOi8vc2NoZW1hcy54bWxzb2FwLm9yZy93cy8yMDA1LzA1L2lkZW50aXR5L2NsYWltcy9zaWQiOiJkZGRkZGRkZC1kZGRkLWRkZGQtZGRkZC1kZGRkZGRkZGRkZGQiLCJpYXQiOjE3ODExMjMwMTYsImlzcyI6Imh0dHBzOi8vdG9rZW4uYWN0aW9ucy5naXRodWJ1c2VyY29udGVudC5jb20iLCJqb2JfaWQiOiJkNzBiOGRhYy0zMjlhLTUzYTUtYmQwZi0zZjE4NjZhZWU1Y2QiLCJuYW1laWQiOiJkZGRkZGRkZC1kZGRkLWRkZGQtZGRkZC1kZGRkZGRkZGRkZGQiLCJuYmYiOjE3ODExMjI3MTYsIm9pZGNfZXh0cmEiOiJ7XCJhY3RvclwiOlwiZXN0b2hsbWFublwiLFwiYWN0b3JfaWRcIjpcIjE0MTAwOTcyXCIsXCJiYXNlX3JlZlwiOlwiXCIsXCJjaGVja19ydW5faWRcIjpcIjgwNjU2NzUwMTkxXCIsXCJlbnZpcm9ubWVudFwiOlwiZGV2XCIsXCJlbnZpcm9ubWVudF9ub2RlX2lkXCI6XCJFTl9rd0RPTDdrUUVzOEFBQUFCQ092SGxRXCIsXCJldmVudF9uYW1lXCI6XCJ3b3JrZmxvd19kaXNwYXRjaFwiLFwiaGVhZF9yZWZcIjpcIlwiLFwiam9iX3dvcmtmbG93X3JlZlwiOlwiYXdzbGFicy9MSVNBLy5naXRodWIvd29ya2Zsb3dzL2NvZGUucmVsZWFzZS5icmFuY2gueW1sQHJlZnMvaGVhZHMvZGV2ZWxvcFwiLFwiam9iX3dvcmtmbG93X3NoYVwiOlwiZDNlYzgyODI2NmNmZmY3ZmJkODk0Y2VlNmQ5OTE0YjUzZDBkYmJjY1wiLFwicmVmXCI6XCJyZWZzL2hlYWRzL2RldmVsb3BcIixcInJlZl9wcm90ZWN0ZWRcIjpcInRydWVcIixcInJlZl90eXBlXCI6XCJicmFuY2hcIixcInJlcG9zaXRvcnlcIjpcImF3c2xhYnMvTElTQVwiLFwicmVwb3NpdG9yeV9pZFwiOlwiODAwNjU3NDI2XCIsXCJyZXBvc2l0b3J5X293bmVyXCI6XCJhd3NsYWJzXCIsXCJyZXBvc2l0b3J5X293bmVyX2lkXCI6XCIzMjk5MTQ4XCIsXCJyZXBvc2l0b3J5X3Zpc2liaWxpdHlcIjpcInB1YmxpY1wiLFwicnVuX2F0dGVtcHRcIjpcIjJcIixcInJ1bl9pZFwiOlwiMjczMDM4MTE2NzNcIixcInJ1bl9udW1iZXJcIjpcIjY1XCIsXCJydW5uZXJfZW52aXJvbm1lbnRcIjpcImdpdGh1Yi1ob3N0ZWRcIixcInNoYVwiOlwiZDNlYzgyODI2NmNmZmY3ZmJkODk0Y2VlNmQ5OTE0YjUzZDBkYmJjY1wiLFwid29ya2Zsb3dcIjpcIk1ha2UgUmVsZWFzZSBCcmFuY2hcIixcIndvcmtmbG93X3JlZlwiOlwiYXdzbGFicy9MSVNBLy5naXRodWIvd29ya2Zsb3dzL2NvZGUucmVsZWFzZS5icmFuY2gueW1sQHJlZnMvaGVhZHMvZGV2ZWxvcFwiLFwid29ya2Zsb3dfc2hhXCI6XCJkM2VjODI4MjY2Y2ZmZjdmYmQ4OTRjZWU2ZDk5MTRiNTNkMGRiYmNjXCJ9Iiwib2lkY19zdWIiOiJyZXBvOmF3c2xhYnMvTElTQTplbnZpcm9ubWVudDpkZXYiLCJvcmNoX2lkIjoiZGU0ZGYwNzEtYmVmYS00ODJjLWI0M2MtYjhiYzZmYzVhNGIzLk1ha2VOZXdSZWxlYXNlQnJhbmNoLl9fZGVmYXVsdCIsIm93bmVyX2lkIjoiRV9rZ0ROQlFvIiwicGxhbl9pZCI6ImRlNGRmMDcxLWJlZmEtNDgyYy1iNDNjLWI4YmM2ZmM1YTRiMyIsInJlcG9zaXRvcnlfaWQiOiI4MDA2NTc0MjYiLCJyZXBvc2l0b3J5X293bmVyX2lkIjoiMzI5OTE0OCIsInJlcG9zaXRvcnlfdmlzaWJpbGl0eSI6InB1YmxpYyIsInJ1bl9pZCI6IjI3MzAzODExNjczIiwicnVuX251bWJlciI6IjY1IiwicnVuX3R5cGUiOiJmdWxsIiwicnVubmVyX2lkIjoiMTAyMDYxNzAyNSIsInJ1bm5lcl90eXBlIjoiaG9zdGVkIiwic2NwIjoiQWN0aW9ucy5SZXN1bHRzOmRlNGRmMDcxLWJlZmEtNDgyYy1iNDNjLWI4YmM2ZmM1YTRiMzpkNzBiOGRhYy0zMjlhLTUzYTUtYmQwZi0zZjE4NjZhZWU1Y2QgQWN0aW9ucy5SdW5uZXI6ZGU0ZGYwNzEtYmVmYS00ODJjLWI0M2MtYjhiYzZmYzVhNGIzOmQ3MGI4ZGFjLTMyOWEtNTNhNS1iZDBmLTNmMTg2NmFlZTVjZCBBY3Rpb25zLlVwbG9hZEFydGlmYWN0czpkZTRkZjA3MS1iZWZhLTQ4MmMtYjQzYy1iOGJjNmZjNWE0YjM6ZDcwYjhkYWMtMzI5YS01M2E1LWJkMGYtM2YxODY2YWVlNWNkIGdlbmVyYXRlX2lkX3Rva2VuOmRlNGRmMDcxLWJlZmEtNDgyYy1iNDNjLWI4YmM2ZmM1YTRiMzpkNzBiOGRhYy0zMjlhLTUzYTUtYmQwZi0zZjE4NjZhZWU1Y2QgQWN0aW9ucy5HZW5lcmljUmVhZDowMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDAiLCJzaGEiOiJkM2VjODI4MjY2Y2ZmZjdmYmQ4OTRjZWU2ZDk5MTRiNTNkMGRiYmNjIiwidHJ1c3RfdGllciI6IjEifQ.DlkT7ndCVBVVrFs9BEsl_r_b6V7HxL6bhY-TmYVW4wW9kDTZcAf-amdDueUBWp4sVTf5vM7Plmb2NxW9h3wxSbTZ-T6sH3rDW9LfbexZMBbM_OpZUQgsC2Pvex9QpNB0P82f34YxLS9ML2-_15_tXi9Qb3HIsoB6yXVM2_GaRGQ5eWko-AKUxS-_eXmGW-Lpa4uo0p4w_22n8o1dRt2VKby3XDhOk86IyQgxohZ4CVZ7pylvoT3T3idWVU3K3OeRgZk-_wPMojmvYgzxAwrENZ6GOSmtdFziIPOKwo6CzQVnI9J6e19DbZP8E5U7BvMFibPNiHLWRiZe6IwAIKL53w"
declare -x ACTIONS_ID_TOKEN_REQUEST_URL="https://run-actions-3-azure-eastus.actions.githubusercontent.com/213//idtoken/de4df071-befa-482c-b43c-b8bc6fc5a4b3/d70b8dac-329a-53a5-bd0f-3f1866aee5cd?api-version=2.0"
declare -x ACTIONS_ORCHESTRATION_ID="de4df071-befa-482c-b43c-b8bc6fc5a4b3.MakeNewReleaseBranch.__default"
declare -x ACTIONS_RUNNER_ACTION_ARCHIVE_CACHE="/opt/actionarchivecache"
declare -x ACTIONS_RUNNER_RETURN_JOB_RESULT_FOR_HOSTED="1"
declare -x AGENT_TOOLSDIRECTORY="/opt/hostedtoolcache"
declare -x ANDROID_HOME="/usr/local/lib/android/sdk"
declare -x ANDROID_NDK="/usr/local/lib/android/sdk/ndk/27.3.13750724"
declare -x ANDROID_NDK_HOME="/usr/local/lib/android/sdk/ndk/27.3.13750724"
declare -x ANDROID_NDK_LATEST_HOME="/usr/local/lib/android/sdk/ndk/29.0.14206865"
declare -x ANDROID_NDK_ROOT="/usr/local/lib/android/sdk/ndk/27.3.13750724"
declare -x ANDROID_SDK_ROOT="/usr/local/lib/android/sdk"
declare -x ANT_HOME="/usr/share/ant"
declare -x AWS_ACCESS_KEY_ID="ASIA3LET5VD6RMXUBWYS"
declare -x AWS_DEFAULT_REGION="us-east-1"
declare -x AWS_REGION="us-east-1"
declare -x AWS_SECRET_ACCESS_KEY="xK4BmRqLBDmtOD1JnF5CI3XeRO0N4bnmqWJbhBSq"
declare -x AWS_SESSION_TOKEN="IQoJb3JpZ2luX2VjECUaCXVzLWVhc3QtMSJIMEYCIQDGc46bgvhZYFO2P9w2PeZactS0+g6pX4YVSOZGZfeBJgIhAItB6XTlNt0IDbSK+5z8Bi05EvSKkezi217tZ9kaKx4yKvADCO7//////////wEQABoMNzc5ODQ2Nzg5MzczIgw/FBHlGFAASgksATkqxAPNTV9vi3va2fM1owbhlwBEM3E55O6yiGKL8z0iV3SdmO66i9NsCeMrsEB/N5Bf61XqAOY3CAWx1y7LWt/gCQrSUjv/e6uE+fdWridmAPEUgY2SS1tgRr0MRoiGwgLnK9WyC6EaPbO2+FMkIBQkJpk0woaOTM1uCW2mpNHiUkInloegrOAz4iMny3vkGkMdvjS5+w58hzXaJmQxe8MhAwXyLj4ec6KstiMuVZRZuguYOjgelD4zFEDYzPm3FueQ6IM553t8tlYBzvA/ELauUvFnFr+eG4TtXHr4bjPRTpIDMXwoHb1tw+5Zr02ghn/3TdXvTdButD00Pr0Kel9Q2pgHUg4Q0TyYCGZMLjVuypdAxdPhcjkTMNluTkfCn/UGWixfYfgmOUhb9s6YNnrNjrTlWsABZ52tJcx74NKY331zx4FOXbUrmGgiNoYRFIR23umPK4Ula9wFwRalg9rUfjuUxArch1oseCmoi/lhRcXLUDFEGswtjiLFGdA1VXirz9hsK9vo96d4EgGxXDhskl3rpoyqxQOdjKnLRXY5f9QUO7e4n3gxobbbqso+22w8qx290pyRnuGZYQghgUwtjhA5al6h3TDNj6fRBjqRAYaVAEWfkrjdPMTNpoB4ts2WCb6GifdhpmiqRKxPrBAHyPPDn+a6tlAGf4nRs11wSYWsgy/M9QKCY2sWe4UiZmrQX59hj8FjNsOlb1TtzroktMMa3qfXlKtg5/Fc4hAI2ictxRHJHTepH0ni3vMUeK/2tqIvDYKIJvMB6zgkOHLN/X4HfCWnGfzhMS8LnITAKGM="
declare -x AZURE_EXTENSION_DIR="/opt/az/azcliextensions"
declare -x BOOTSTRAP_HASKELL_NONINTERACTIVE="1"
declare -x CHROMEWEBDRIVER="/usr/local/share/chromedriver-linux64"
declare -x CHROME_BIN="/usr/bin/google-chrome"
declare -x CI="true"
declare -x CONDA="/usr/share/miniconda"
declare -x DEBIAN_FRONTEND="noninteractive"
declare -x DOTNET_MULTILEVEL_LOOKUP="0"
declare -x DOTNET_NOLOGO="1"
declare -x DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1"
declare -x EDGEWEBDRIVER="/usr/local/share/edge_driver"
declare -x ENABLE_RUNNER_TRACING="true"
declare -x GECKOWEBDRIVER="/usr/local/share/gecko_driver"
declare -x GHCUP_INSTALL_BASE_PREFIX="/usr/local"
declare -x GITHUB_ACTION="__run_2"
declare -x GITHUB_ACTIONS="true"
declare -x GITHUB_ACTION_REF=""
declare -x GITHUB_ACTION_REPOSITORY=""
declare -x GITHUB_ACTOR="estohlmann"
declare -x GITHUB_ACTOR_ID="14100972"
declare -x GITHUB_API_URL="https://api.github.com"
declare -x GITHUB_BASE_REF=""
declare -x GITHUB_ENV="/home/runner/work/_temp/_runner_file_commands/set_env_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_EVENT_NAME="workflow_dispatch"
declare -x GITHUB_EVENT_PATH="/home/runner/work/_temp/_github_workflow/event.json"
declare -x GITHUB_GRAPHQL_URL="https://api.github.com/graphql"
declare -x GITHUB_HEAD_REF=""
declare -x GITHUB_JOB="MakeNewReleaseBranch"
declare -x GITHUB_OUTPUT="/home/runner/work/_temp/_runner_file_commands/set_output_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_PATH="/home/runner/work/_temp/_runner_file_commands/add_path_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_REF="refs/heads/develop"
declare -x GITHUB_REF_NAME="develop"
declare -x GITHUB_REF_PROTECTED="true"
declare -x GITHUB_REF_TYPE="branch"
declare -x GITHUB_REPOSITORY="awslabs/LISA"
declare -x GITHUB_REPOSITORY_ID="800657426"
declare -x GITHUB_REPOSITORY_OWNER="awslabs"
declare -x GITHUB_REPOSITORY_OWNER_ID="3299148"
declare -x GITHUB_RETENTION_DAYS="90"
declare -x GITHUB_RUN_ATTEMPT="2"
declare -x GITHUB_RUN_ID="27303811673"
declare -x GITHUB_RUN_NUMBER="65"
declare -x GITHUB_SERVER_URL="https://github.com"
declare -x GITHUB_SHA="d3ec828266cfff7fbd894cee6d9914b53d0dbbcc"
declare -x GITHUB_STATE="/home/runner/work/_temp/_runner_file_commands/save_state_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_STEP_SUMMARY="/home/runner/work/_temp/_runner_file_commands/step_summary_8e4d49b9-2d66-4477-bb5e-8cfe9c66bdca"
declare -x GITHUB_TRIGGERING_ACTOR="estohlmann"
declare -x GITHUB_WORKFLOW="Make Release Branch"
declare -x GITHUB_WORKFLOW_REF="awslabs/LISA/.github/workflows/code.release.branch.yml@refs/heads/develop"
declare -x GITHUB_WORKFLOW_SHA="d3ec828266cfff7fbd894cee6d9914b53d0dbbcc"
declare -x GITHUB_WORKSPACE="/home/runner/work/LISA/LISA"
declare -x GOROOT_1_22_X64="/opt/hostedtoolcache/go/1.22.12/x64"
declare -x GOROOT_1_23_X64="/opt/hostedtoolcache/go/1.23.12/x64"
declare -x GOROOT_1_24_X64="/opt/hostedtoolcache/go/1.24.13/x64"
declare -x GOROOT_1_25_X64="/opt/hostedtoolcache/go/1.25.10/x64"
declare -x GRADLE_HOME="/usr/share/gradle-9.5.1"
declare -x HOME="/home/runner"
declare -x HOMEBREW_CLEANUP_PERIODIC_FULL_DAYS="3650"
declare -x HOMEBREW_NO_AUTO_UPDATE="1"
declare -x INVOCATION_ID="a62f0c9147f3428ea44c407352e6435a"
declare -x ImageOS="ubuntu24"
declare -x ImageVersion="20260525.161.1"
declare -x JAVA_HOME="/usr/lib/jvm/temurin-17-jdk-amd64"
declare -x JAVA_HOME_11_X64="/usr/lib/jvm/temurin-11-jdk-amd64"
declare -x JAVA_HOME_17_X64="/usr/lib/jvm/temurin-17-jdk-amd64"
declare -x JAVA_HOME_21_X64="/usr/lib/jvm/temurin-21-jdk-amd64"
declare -x JAVA_HOME_25_X64="/usr/lib/jvm/temurin-25-jdk-amd64"
declare -x JAVA_HOME_8_X64="/usr/lib/jvm/temurin-8-jdk-amd64"
declare -x JOURNAL_STREAM="9:13712"
declare -x LANG="C.UTF-8"
declare -x LOGNAME="runner"
declare -x MEMORY_PRESSURE_WATCH="/sys/fs/cgroup/system.slice/hosted-compute-agent.service/memory.pressure"
declare -x MEMORY_PRESSURE_WRITE="c29tZSAyMDAwMDAgMjAwMDAwMAA="
declare -x NVM_DIR="/home/runner/.nvm"
declare -x OLDPWD
declare -x PATH="/snap/bin:/home/runner/.local/bin:/opt/pipx_bin:/home/runner/.cargo/bin:/home/runner/.config/composer/vendor/bin:/usr/local/.ghcup/bin:/home/runner/.dotnet/tools:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin"
declare -x PIPX_BIN_DIR="/opt/pipx_bin"
declare -x PIPX_HOME="/opt/pipx"
declare -x POWERSHELL_DISTRIBUTION_CHANNEL="GitHub-Actions-Linux"
declare -x PSModulePath="/root/.local/share/powershell/Modules:/usr/local/share/powershell/Modules:/opt/microsoft/powershell/7/Modules:/usr/share/az_14.6.0"
declare -x PWD="/home/runner/work/LISA/LISA"
declare -x RUNNER_ARCH="X64"
declare -x RUNNER_ENVIRONMENT="github-hosted"
declare -x RUNNER_NAME="GitHub Actions 1020617025"
declare -x RUNNER_OS="Linux"
declare -x RUNNER_TEMP="/home/runner/work/_temp"
declare -x RUNNER_TOOL_CACHE="/opt/hostedtoolcache"
declare -x RUNNER_TRACKING_ID="github_d1c4cd78-6dc5-4007-8936-0e352760b785"
declare -x RUNNER_WORKSPACE="/home/runner/work/LISA"
declare -x SELENIUM_JAR_PATH="/usr/share/java/selenium-server.jar"
declare -x SGX_AESM_ADDR="1"
declare -x SHELL="/bin/bash"
declare -x SHLVL="1"
declare -x SWIFT_PATH="/usr/share/swift/usr/bin"
declare -x SYSTEMD_EXEC_PID="2092"
declare -x USER="runner"
declare -x USE_BAZEL_FALLBACK_VERSION="silent:"
declare -x VCPKG_INSTALLATION_ROOT="/usr/local/share/vcpkg"
declare -x XDG_CONFIG_HOME="/home/runner/.config"
declare -x XDG_RUNTIME_DIR="/run/user/1001" block format
- **Tooling**: Updated automated PR description generation script

## Acknowledgements
* @121983012+jmharold
* @32586639+gingerknight
* @bedanley
* @drduhe
* @estohlmann
* @evmann

**Full Changelog**: https://github.com/awslabs/LISA/compare/v6.6.0..v6.7.0

# v6.6.0

## Key Features

### Token Usage and Context Window Visibility

LISA now provides improved observability for model usage and configuration:

- View cumulative token usage for each user session.
- Display a context window field in model cards across Model Management and Model Library.
- Support overriding inferred context windows for LISA-hosted models through environment configuration.

### Bedrock Agent Integration

LISA now includes native Bedrock Agent integration, giving administrators a streamlined way to publish Bedrock Agents in the platform catalog and make them available to end users.

Users can opt in to these agents directly from the Agent Management UI, which makes it easier to adopt Bedrock-powered workflows without separate integration steps.

### LISA Serve Throttling

LISA Serve now includes throttling controls to better protect service stability under bursty or high-volume traffic patterns.

These controls help prevent noisy-neighbor behavior, improve predictability during traffic spikes, and provide a stronger baseline for multi-tenant reliability.

### Security Hardening

CORS origins are now configurable via a new `corsAllowedOrigins` allowlist that is threaded through all API Gateways, Lambdas, FastAPI services, and MCP server components via a new CDK aspect, replacing permissive defaults. Additionally, client-side OAuth callback validation, safe error rendering in the UI, and stricter Pydantic request parsing for MCP Server and Workbench Lambdas reduce injection and untrusted-input risks.

## Other Key Changes

- Dependency and security maintenance updates across Python and npm packages.
- Minor reliability fixes discovered during routine update work.
- Small MCP Workbench lifecycle improvements for tool synchronization and routing.
- Cypress CI workflow fixes for branch reporting and manual nightly test support.
- Incremental SDK improvements, including RAG evaluation support.


## Acknowledgements
* @bedanley
* @drduhe
* @estohlmann
* @gingerknight
* @jmharold

**Full Changelog**: https://github.com/awslabs/LISA/compare/v6.5.0..v6.6.0

# v6.5.0

## Key Features

### Self-Service RAG Administration

A new RAG Admin role gives designated users full control over RAG repository operations, document ingestion, collection management, and pipeline configuration without granting full system administrator privileges. This reduces the operational bottleneck where every RAG change required a system administrator. Self-service RAG is especially useful in multi-tenant environments.

### Operations Metrics Dashboard

New dashboard reports track metrics across models and clusters, including inference latency, token usage, and batch ingestion job status. For example, customers can use the new input/output token reports to derive costs across users, groups, and models. This is useful for multi-tenant environments with a variety of end-user orgs. Also, model containers publish Prometheus metrics for vLLM, TEI, and TGI, and batch ingestion jobs report totals and failures for RAG document ingestion.

### Integrating Externally Deployed Models

Administrators can register deployed models that are not LISA-managed by providing a URL that can be accessed from the LiteLLM ECS cluster. These models appear and behave like other models in the platform.

### AWS Session Credentials

LISA now lets you attach AWS credentials to a chat session. While that session is active, MCP tools can use those credentials to call AWS APIs, so tool-based workflows can reach AWS resources in the same context as the conversation instead of requiring separate per-tool setup.

An example of a tool using this can be seen: lib/serve/mcp-workbench/src/examples/sample_tools/aws_operator_tools.py

## Other Key Changes

- Updated OpenSearch for new RAG collections to the latest supported version and indexing engine (existing collections continue to work as before)
- Introduced optional audit logging for input/output from requests to LISA with opt-in and filtering
- Implemented a deployment Lambda to ensure configured models are present in LiteLLM
- Split Cypress E2E workflows into nightly health checks and weekly full suite runs, with API-based resource cleanup between runs
- Updated LiteLLM to version 1.82.4

## Acknowledgements
* @bedanley
* @drduhe
* @Ernest-Gray
* @estohlmann
* @gingerknight
* @jmharold

**Full Changelog**: https://github.com/awslabs/LISA/compare/v6.4.0..v6.5.0

# v6.4.0

## Key Features

### Project Organization for Chat Sessions

Customers can organize chat sessions into Projects, providing a structured way to manage and navigate conversation history. Projects allow users to group related sessions together, making it easier to find and revisit past conversations across different topics.

### Chat Assistant Stacks

Chat Assistant Stacks allow administrators to define preconfigured assistants that bundle models, RAG repositories and collections, MCP servers and tools, and prompt templates into a single package. Users can browse available assistants and start chat sessions with everything preconfigured, eliminating the need for manual setup. Access to each stack is controlled through enterprise user groups, allowing administrators to tailor assistant availability to specific teams or roles.

### Other Features

- Added context window inference step to model creation state machine for LISA-hosted and third-party models
- Added announcements banner feature to Configuration UI for administrators to set global messages for all users
- Added support for editing pipelines after repository creation
- Added secret rotation support for PGVector database credentials

## UI Updates

- Stopped models now appear in model dropdown but are properly disabled to indicate unavailability
- Prompt area buttons are now properly disabled when prompt is disabled (e.g., when model is stopped)

## Other Key Changes

- Batch ingestion job definition now uses static resource ID to prevent failures from definition drift during deployments
- REST containers now scale based on ECS metrics instead of ASG metrics for more reliable scaling
- Added support for additional text-based file types for RAG uploads including:
  - Javascript
  - HTML
  - Markdown
  - JSON
  - CSS
  - XML

## Bug Fixes

- Fixed a liteLLM configuration issue that double prefixed openAI models, this resolves an issue with LISA hosted models integrating with Claude Code
- Fixed pipeline event handling issues
- Fixed RAG collection ID resolution

## Documentation

- Added new API Reference documentation section to make it easier for developers to know where the various entity API documentation exists within our doc site.
- Added suggestions on self-hosted model performance scaling settings.

## Dependency Updates

- Updated `actions/setup-node` and `actions/upload-artifact` GitHub Actions to latest versions
- Upgraded various dependencies across the platform for security and compatibility

## Acknowledgements
* @bedanley
* @Ernest-Gray
* @estohlmann
* @gingerknight
* @jmharold

**Full Changelog**: https://github.com/awslabs/LISA/compare/v6.3.0..v6.4.0


# v6.3.0

## UI Updates
- Added RAG citation document preview side panel in Chat UI
- Exposed the document preview panel in the document library for viewing documents
- Added "Dismiss all" button for notification stacks
- Fixed "Loading Configuration..." text styling to match LISA UI using Cloudscape components
- Added last updated date/time to session displays

## Other Key Changes
- Updated VLLM image to latest AWS deep-learning base with GPU settings for ECS, memory reservation, and tensor parallelization from GPU count
- Dockerfiles for embedding (instructor, tei), text generation (tgi), and VLLM now run OS package upgrades during build
- Removed deprecated LISA Serve V1 endpoints and supporting infrastructure
- Updated dependencies across the codebase

## Bug Fixes
- Fixed RAG pipeline collection ID resolution (find_by_id_or_name fallback) and EventBus update mismatches on deployment
- Resolved max_tokens handling for non-Anthropic models on Anthropic routes
- Improved RAG PDF parsing quality (excessive whitespace and invisible Unicode characters)
- Addressed consistency of UI validation warnings for field format and required fields
- Added missing required role for batch ingestion
- Added cache clearing at login to prevent cache corruption issues

## Documentation
- Added Claude Code setup guide for LISA Serve integration
- Updated deployment guide

## Acknowledgements
* @bedanley
* @Ernest-Gray
* @estohlmann
* @gingerknight
* @jmharold

**Full Changelog**: https://github.com/awslabs/LISA/compare/v6.2.1..v6.3.0

# v6.2.1

## Bug Fixes
- Removed FastAPI import from auth handler preventing lambdas without FastAPI in the layer dependencies from working
- Updated Session model to account for session configuration data types to allow resuming old stored sessions
- Made exception handling more uniform and consistent across the application

## UI Updates
- Cleaned up the MCP approval modal
- Removed borders around all tables for a consistent theme across the UI
- Added markdown preview toggle to prompt input
- Moved delete all sessions button under user profile and added back the refresh button to session panel

## Documentation Updates
- Cleared up the vLLM variables LISA supports
- Updated deployment guide to account for new cognito updates

## Acknowledgements
* @bedanley
* @Ernest-Gray
* @estohlmann
* @jmharold

**Full Changelog**: https://github.com/awslabs/LISA/compare/v6.2.0..v6.2.1

# v6.2.0

## Key Features

### Custom Branding
LISA supports custom branding capabilities, allowing customers to tailor the user interface with specific logos and color schemes. The feature provides three key customization areas:

1. **Visual Assets** - Replace logos (favicon, top navigation logo, login image) in `lib/user-interface/react/public/branding/custom/`
2. **Display Name** - Change "LISA" brand name to your organization's product name via `customDisplayName` in `config-custom.yaml`
3. **Theme Customization** - Modify colors, fonts, and visual styling through the [Cloudscape theming system](https://cloudscape.design/foundation/visual-foundation/theming/)

### Video Generation Models
LISA supports video generation.

- Adding new VideoGen model type that admins can create in the model management
- Proxying routes to LiteLLM for video generation
- Saving generated videos in S3 and allowing users to download and share video links
- Exporting all videos from a selected session as a zip

### Interactive Configuration Generator CLI
LISA offers an interactive CLI tool that guides customers through creating a valid `config-custom.yaml` file for deployment. Instead of manually editing YAML and referencing `example_config.yaml`, customers can now run:

> awslabs-lisa@6.2.0 generate-config
> tsx scripts/generate-config.ts

╔════════════════════════════════════════════════════════════════╗
║           LISA Configuration Generator                         ║
║   Generate a config-custom.yaml for LISA deployment            ║
╚════════════════════════════════════════════════════════════════╝

The generator prompts for and validates:
- Core Configuration: AWS account, region, partition, deployment stage/name, S3 bucket
- Partition Support: additional partition configurations

### Reasoning Model Support
Admins can mark models as "reasoning-capable," which enables those models to output reasoning content alongside their responses. Customers can then configure the level of reasoning effort to be included, and the reasoning content is displayed in LISA Chat and exported with the session data.

## Other Key Changes
- **Image Editing Support**: Users can now upload reference images during image generation, allowing the model to create precise edits and updates based on the provided visual reference
- **Security**: Enabled encryption at rest for all S3 buckets, enforced SSL/TLS traffic only to S3, and encrypted all EBS volumes
- **Deployment**: Updated container source to use AWS ECR, upgraded host EC2 image to use AL2023
- **Usability**: Added loading/refresh icons across pages to better inform users when a refresh is taking place
- **Database**: Enabled IAM-based authentication for RDS connections, removed the need for storing master passwords
- **Accessibility**: Added a retry button next to failed user prompts, made the delete session dropdown button only appear if the config allows it
- **Bugfixes**: Addressed several IAM permission issues, CDK warnings, and model deployment healthiness checks
- **UI Quality of Life**: Continued to make subtle UI improvements by:
  - Adding various highlighting and background updates throughout the UI to make sections and errors stand out and more obvious
  - Adding loading indicators to various MCP toggles / checkboxes to display that calls are happening in the background
  - Updated various iconography, logos, and buttons to have a more uniform and clean feel

## Acknowledgements
* @bedanley
* @Ernest-Gray
* @estohlmann
* @jmharold

**Full Changelog**: https://github.com/awslabs/LISA/compare/v6.1.1..v6.2.0

# v6.1.1

##  UI Cleanup
### [Light/Dark Theme Fixes]
Some UI elements in light mode were being rendered in a dark theme, such as code blocks, Mermaid tables, message metadata, etc. This change ensures elements render in their appropriate theme based on the user's selection.

### [Auto-Scrolling Fix]
Allows users to break out of auto-scrolling during streamed responses by scrolling away from the bottom of the screen. Users can reset auto-scrolling by scrolling back down to the bottom of the stream.

### [API Token Dashboard Metrics]
This change ensures that users who programmatically interact with LISA are captured in the metrics dashboard. Additionally, it introduces a reorganization of the metrics dashboard to enhance readability.

### [Cypress Smoke Test Refactor]
Significantly enhanced the smoke tests to be more reliable. Added new E2E tests that reuse the smoke tests and a new model creation workflow E2E test.

### [Session History Reload Fix]
Fixed session history not loading when selected, and updated session hooks to correctly invalidate and retrieve the session after selecting a new session.

### [Markdown Table Support]
Introduced GitHub Flavored Markdown (GFM) to support markdown tables. Added Tailwind CSS overrides to render markdown in chat prompts. Enhanced the system prompt to render math expressions without additional prompting.


## Key Changes
- **Documentation**: Added access control details to the Getting Started section along with general updates, added instructions on how to accept the self-signed certificate in the browser, and updates to configuration labels.
- **Cypress Tests**: Added additional smoke tests to ensure admin pages load with data, chat prompts render responses, chat sessions are selectable and load properly, and non-admins can't navigate to admin pages.
- **Administrative**: Added an `AdminRoute` wrapper around the `McpWorkbench` component.

## Acknowledgements
* @bedanley
* @estohlmann
* @jmharold

**Full Changelog**: https://github.com/awslabs/LISA/compare/v6.1.0..v6.1.1

# v6.1.0

## ⚠️ Important: Major Dependency Updates

**This release includes comprehensive dependency updates across the entire platform.** While these updates are not breaking changes, they represent significant infrastructure improvements that enhance security and platform stability:

- **Lambda Runtime Upgrades**: All Lambda functions now use Node.js v24 and Python v3.13 (upgraded from EOL versions)
- **Security Vulnerability Remediation**: Updated all Python and npm dependencies to address outstanding CVEs
- **Platform Modernization**: Comprehensive updates to core libraries including React, AWS CDK, LangChain, Boto3, LiteLLM, and more

**Recommendation**: Test thoroughly in non-production environments before deploying to production systems.

## Key Features

### API Token Management

To further support multi-tenant environments, LISA Admins can now manage and associate API tokens with specific users or systems. This feature adds an API Management UI where Admins can create, view, and delete API tokens. This feature can be extended to non-admin users by configuring user groups and enabling it in the UI as a configuration option.

**User Experience:**
- **Admin UI**: Admins can view, create, and delete API tokens for users and system users
- **User UI**: Users can create and delete their own API tokens if enabled by the admin

### Schedule Management

This feature delivers automatic resource scheduling with LISA self-hosted models through AWS Auto Scaling Groups and Schedule Actions, enabling automated start/stop scheduling that reduces operational costs while maintaining service availability during business hours. The solution supports both UI-driven and API-driven workflows, eliminating manual intervention overhead and providing intelligent resource management.
**Scheduling Types:**
- **DAILY**: Configure different start/stop times for each day of the week
- **RECURRING**: Configure a single start/stop time to be used throughout the week
- **NONE**: The model will run continuously with no scheduled downtime

### RAG UI Enhancements

This set of UI enhancements improves the overall user experience of the Repository, Analysis, and Guardrail (RAG) components:
- **Consolidated Components**: Standardized common features across the UI such as User Admin Groups inputs, Metadata/Tags forms, Chunking Strategies forms, time rendering elements, and solidified sentence casing for element labels
- **Expanded Tables**: Exposed more fields to the user in the Repository and Collection tables
- **Model In-Use Deletion Notification**: Better handles models that are currently in use by collections or pipelines when deleting models
- **Placeholder Descriptions**: Added placeholder descriptions to improve discoverability
- **Reorganized Forms**: Reorganized Collection and Repository fields into separate wizard forms

### Dependency Updates

This release includes several dependency updates to address security vulnerabilities and keep the project up to date:
- **Python and Node Lambda runtimes**: Upgraded Lambda runtimes to Node v24 and Python v3.13 to correct EOL versions
- **Python Dependencies**: Updated Python dependencies to the latest compatible versions, addressing outstanding CVEs: Boto3, LiteLLM, LangChain, Cryptography, etc.
- **npm Dependencies**: Updated npm dependencies to latest compatible versions, addressing outstanding CVEs: React, cdk-lib, LangChain, Tailwind, Vite, etc...

### Bug Fixes and Other Improvements

- **Consistent Date Handling**: Applied consistent UTC timezone handling for object creation and UI rendering
- **VPC/Cert/Guardrail Config Updates**: Ensured consistent VPC and Cert configurations across all Lambdas and updated the Guardrail table config
- **MCP API Deployment Fix**: Ensured MCP APIs are deployed even when the MCP Workbench is disabled
- **Document Tagging Improvements**: Improved the logic for applying tags from all levels (repository, collection, document, pipeline) during document ingestion

## Key Changes

- **Feature**: Added API Token Management UI for admins and users
- **Feature**: Implemented automated resource scheduling through AWS Auto Scaling Groups
- **Enhancement**: Improved the overall user experience of the RAG components
- **Dependency Update**: Updated various npm, GitHub Actions, and Python dependencies
- **Bug Fix**: Applied consistent date handling, VPC configurations, and fixed various other bugs

## Acknowledgements

* @batzela
* @bedanley
* @dustinps
* @jmharold
* @nishrs

**Full Changelog**: https://github.com/awslabs/LISA/compare/v6.0.1..v6.1.0

# v6.0.0
Happy Thanksgiving! We are proud to announce the launch of our next major version, 6.0.0! This launch aligns with AWS re:invent in Las Vegas from Dec 1-5th. LISA 6.0.0 includes major enhancements to LISA's RAG capabilities. It also includes a new standalone solution, LISA MCP.

We hope you enjoy this release as much as we enjoyed building it. Please reach out to our product team via the "Contact us" button in the readme. Our product roadmap is customer driven, and we want to hear your feedback, questions, and needs as we look to 2026.


## Breaking Changes
- **API Token Table Migration**: The API token table has been renamed and moved from the Serve stack to the API Base stack (`LisaServeTokenTable` → `LisaApiBaseTokenTable`).
**Export all existing API keys before upgrading** and recreate them in the new table after deployment. This affects admin keys, service accounts, and any programmatic API access.
- **Management Key Secret Migration**: The LISA management key secret has been moved to the API Base stack with a new name format: `${deploymentName}-management-key` (removed `lisa-` prefix). **Update any scripts or integrations that reference the secret by name.** The secret value will be auto-generated during deployment; export from AWS Secrets Manager before upgrading if you need to preserve the existing value. Code using the SSM parameter `${deploymentPrefix}/appManagementKeySecretName` will continue to work without changes.
- **Existing Bedrock Knowledge Base Repositories** must be redeployed to support the new collections infrastructure. This is a simple update operation that creates the necessary infrastructure for automatic data source collection creation. Use the repository update API or UI to redeploy existing Bedrock Knowledge Base repositories.

## Key Features
### LISA MCP
LISA MCP is a standalone infrastructure-as-code solution that allows administrators to deploy and host any Model Context Protocol (MCP) servers directly within LISA. This enterprise hosting platform provides turn-key infrastructure deployment, automatic scaling, and secure networking, allowing organizations to build and operate custom MCP tools without managing underlying infrastructure.
#### Enterprise Hosting Capabilities
- **Turn-key Deployment**: Deploy STDIO, HTTP, or SSE MCP servers through a single API call or intuitive UI workflow, eliminating the need for manual infrastructure configuration
- **Dynamic Container Management**: Bring your own pre-built container images or point to S3 artifacts that are automatically packaged into containers at deployment time
- **Automatic Scaling**: Configure auto-scaling policies with customizable min/max capacity, CPU, and memory settings to handle varying workloads efficiently
- **Secure VPC Networking**: All MCP servers run within your private VPC with Application and Network Load Balancers, ensuring traffic never leaves your secure network boundaries
- **API Gateway Integration**: Hosted MCP servers are automatically exposed through LISA's existing API Gateway, inheriting the same authentication, authorization, and security controls (API keys, IDP lockdown, JWT group enforcement) used across the platform
#### Administrative Control
- **MCP Management UI**: Complete lifecycle management through a dedicated admin interface where administrators create, update, start, stop, and delete hosted MCP servers
- **Group-Based Access Control**: Restrict server visibility and usage to specific identity provider groups or make them available organization-wide
- **Lifecycle Automation**: Step Functions orchestrate provisioning, health monitoring, failure handling, and connection publishing with full auditability through DynamoDB status records
- **Health Monitoring**: Built-in health checks at both the container and load balancer levels ensure reliable service availability
#### Integration & Extensibility
- **External Integration Support**: Hosted MCP servers can be accessed by external agents, copilots, RPA bots, or SaaS workloads using the same API Gateway endpoints and authentication mechanisms
- **mcp-proxy Support**: STDIO servers are automatically wrapped with `mcp-proxy` and exposed over HTTP, simplifying deployment of standard MCP server implementations
- **UI & API Parity**: Manage servers through either the MCP Management admin page or REST API endpoints (`/mcp`), providing flexibility for automation and programmatic workflows
### LISA RAG Collections
LISA's RAG capabilities just got a major upgrade! We've completely reimagined how you organize and manage RAG documents with the introduction of Collections. Collections transform how you structure your RAG content. Think of repositories as filing cabinets and collections as the organized drawers within—each with its own configuration.
#### Flexible Document Organization

- **Custom Chunking Strategies**: Configure different chunking approaches per collection (fixed-size or no chunking). If using a Bedrock Knowledge Base all service chunking strategies are supported
- **Flexible Embedding Models**: Each collection can use its own embedding model, optimizing retrieval for specific document types
- **Access Control**: Set collection-level permissions with group-based access control, making it easy to share some collections organization-wide while keeping others restricted within the same repository
- **Rich Metadata Support**: Tag documents with custom metadata at the repository, collection, or document level for powerful filtering and organization
#### Intelligent Document Lifecycle Management

- **Smart Deletion Workflows**: Delete collections asynchronously with optimized cleanup for each supported Repository
- **Document Preservation**: User-managed documents in Bedrock Knowledge Bases are automatically preserved during collection operations, ensuring you never lose important content
- **Enhanced UI Experience**: Browse, filter, and sort collections with visual status indicators, intuitive creation wizards, and document library integration with breadcrumb navigation
- **Admin-Controlled Operations**: Collection creation, updates, and deletion are restricted to administrators while regular users can continue to view and upload documents to collections they have permission to access
- **Backward Compatibility**: Existing repositories automatically get a virtual "Default" collection using the repository's embedding model with zero downtime and no database migrations required
#### Bedrock Knowledge Base Updates

- **Automatic Collection Creation**: Each Bedrock Knowledge Base Data Source gets its own collection with LISA's management capabilities
- **Custom Metadata & Tagging**: Add LISA's metadata to your Bedrock Knowledge Base documents for enhanced organization and filtering
### Other Enhancements
- Updated the prompt area to auto-expand from 2 rows to 20 rows when typing a large prompt.
- Updates for easier prisma client generation
- Enhanced logging in LISA Rest ECS cluster to include LiteLLM logs

## Acknowledgements
* @bedanley
* @dustins
* @estohlmann
* @jmharold

**Full Changelog**: https://github.com/awslabs/LISA/compare/v5.4.0..v6.0.0

# v5.4.0

## Key Features

### Bedrock Guardrails Integration
LISA Administrators can now Bedrock Guardrails to any models via the Model Management page or API
- **Comprehensive Protection**: Integrated with Bedrock Guardrails through LiteLLM's proxy support of the ApplyGuardrail API, enabling guardrails during prompt input, response generation, and prompt output.
- **Advanced Capabilities**: Supports topic denial, word filtering, sensitive information limitation, contextual grounding checks, and automated reasoning for factual accuracy.
- **Flexible Administration**: Administrators can apply Guardrails to any LISA model (self hosted or 3rd party) via the Model Management UI or API, with customizable permissions for different user groups.
- **Adaptive Policies**: Guardrails and group permissions can be updated anytime to evolve content moderation alongside organizational needs.

### Offline/Air-gapped Deployment Support
Enhanced the platform to support offline and air-gapped deployments by enabling pre-caching of external dependencies for the REST API and MCP Workbench.
- **Nodeenv Pre-caching**: Added support for pre-caching the required nodeenv in the REST API container to enable offline deployments.
- **Offline Deployment**: Enabled configuration of pre-cached external dependencies for the MCP Workbench via  to support offline and air-gapped deployments.

### MCP Workbench Refactoring
Migrated the MCP Workbench deployment to use the shared LisaServe ECS cluster, improving modularity and enabling conditional deployment.
- **MCP Workbench Stack**: Created a dedicated stack that deploys the MCP Workbench as a separate ECS service on the shared cluster.
- **Conditional Deployment**: Introduced a  configuration flag to control the optional deployment of the MCP Workbench.
- **Container Overrides**: Added support for overriding the MCP Workbench container image during deployment..

### MCP Workbench UX Improvements
Enhanced the user experience of the MCP Workbench with tool validation, error display, and theme support.
- **Validation**: Implemented tool validation to improve the user experience.
- **Theming**: Introduced theme support for the MCP Workbench UI.

## Acknowledgements
* @batzela
* @bedanley
* @dustins
* @estohlmann
* @jmharold

# v5.3.2

## Key Features

### Enabling OAuth Backed MCP Connections
- **MCP OAuth Support**: LISA now supports OAuth authentication for the MCP (Model Context Protocol) connection feature, enabling users to securely authenticate and access their connections
- **Connection Management**: Users can now reset their connections through the connection management interface allowing users to update previously configured settings stored in local storage

### Rag Ingestion JobStatus Update
- **DDB**: The GSI (Global Secondary Index) for the JobStatusTable has been updated to improve the querying and filtering capabilities of the job status information
- **Job Status Widget**: The RAG ingestion UI now features a new status tracking widget that displays your recent document ingestion job history, enabling monitoring of processing progress

### Chat Widget Performance Optimization
This release includes significant performance improvements to the chat widget, addressing performance degradation issues caused by excessive re-rendering
- **Memoization**: The chat widget has been optimized using memoization techniques, reducing the number of unnecessary re-renders and improving the overall responsiveness of the application
- **Conditional Dependencies**: The chat widget's dependency handling has been improved, ensuring that only the necessary components are re-rendered based on changes in the data

### Langfuse Documentation
This release includes updates to our [documentation site](https://awslabs.github.io/LISA/config/langfuse-tracing.html) where a guide was created on how to integrate Langfuse into LISA Serve to view your LLM traces

## Acknowledgements
* @bedanley
* @dustins
* @estohlmann
* @jmharold

**Full Changelog**: https://github.com/awslabs/LISA/compare/v5.3.1..v5.3.2

# v5.3.1

## Key Features

### Session Encryption

LISA now supports optional session encryption. Administrators can activate encryption which applies to all sessions. When activated, chat sessions are encrypted prior to storage in DynamoDB and automatically decrypted when retrieving data, enhancing data security at rest.

### Embedding Client Consolidation

- **Unified Configuration**: Consolidated embedding clients so both embedding and retrieval use the same configuration logic
- **LiteLLM Integration**: Removed OpenAIEmbedding in favor of LiteLLM provided embedding through RagEmbedding
- **Authentication Streamlining**: Merged LisaServe Auth to follow same flow for LiteLLM requests and passthrough

### Security Improvements and Vulnerability Remediation

This release includes security related updates across the codebase.
**Security Enhancements:**

- **Dependency Security**: Updated vulnerable dependencies across Python and Node.js packages with Dependabot configuration for automated security updates
- **Container Security**: Updated Dockerfiles with security-focused base images and improved container build processes
- **Infrastructure Security**: Added CodeQL security scanning workflow and enhanced CI/CD pipeline with security checks
- **API Security**: Improved API key handling and cleanup mechanisms with enhanced LiteLLM integration

### Bug Fixes

- **Model ID Normalization**: Force model-id to use lowercase per OpenSearch requirements
- **Text Encoding**: Encode text files using UTF-8 to remove special character double encoding
- **Documentation Cleanup**: Update cleanup docs function to correct signature
- **Model Refresh**: Fix refresh of models functionality
- **UI Optimization**: Remove duplicate similar_search queries from UI
- **Threading Fix**: Fix threading of async auth calls in RestAPI

### Additional Features

- **Expanded SDK**: Enhanced SDK functionality with integration script for setting up models and vector stores
- **Request Caching**: Cache repeated requests for configs and keys

## Breaking Changes

- **Bedrock Model Configuration**: Legacy Bedrock models not prefixed with `bedrock/` will need to be recreated. The updated LiteLLM version requires removal of placeholder API keys from Bedrock models, which are identified using the 'bedrock/' prefix.

## Acknowledgements

- @bedanley
- @estohlmann
- @jmharold
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v5.3.0...v5.3.1>

# v5.3.0

## Key Features

### Model Context Protocol (MCP) Workbench

LISA now includes a comprehensive MCP Workbench that enables administrators to create, test, manage and host custom MCP tools directly within LISA.

#### MCP Tool Development

- **Custom Tool Creation**: Administrators can create and edit custom MCP tools using a built-in code editor with syntax highlighting
- **Tool Testing Environment**: Integrated testing capabilities for validating MCP tools before enterprise rollout
- **Template-Based Development**: Pre-built tempslate and examples to accelerate tool development
- **MCP file hosting support**: Administrators can upload MCP tool code directly to S3. The MCP Workbench connection will automatically host this tool for use
- **Improved Authentication**: Enhanced authentication mechanisms for MCP server connections, if users specify `{LISA_BEARER_TOKEN}` in the header field, LISA will populate this with the users active token. This is important for proxying calls to internally hosted servers that use the same authentication mechanisms as LISA

#### Administrative Control

- **Tool Management**: Administrators can manage and configure the MCP workbench capabilities for their organization
- **IDP Group Locking**: MCP connections can now be locked down to specific Identity Provider (IdP) groups for enhanced security

### Enhanced Model Control

- **Custom API Key Support**: Support for handling custom API keys for third-party models added to Model Management

### Mermaid Diagram Sanitization

- **Security Enhancement**: Implemented sanitization for Mermaid diagrams to prevent potential security vulnerabilities
- **Safe Rendering**: Ensures that Mermaid diagrams are rendered safely without executing malicious code

## What's Next?

We'll be launching broader MCP tool hosting capabilities in an upcoming LISA release.

## Acknowledgements

- @bedanley
- @estohlmann
- @jmharold
- @dustins
- @jonleeh
- @drduhe

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v5.2.0...v5.3.0>

# v5.2.0

## Key Features

### Model Context Protocol (MCP)  Enhancements

- **Connection Validation**: Real-time connection testing with detailed feedback on server connectivity during connection creation/edit
- **Enhanced Debugging**: Improved error handling and connection status reporting for MCP servers

### Session Management Improvements

- **Time-Based Session Grouping**: Sessions are now automatically organized into time-based groups based on updated date (Last Day, Last 7 Days, Last Month, Last 3 Months, Older)
- **Session ID Removal**: Removed session ID from prompt input for cleaner user interface

### RAG (Retrieval-Augmented Generation) Improvements

#### Document Processing

- **Document Chunk Processing Fixes**: Resolved issues with document chunk processing and ingestion
- **Document Library Pagination**: Added pagination support for the Document Library to handle large numbers of documents efficiently

#### Vector Store Configuration

- **Default Embedding Model Support**: Added ability to define a default embedding model when creating or updating vector stores
- **IAM Permissions Optimization**: Trimmed vector store IAM permissions to follow the principle of least privilege
- **Container Configuration**: Added container override configuration for batch ingestion processes

#### Batch Ingestion

- **Container Configuration**: Added support for container override configuration in batch ingestion jobs
- **Max Batch Jobs Setting**: Implemented dynamic maximum batch jobs limit
- **Ingestion Rules Updates**: Automatic updates to ingestion rules when Lambda functions are updated

### Model Management Improvements

- **Base Container Configuration**: Added support for using prebuilt model containers, instead of building during model deployment

### UI/UX Enhancements

- **General UI Improvements**: Various user interface enhancements to improve usability
- **Updated Default System Prompt**: Updated LISAs default system prompt to take advantage of new rendering capabilities. Pairing this prompt with new UI components supports the display of:
  - Inline-Code
  - Mathematic equations using LaTex syntax
  - Mermaid Diagrams. These diagrams can also be copied and downloaded as images

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins
- @jmharold

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v5.1.0...v5.2.0>

# v5.1.0

## Key Features

### Model Management Enhancements

We updated LISA's Model Management wizard experience that supports creating and updating configured models.

#### Administrative Enhancements

- Renamed "Create Model" to "Configure Model" for clarity in the model setup process
- Improved the model management configuration wizard for more intuitive field organization and workflow:
  - Moved "LISA Hosted Model" toggle to the top of the wizard to drive workflow
  - Added a dedicated "Model Description" field to better document model purposes
  - Decluttered creation wizard for third-party models to only display relevant fields
- Enhanced post-creation model management:
  - Administrators can now view all configuration details for both self-hosted and third-party models post creation
  - Expanded editable fields post-creation for self-hosted and third-party models. This includes model features, streaming capabilities, access controls, and others. See LISA's Documentation for more details.

#### Access Control Improvements

- Added enterprise group-based access control for models, allowing administrators to:
  - Restrict model access to specific IdP groups
  - Configure models with open access when no groups are specified

#### New Model Library for All Users

- When activated, all users can view the "Model Library" page under the Library menu
- Users see the models that they have access to in the Model Library. Users have visibility into the features and capabilities that each model supports (e.g., imagegen, MCP, Streaming, Document summarization). This is useful in environments with many available models.

### Amazon Bedrock Knowledge Base Integration

LISA now supports Amazon Bedrock Knowledge Bases for enhanced RAG capabilities.

#### Administrative Features

- Bring Your Own Knowledge Base (BYOKB) support:
  - Administrators can connect pre-created Bedrock Knowledge Bases to LISA. This includes Amazon Neptune, which supports GraphRAG.
  - Simple configuration requiring only basic BRKB info
  - Integration available through both UI and API interfaces
- Granular access control:
  - Restrict Knowledge Base access to specific user groups
  - Manage permissions at the Knowledge Base level

#### Document Management

- Comprehensive document ingestion options:
  - Automated document ingestion pipeline support
  - Direct document uploads to Knowledge Bases via the LISA UI leveraging Bedrock's supported chunking strategies
- Full integration with LISA's Document Library:
  - View documents stored within Bedrock Knowledge Bases
  - Download documents for offline use

#### RAG Capabilities

- Seamless integration with LISA's RAG workflow:
  - Users can select Bedrock Knowledge Bases as vector stores for RAG prompting
  - Support for Bedrock's query options for optimized retrieval

### UI Improvements

We made several user experience enhancements to improve productivity and workflow:

#### Session Management

- **Session Title Filtering**: Quickly locate specific sessions with new filtering capabilities
- **Session Renaming**: Easily rename existing sessions through a new action menu item with a simple text input dialog
- **Persistent Name Changes**: Session name changes are now saved and maintained across sessions

#### Model Preferences

- **Global Default Model**: Administrators can set a preferred model as the global default from the Model Library view
- **Automatic Application**: Default model settings are automatically applied to all new sessions

#### Model Comparison Tool

- **Multi-Model Evaluation**: Select and compare responses from up to 4 models side-by-side. Administrators can activate or deactivate the feature in the Configuration page.
- **Configurable Prompts**: Apply custom prompt parameters for each comparison session
- **Ephemeral Results**: View comparison results without creating permanent sessions
- **Response Format**: Results displayed in a familiar chat-like interface for easy evaluation
- **Export Capability**: Download comparison results in JSON format for further analysis

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins
- @jmharold

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v5.0.0...v5.1.0>

# v5.0.0

## Model Context Protocol (MCP) Integration

LISA now supports Model Context Protocol (MCP), a popular open standard that enables developers to securely connect AI assistants with external tools and services! LISA customers can leverage MCP servers and tools directly within LISA's chat assistant user interface, or APIs.

### Administrative Features

- Control the availability of MCP support via LISA's Configuration page
- Create, edit, and delete MCP server connections
- Activate or deactivate specific MCP server connections
- Choose the MCP server connections for global use in order to support organization-wide availability
- Identify specific LLMs to support handling of tool calls

### User Experience Enhancements

- Create, edit, and delete personal MCP server connections
- Browse the intuitive user interface to view personal and global MCP server connections
- Activate specific MCP server connections for individual use
- Real-time visibility into the number of active MCP servers and tools for personal use in chat sessions
- Seamless integration with existing LLM chat interface to execute MCP tools

### Tool Management Functionality

- Users individually opt out of specific MCP server tools with simple toggle controls
- Users  are automatically enrolled in Safe Mode, which requires confirmation for tool execution. Users have the optional to auto-approve specific tool actions
- Users have the ability to manually stop tool execution at any time via Stop generation button

### Autopilot Mode

- Users can individually activate Autopilot Mode for streamlined tool execution without confirmation prompts
- User-specific setting applies across all active MCP server connections
- Reduces risk of tool timeouts waiting for user confirmation, but maintains users' visibility into actions being executed
- Beneficial for multi-step workflows involving multiple tools

## Usage Analytics Dashboard

Comprehensive visibility into LISA usage analytics via an Amazon CloudWatch dashboard. The LISA User Metrics Dashboard is automatically created during deployment and can be accessed through the AWS Management Console

## Administrative Insights

- 12 new metric widgets depict detailed usage to help measure platform adoption and impact
- Track unique user counts across multiple time periods and features (daily, weekly, monthly, quarterly, YTD)
- Monitor organization-level engagement through IDP group aggregation
- Visualize usage trends with interactive time-series graphs

### Detailed Usage Metrics

- Comprehensive prompt tracking showing total prompts by users and groups
- RAG utilization metrics showing vector store engagement patterns by users and groups
- MCP tool call metrics showing total tool usage over time by users and groups

## Updated Documentation

- Updated System Administrator Guides within LISA's documentation. This is accessible via the Document link in the GitHub repo, and also bundled with LISA
- Additional updates are coming soon for the Advanced Configuration and User Guides sections

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.4.4...v5.0.0>

# v4.4.4

## Bug Fixes

- Resolved an issue with docker base images
- Added logic to support ACM based certs and custom hosting

## Acknowledgements

- @bedanley
- @jmharold
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.4.3...v4.4.4>

# v4.4.3

## Security Enhancements

- Allowing IAM auth with LISA RDS Instances
- Fixing breaking 3rd party Dependency

## Acknowledgements

- @bedanley
- @jmharold
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.4.2...v4.4.3>

# v4.4.2

## System Improvements

- Updated configuration items to make ADC region deployments easier
- Updated markdown rendering to properly display code blocks and unordered lists

## Security Enhancements

- Enforce SSL access to EC2 docker bucket
- Enable Access Logging with New Log Destination Bucket
- Updated 3rd party dependencies

## Acknowledgements

- @bedanley
- @jmharold
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.4.1...v4.4.2>

# v4.4.1

## Bug Fixes

- Updated OpenSearch vector store creation to support private VPCs

## System Improvements

- LISA now supports P5 Instances!

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.4.0...v4.4.1>

# v4.4.0

## Key Features

### Image Generation

LISA now supports Image Generation capabilities!

#### Administrative Features

- Administrators can now configure and deploy models with the new IMAGEGEN classification type

#### User Experience Enhancements

- Users can customize image generation parameters including:
  - Output quantity: Specify the number of images to generate per prompt
  - Quality settings: Select between Standard and High Definition (HD) resolution
  - Aspect ratio options: Choose from Square, Portrait, or Landscape formats

#### Image Management Functionality

- Comprehensive image handling options:
  - Preview generated images directly in the interface
  - Download individual images to local storage
  - Copy images directly to clipboard for immediate use
  - Perform bulk downloads of all images from a session to a zip file
  - Regenerate variations using identical parameters

#### Persistent Storage Solution

- All generated images are automatically preserved in session-specific S3 storage
- Seamless retrieval of previously generated images when returning to a session

### Directive Prompt Templates

LISA’s prompt library now supports directive prompt templates

#### User Template Management

- Users can now create and implement specialized directive prompt templates, complementing the existing persona prompt template functionality
- Seamless import capabilities allow for integration of directive templates into both active and newly created sessions

#### Flexible Access Control Options

Extended the existing permission settings enable users to designate directive templates as:

- Private resources for individual use
- Global assets accessible organization-wide
- Restricted resources with access limited to specific IDP groups

#### Workflow Integration

- Directive templates enhance structured interactions and standardized workflows across the platform

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.3.0...v4.4.0>

# v4.3.0

## Key Features

### RAG Ingestion Backend Overhaul

- **Ingestion Job Tracking:** Introduced a new DynamoDB table for tracking ingestion jobs using UUIDs. This enables real-time status queries and establishes a foundation for future monitoring and analytics.
- **Execution Migration to AWS Batch:** RAG ingestion workflows now run on AWS Batch with Fargate, removing the 15-minute timeout limitation of Lambda and enabling the reliable execution of large or complex ingestion tasks. This change also unlocks support for event-driven monitoring and job orchestration.

### Benefits

- Improved scalability and reliability of ingestion processes.
- Lays the groundwork for future enhancements such as parallelized embeddings and multi-step ingestion workflows.

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.2.0...v4.3.0>

# v4.2.0

## Key Features

### RAG Updates

- LISA's RAG stack can now be deployed without also deploying LISA's UI. This expands LISA's modularity to better support our customers using custom UIs.
- RAG ingestion and similarity search functionalities now support user tokens in addition to bearer tokens.
  - *Note:* Administrators must deploy a Model and Vector Store via API using an Admin token before utilizing ingestion or search functionalities.
- Vector Store Ingestion Pipelines can now be configured with a `0` chunk size. This enables users to upload entire documents into a vector store as a single 'chunk.' This allows customers to set up custom parsing outside of LISA

## System Improvements

- Started building out our Python Unit Testing framework to enhance system reliability and performance.

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.1.1...v4.2.0>

# v4.1.1

## Bug Fixes

- Upgraded LiteLLM so that SagemakerEndpoint hosted models will be supported again

## User Interface Improvements

- Updated sessions UI to be more condensed and match the rest of the UI theme
- Save session configuration in DDB so when users re-opens session their settings persist

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.1.0..v4.1.1>

# v4.1.0

## Key Features

### Image Processing

- LISA now supports LLMs that offer image analysis/input! During the model creation process, Administrators designate if a model is compatible with image input.
- Users are now able to incorporate images into their session context for supported image files. They can ask the compatible LLM questions about their images.
- LISA's message interactions have been restructured from langchain to system-managed objects, enabling the support of advanced message types. This breaks down messages into unique multi-part elements instead of one large text based message that is sent to the model.

### Prompt Management

- Users can now create and modify personas for ongoing use across sessions. The visibility of these personas can be defined in the following ways:
  - Personal use
  - Specific Identity Provider (IDP) groups
  - Public access (visible to all LISA users)
- When a user initiates a session, they can import and update the personas they have access to.
- Administrators can enable this functionality through the system configuration page.

## User Interface Improvements

- When a request includes RAG documents, citations are now displayed inline in the ChatUI. They were previously only visible in metadata.
- A new landing page now has 'Quick Actions' that display if a user has yet to initiate a conversation.
- Users can now download their session history as a JSON file.
- The top menu options have been consolidated to minimize clutter.

## System Improvements

- Upgrading third-party dependencies to leverage the latest features from our dependencies.

## Upcoming Features

- We will be enhancing our Prompt Library to store user-defined prompt inputs in addition to persona definitions.

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.0.3...v4.1.0>

# v4.0.3

## Bug Fixes

- Resolved issue with subnets imports
- Resolved issue with custom model deployment

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.0.2..v4.0.3>

# v4.0.2

## Enhancements

- Revised base configuration to eliminate default RagRepository declaration. **Important:** Ensure config-custom.yaml contains an empty array declaration if no configurations are defined.
- Implemented multi-instance LISA deployment support within single AWS accounts. Customers may now deploy more than one LISA environment into a single account.
- Optimized data schema architecture to eliminate redundant reference patterns

## User Interface Improvements

- Enhanced proxy configuration to support HTTP status code propagation for improved error handling
- Introduced configurable markdown viewer toggle for non-standard model outputs
- Implemented redesigned administrative configuration interface
- Enhanced session management:
  - Removed UUID exposure from breadcrumb navigation
  - Transitioned to last-modified timestamp display from access time
  - Improved session loading indicators for enhanced user feedback
- Integrated document library refresh functionality
- Resolved critical Redux store corruption issue affecting state management overrides, reducing noticeable latency when fetching data in the UI

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.0.1..v4.0.2>

# v4.0.1

## Bug Fixes

### Vector Store Management

- Enhanced UI to display default repository name when not specified
- Improved UI to show "GLOBAL" when no groups are assigned
- Refined repository schema regex to ensure valid input fields
- Optimized admin routing for RAG repository access
- Updated RAG Configuration table to align with config destruction property
- Resolved issue preventing creation of OpenSearch vector stores

### User Interface

- Implemented consistent positioning of chat input at the bottom of the screen

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v4.0.0..v4.0.1>

# v4.0.0

Our 4.0 launch brings enhanced RAG repository management features to LISA’s chatbot user interface (UI). Our new RAG document library allows users to view and manage RAG repository files. Administrators are now able to manage and configure vector stores (also known as RAG repositories), and document ingestion pipelines directly in the Configuration page without having to redeploy LISA.

## **Enhancements**

### **RAG Repository Management**

- Admins can create, edit, delete RAG repositories via LISA’s Configuration UI. Admins can also manage access through the UI. LISA re-deployments are no longer required.
- Admins can create, edit, delete new document ingestion pipelines via LISA’s Configuration UI. LISA re-deployments are no longer required.
- We added a RAG deletion pipeline that automatically removes S3 documents when deleted from RAG repositories.
- We introduced new API endpoints for dynamic management of vector stores and ingestion pipelines.
- Customers who previously configured LISA with RAG repositories (v3.5 and before) will be able to view these legacy RAG repositories in the Configuration UI. However, they will not be able to make any changes through the UI. Admins must continue to manage RAG repositories through the config file. We recommend that when you are ready, you delete any legacy RAG repositories through the UI. Then you will need to redeploy CDK which will automatically tear down the legacy repository’s resources. Then you will be able to recreate RAG repositories through the UI and re-load documents.

### **Document Library**

- Added a RAG Document Library page in the chatbot UI. Users can download previously uploaded documents from the RAG repositories that they have access to.
- Users can also delete files from RAG repositories that they originally uploaded in the Document Library. Admins can delete any files through the Document Library. Files are also automatically removed from S3.

> **Note:** As of LISA 4.0, new RAG repositories and document ingestion pipelines can no longer be configured at deployment via YAML.

## **Security**

- Updated third-party dependencies.

## **Acknowledgements**

- [@bedanley](https://amzn-aws.slack.com/team/U03P7CBD673)
- @dustins
- @estohlmann
  [**Full Changelog**](https://github.com/awslabs/LISA/compare/v3.5.1...v4.0.0)

# v3.5.1

## Bug Fixes

### Chat Session Management

- Resolved url redirect issue that prevented creation of new chat sessions via the New button
- Resolved intermittent loading issues when accessing historical conversations due to LangChain memory object
- Addressed error handling for LLM interactions after multiple prompts

### Document Summarization

- Fixed stability issues with document summarization functionality in existing chat sessions

### UI

-Corrected display scaling issues in Firefox for large screen resolutions

# v3.5.0

## Key Features

### User Interface Modernization

- New year new me? We are rolling out an updated user interface (UI) in Q1. This release is the first stage of this effort.
- **Document Summarization**
  - Building on existing non-RAG in context capabilities, we added a more comprehensive Document Summarization feature. This includes a dedicated modal interface where users:
    - Upload text-based documents
    - Select from approved summarization models
    - Select and customize summarization prompts
    - Choose between integrating summaries into existing chat sessions or initiating new ones
  - System administrators retain full control through configuration settings in the Admin Configuration page

## Other UI Enhancements

- Refactored chatbot UI in advance of upcoming UI improvements and this launch
- Consolidated existing chatbot features to streamline the UI
- Added several components to improve user experience: copy button, response generation animation
- Markdown formatting updated in LLM responses

## Other System Enhancements

- Enhanced user data integration with RAG metadata infrastructure, enabling improved file management within vector stores
- Optimized RAG metadata schema to accommodate expanded documentation requirements
- Started updating sdk to be compliant with current APIs
- Implementation of updated corporate brand guidelines

## Coming soon

Our development roadmap includes several significant UI/UX enhancements:

- Streamlined vector store file administration and access control
- Integrated ingestion pipeline management
- Enhanced Model Management user interface

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v3.4.0...v3.5.0>

# v3.4.0

## Key Features

### Vector Store Support

- Implemented support for multiple vector stores of the same type. For example, you can now configure more than 1 OpenSearch vector store with LISA.
- Introduced granular access control for vector stores based on a list of provided IDP groups. If a list isn’t provided the vector store is available to all LISA users.
- Expanded APIs for vector store file management to now include file listing and removal capabilities.

### Deployment Flexibility

- Enabled custom IAM role overrides with documented minimum permissions available on our [documentation site](https://awslabs.github.io/LISA/config/role-overrides)
- Introduced partition and domain override functionality

## Other System Enhancements

- Enhanced create model validation to ensure data integrity
- Upgraded to Python 3.11 runtime for improved performance
- Updated various third-party dependencies to maintain security and functionality
- Updated the ChatUI:
  - Refined ChatUI for improved message display
  - Upgraded markdown parsing capabilities
  - Implemented a copy feature for AI-generated responses

## Coming soon

Happy Holidays! We have a lot in store for 2025. Our roadmap is customer driven. Please reach out to us via Github issues to talk more!  Early in the new year you’ll see chatbot UI and vector store enhancements.

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v3.3.2...v3.4.0>

# v3.3.2

## Bug Fixes

- Resolved issue where invalid schema import was causing create model api calls to fail
- Resolved issue where RAG citations weren't being populated in metadata for non-streaming requests
- Resolved issue where managing in-memory file context wouldn't display success notification and close the modal

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v3.3.1...v3.3.2>

# v3.3.1

## Bug Fixes

- Resolved issue where AWS partition was hardcoded in RAG Pipeline
- Added back in LiteLLM environment override support
- Updated Makefile Model and ECR Account Number parsing

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v3.3.0...v3.3.1>

# v3.3.0

## Key Features

### RAG ETL Pipeline

- This feature introduces a second RAG ingestion capability for LISA customers. Today, customers can manually upload documents via the chatbot user interface directly into a vector store. With this new ingestion pipeline, customers have a flexible, scalable solution for automating the loading of documents into configured vector stores.

## Enhancements

- Implemented a confirmation modal prior to closing the create model wizard, enhancing user control and preventing accidental data loss
- Added functionality allowing users to optionally override auto-generated security groups with custom security groups at deployment time

## Acknowledgements

- @bedanley
- @djhorne-amazon
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v3.2.1...v3.3.0>

# v3.2.1

## Bug Fixes

- Resolved issue where subnet wasn't being passed into ec2 instance creation
- Resolved role creation issue when deploying with custom subnets
- Updated docker image to grant permissions on copied in files

## Coming Soon

- Version 3.3.0 will include a new RAG ingestion pipeline. This will allow users to configure an S3 bucket and an ingestion trigger. When triggered, these documents will be pre-processed and loaded into the selected vector store.

## Acknowledgements

- @bedanley
- @estohlmann

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v3.2.0...v3.2.1>

# v3.2.0

## Key Features

### Enhanced Deployment Configuration

- LISA v3.2.0 introduces a significant update to the configuration file schema, optimizing the deployment process
- The previous single config.yaml file has been replaced with a more flexible two-file system: config-base.yaml and config-custom.yaml
- config-base.yaml now contains default properties, which can be selectively overridden using config-custom.yaml, allowing for greater customization while maintaining a standardized base configuration
- The number of required properties in the config-custom.yaml file has been reduced to 8 items, simplifying the configuration process
- This update enhances the overall flexibility and maintainability of LISA configurations, providing a more robust foundation for future developments and easier customization for end-users

#### Important Note

- The previous config.yaml file format is no longer compatible with this update
- To facilitate migration, we have developed a utility. Users can execute `npm run migrate-properties` to automatically convert their existing config.yaml file to the new config-custom.yaml format

### Admin UI Configuration Page

- Administrative Control of Chat Components:
  - Administrators now have granular control over the activation and deactivation of chat components for all users through the Configuration Page
  - This feature allows for dynamic management of user interface elements, enhancing system flexibility and user experience customization
  - Items that can be configured include:
    - The option to delete session history
    - Visibility of message metadata
    - Configuration of chat Kwargs
    - Customization of prompt templates
    - Adjust chat history buffer settings
    - Modify the number of RAG documents to be included in the retrieval process (TopK)
    - Ability to upload RAG documents
    - Ability to upload in-context documents
- System Banner Management:
  - The Configuration Page now includes functionality for administrators to manage the system banner
  - Administrators can activate, deactivate, and update the content of the system banner

### LISA Documentation Site

- We are pleased to announce the launch of the official [LISA Documentation site](https://awslabs.github.io/LISA/)
- This comprehensive resource provides customers with additional guides and extensive information on LISA
- The documentation is also optionally deployable within your environment during LISA deployment
- The team is continuously working to add and expand content available on this site

## Enhancements

- Implemented a selection-based interface for instance input, replacing free text entry
- Improved CDK Nag integration across stacks
- Added functionality for administrators to specify block volume size for models, enabling successful deployment of larger models
- Introduced options for administrators to choose between Private or Regional API Gateway endpoints
- Enabled subnet specification within the designated VPC for deployed resources
- Implemented support for headless deployment execution

## Bug Fixes

- Resolved issues with Create and Update model alerts to ensure proper display in the modal
- Enhanced error handling for model creation/update processes to cover all potential scenarios

## Coming Soon

- Version 3.3.0 will include a new RAG ingestion pipeline. This will allow users to configure an S3 bucket and an ingestion trigger. When triggered, these documents will be pre-processed and loaded into the selected vector store.

## Acknowledgements

- @bedanley
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v3.1.0...v3.2.0>

# v3.1.0

## Enhancements

### Model Management Administration

- Supports customers updating a subset of model properties through the model management user interface (UI) or APIs
- These new model management features are also limited to users in the configured IDP LISA administration group
- This feature prevents customers from having to delete and re-create models every time they want to make changes to available models already deployed in the infrastructure

### Other Enhancements

- Updated the chat UI to pull available models from the model management APIs instead of LiteLLM. This will allow the UI to pull all metadata that is stored about a model to properly enable/disable features, current model status is used to ensure users can only interact with `InService` models when chatting
- Updated default Model Creation values, so that there are fewer fields that should need updating when creating a model through the UI
- Removed the unnecessary fields for ECS config in the properties file. LISA will be able to go and pull the weights with these optional values and if an internet connection is available
- Added the deployed LISA version in the UI profile dropdown so users understand what version of the software they are using

## Bug fixes

- Updated naming prefixes if they are populated to prevent potential name clashes, customers can now  more easily use prefix resource names with LISA
- Fixed an issue where a hard reload was not pulling in the latest models
- Resolved a deployment issue where the SSM deployment parameter was being retained
- Addressed an issue where users could interact with the chat API if a request was being processed by hitting the `Enter` key

## Coming Soon

- Version 3.2.0 will simplify the deployment process by removing all but the key properties required for the deployment, and extracting constants into a separate file as optional items to override. This will make LISA's deployment process a lot easier to understand and manage.

## Acknowledgements

- @petermuller
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v3.0.1...v3.1.0>

# v3.0.1

## Bug fixes

- Updated our Lambda admin validation to work for no-auth if user has the admin secret token. This applies to model management APIs.
- State machine for create model was not reporting failed status
- Delete state machine could not delete models that weren't stored in LiteLLM DB

## Enhancements

- Added units to the create model wizard to help with clarity
- Increased default timeouts to 10 minutes to enable large documentation processing without errors
- Updated ALB and Target group names to be lower cased by default to prevent networking issues

## Coming Soon

- 3.1.0 will expand support for model management. Administrators will be able to modify, activate, and deactivate models through the UI or APIs. The following release we will continue to ease deployment steps for customers through a new deployment wizard and updated documentation.

## Acknowledgements

- @petermuller
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v3.0.0...v3.0.1>

# v3.0.0

## Key Features

### Model Management Administration

- Supports customers creating and deleting models through a new model management user interface (UI), or APIs
- Our new Model Management access limits these privileges to users in the configured IDP LISA administration group
- This feature prevents customers from having to re-deploy every time they want to add or remove available models

### Note

- These changes will require a redeployment of LISA
- Take note of your configuration file and the models you have previously configured. Upon deployment of LISA 3.0 these models will be deleted and will need to be added back via the new model management APIs or UI
- You can see breaking changes with migrating from 2.0 -> 3.0 in the README

## Enhancements

- Updated our documentation to include more details and to account for model management

## Coming Soon

- 3.0.1 will expand support for model management. Administrators will be able to modify, activate, and deactivate models through the UI or APIs. The following release we will continue to ease deployment steps for customers through a new deployment wizard and updated documentation.

## Acknowledgements

- @jtblack-aws
- @buejosep
- @petermuller
- @stephensmith-aws
- @estohlmann
- @dustins

**Full Changelog**: <https://github.com/awslabs/LISA/compare/v2.0.1...v3.0.0>

# March 26, 2024

#### Breaking changes

- [V1282850793] Shorten logical and physical CDK resource names
  - Long resource names were causing collisions when they were getting truncated. This was particularly problematic for customers using the Enterprise CDK `PermissionsBoundaryAspect`.
  - By updating these resource names and naming conventions you will not be able to simply redploy the latest changes on top of your existing deployment.
- [V1282892036] Combine Session, Chat, and RAG API Gateways into a single API Gateway
  - While Session, Chat, and RAG all remain completely optional, deploying any combination of them will result in a single API Gateway (with configurable custom domain)

#### Enhancements

- [V1282843657] Add support for PGVector VectorStore
  - Customers can now configure LISA to use PGVector in addition or in place of OpenSearch for their RAG repository. LISA can connect to an existing RDS Postgres instance or one can be deployed as part of the LISA deployment.
  - PGVector is now the "default" configuration in the `config.yaml` file as PGVector is considerably faster to deploy for demo/test purposes
- [V1282894257] Improved support for custom DNS
  - Customers can now specify a custom domain name for the LISA API Gateway as well as the LISA Serve REST ALB. If these values are set in the `config.yaml` file the UI will automatically use the correct pathing when making service requests without needing any additional code changes.
- [V1282858379] Move advanced chat configuration options between a collapsible "Advanced configuration" sectoin
  - The chat "control panel" has been redesigned to hide the following items chat buffer, model kwargs, prompt template, and the metadata toggle
- [V1282855530] Add support for Enterprise CDK PermissionBoundaryAspect and custom synthesizer
  - Added new property to the `config.yaml` to allow customers to optionally specify a configuration for the PermissionBoundaryAspect. If counfigured the aspect will be applied to all stacks
  - Added new property to the `config.yaml` to allow customers to optionally specify a stack sythensizer for the deployment. If counfigured the specified synthesizer will be set as a property on all stacks
- [V1282860639] Add support for configuring a system banner
  - Customers can customize the foreground, background, and text content via `config.yaml`
- [V1282834825] Support for bringing an existing VPC
  - Customers can optionally specify a VPC ID in `config.yaml`. If set LISA will import the corresponding VPC instead of creating a new one.
- [V1282880371] Support for additional (smaller) instance types for use with the LISA Serve REST API
  - Default is now an `m5.large` however customers can use any instance type they wish although they may need to update `schema.ts` if the instance type isn't already listed there

#### Bugs

- [AIML-ADC-7604] Rag context not visible in metadata until subsequent messages
  - This has been addressed by adding a dedicated `ragContext` property to the message metadata. The relevant documents including s3 key will now be visible when sending a message with a RAG repository and embedding model selected.
- [V1283663967] Chat messages occasionally wrap
  - Sometimes the model returns text that gets wrapped in `<pre><code> </code></pre>`. The default style for this content now has word-wrap and word-break styles applied to prevent the message overflowing.

#### Additional changes

- Resolved issue with files being added to the selected files list twice during RAG ingest.
- Added flashbar notification and automatically close RAG modal after successful upload
- Customers can optionally specify an existing OpenSearch cluster to use rather than creating one. When specifying an existing cluster customers will need to ensure the clsuter is reachable from the VPCs in which the RAG lambdas are running.
