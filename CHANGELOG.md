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
* @bedanley
* @estohlmann
* @dustins

**Full Changelog**: https://github.com/awslabs/LISA/compare/v3.4.0...v3.5.0

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
* @bedanley
* @estohlmann
* @dustins

**Full Changelog**: https://github.com/awslabs/LISA/compare/v3.3.2...v3.4.0

# v3.3.2
## Bug Fixes
- Resolved issue where invalid schema import was causing create model api calls to fail
- Resolved issue where RAG citations weren't being populated in metadata for non-streaming requests
- Resolved issue where managing in-memory file context wouldn't display success notification and close the modal

## Acknowledgements
* @bedanley
* @estohlmann
* @dustins

**Full Changelog**: https://github.com/awslabs/LISA/compare/v3.3.1...v3.3.2

# v3.3.1
## Bug Fixes
- Resolved issue where AWS partition was hardcoded in RAG Pipeline
- Added back in LiteLLM environment override support
- Updated Makefile Model and ECR Account Number parsing

## Acknowledgements
* @bedanley
* @estohlmann
* @dustins

**Full Changelog**: https://github.com/awslabs/LISA/compare/v3.3.0...v3.3.1

# v3.3.0
## Key Features
### RAG ETL Pipeline
- This feature introduces a second RAG ingestion capability for LISA customers. Today, customers can manually upload documents via the chatbot user interface directly into a vector store. With this new ingestion pipeline, customers have a flexible, scalable solution for automating the loading of documents into configured vector stores.

## Enhancements
- Implemented a confirmation modal prior to closing the create model wizard, enhancing user control and preventing accidental data loss
- Added functionality allowing users to optionally override auto-generated security groups with custom security groups at deployment time

## Acknowledgements
* @bedanley
* @djhorne-amazon
* @estohlmann
* @dustins

**Full Changelog**: https://github.com/awslabs/LISA/compare/v3.2.1...v3.3.0


# v3.2.1
## Bug Fixes
- Resolved issue where subnet wasn't being passed into ec2 instance creation
- Resolved role creation issue when deploying with custom subnets
- Updated docker image to grant permissions on copied in files

## Coming Soon
- Version 3.3.0 will include a new RAG ingestion pipeline. This will allow users to configure an S3 bucket and an ingestion trigger. When triggered, these documents will be pre-processed and loaded into the selected vector store.

## Acknowledgements
* @bedanley
* @estohlmann

**Full Changelog**: https://github.com/awslabs/LISA/compare/v3.2.0...v3.2.1


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
* @bedanley
* @estohlmann
* @dustins

**Full Changelog**: https://github.com/awslabs/LISA/compare/v3.1.0...v3.2.0


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
* @petermuller
* @estohlmann
* @dustins

**Full Changelog**: https://github.com/awslabs/LISA/compare/v3.0.1...v3.1.0


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
* @petermuller
* @estohlmann
* @dustins

**Full Changelog**: https://github.com/awslabs/LISA/compare/v3.0.0...v3.0.1


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
* @jtblack-aws
* @buejosep
* @petermuller
* @stephensmith-aws
* @estohlmann
* @dustins

**Full Changelog**: https://github.com/awslabs/LISA/compare/v2.0.1...v3.0.0


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
