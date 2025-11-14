# Breaking Changes

## v6.0.0

Beginning with LISA v6.0.0, the API token table is no longer owned by the Serve stack—it's been moved into the API Base
stack so MCP hosting and future API workloads can scale independently. As part of this move the DynamoDB table is renamed
(`LisaServeTokenTable` → `LisaApiBaseTokenTable`). CloudFormation cannot migrate the data automatically, so **admins must
export all existing API keys before upgrading** and then create the corresponding records in the new table after the
deployment completes. If you rely on programmatic API access (admin keys, service accounts, automations, etc.),
make sure to capture the current values so they can be re-added once the new table exists.


## v4.0.0

With the release of LISA v4.0, we introduced a significant update to the configuration and functionality of RAG
repositories, enabling dynamic configuration of vector stores and ingestion pipelines. New vector stores and
ingestion pipelines can now only be created using this dynamic system. Existing RAG configurations defined in YAML
will continue to function and can be updated; however, once removed, they cannot be recreated using the YAML-based
configuration.

## Migrating to v3.2.0

With the release of LISA v3.2.0, we have implemented a significant update to the configuration file schema to streamline
the deployment process. The previous single config.yaml file has been deprecated in favor of a more flexible two-file
system: config-base.yaml and config-custom.yaml.

The config-base.yaml file now contains default properties, which can be selectively overridden using the
config-custom.yaml file. This new structure allows for greater customization while maintaining a standardized base
configuration.

To facilitate the transition to this new configuration system, we have developed a migration utility. Users can execute
the command `npm run migrate-properties` to automatically convert their existing config.yaml file into the new
config-custom.yaml format.

This update enhances the overall flexibility and maintainability of LISA configurations, providing a more robust
foundation for future developments and easier customization for end-users.

## v2 to v3 Migration

With the release of LISA v3.0.0, we have introduced several architectural changes that are incompatible with previous
versions. Although these changes may cause some friction for existing users, they aim to simplify the deployment
experience and enhance long-term scalability. The following breaking changes are critical for existing users planning to
upgrade:

1. Model Deletion Upon Upgrade: Models deployed via EC2 and ECS using the config.yaml file’s ecsModels list will be
   deleted during the upgrade process. LISA has migrated to a new model deployment system that manages models
   internally, rendering the ecsModels list obsolete. We recommend backing up your model settings to facilitate their
   redeployment through the new Model Management API with minimal downtime.
1. Networking Changes and Full Teardown: Core networking changes require a complete teardown of the existing LISA
   installation using the make destroy command before upgrading. Cross-stack dependencies have been modified,
   necessitating this full teardown to ensure proper application of the v3 infrastructure changes. Additionally, users
   may need to manually delete some resources, such as ECR repositories or S3 buckets, if they were populated before
   CloudFormation began deleting the stack. This operation is destructive and irreversible, so it is crucial to back up
   any critical configurations and data (e.g., S3 RAG bucket contents, DynamoDB token tables) before proceeding with the
   upgrade.
1. New LiteLLM Admin Key Requirement: The new Model Management API requires an "admin" key for LiteLLM to track models
   for inference requests. This key, while transparent to users, must be present and conform to the required format (
   starting with sk-). The key is defined in the config.yaml file, and the LISA schema validator will prompt an error if
   it is missing or incorrectly formatted.

## v3.0.0 to v3.1.0

In preparation of the v3.1.0 release, there are several changes that we needed to make in order to ensure the stability
of the LISA system.

1. The CreateModel API `containerConfig` object has been changed so that the Docker Image repository is listed in
   `containerConfig.image.baseImage` instead of
   its previous location at `containerConfig.baseImage.baseImage`. This change makes the configuration consistent with
   the config.yaml file in LISA v2.0 and prior.
2. The CreateModel API `containerConfig.image` object no longer requires the `path` option. We identified that this was
   a confusing and redundant option to set, considering
   that the path was based on the LISA code repository structure, and that we already had an option to specify if a
   model was using TGI, TEI, or vLLM. Specifying the `inferenceContainer`
   is sufficient for the system to infer which files to use so that the user does not have to provide this information.
3. The ApiDeployment stack now follows the same naming convention as the rest of the stacks that we deploy, utilization
   the deployment name and the deploymentStage names. This allows users
   to have multiple LISA installations with different parameters in the same account without needing to change region or
   account entirely. After successful deployment, you may safely delete the
   previous `${deploymentStage}-LisaApiDeployment` stack, as it is no longer in use.
4. If you have installed v3.0.0 or v3.0.1, you will need to **delete** the Models API stack so that the model deployer
   function will deploy again. The function was converted to a Docker Image
   Function so that the growing Function size would fit within the Lambda constraints. We recommend that you take the
   following actions to avoid leaked resources:
    1. Use the Model Management UI to **delete all models** from LISA. This is needed so that we delete any
       CloudFormation stacks that track GPU instances. Failure to do this will require manual
       resource cleanup to rid the account of inaccessible EC2 instances. Once the Models DynamoDB Table is deleted, we
       do not have a programmatic way to re-reference deployed models, so that is
       why we recommend deleting them first.
    2. **Only after deleting all models through the Model Management UI**, manually delete the Model Management API
       stack in CloudFormation. This will take at least 45 minutes due to Lambda's use
       of Elastic Network Interfaces for VPC access. The stack name will look like:
       `${deployment}-lisa-models-${deploymentStage}`.
    3. After the stack has been deleted, deploy LISA v3.1.0, which will recreate the Models API stack, along with the
       Docker Lambda Function.
5. The `ecsModels` section of `config.yaml` has been stripped down to only 3 fields per model: `modelName`,
   `inferenceContainer`, and `baseImage`. Just as before, the system will check to see if the models
   defined here exist in your models S3 bucket prior to LISA deployment. These values will be needed later when invoking
   the Model Management API to create a model.
