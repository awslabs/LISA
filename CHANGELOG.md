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
