# LISA Configuration Schema

## OpenSearchExistingClusterConfig

_Object containing the following properties:_

| Property            | Description                          | Type                       |
| :------------------ | :----------------------------------- | :------------------------- |
| **`endpoint`** (\*) | Existing OpenSearch Cluster endpoint | `string` (_min length: 1_) |

_(\*) Required._

## OpenSearchNewClusterConfig

_Object containing the following properties:_

| Property                 | Description                                                                                                                                                                         | Type                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Default              |
| :----------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------------- |
| `dataNodes`              | The number of data nodes (instances) to use in the Amazon OpenSearch Service domain.                                                                                                | `number` (_≥1_)                                                                                                                                                                                                                                                                                                                                                                                                                                                     | `2`                  |
| `dataNodeInstanceType`   | The instance type for your data nodes                                                                                                                                               | `string`                                                                                                                                                                                                                                                                                                                                                                                                                                                            | `'r7g.large.search'` |
| `masterNodes`            | The number of instances to use for the master node                                                                                                                                  | `number` (_≥0_)                                                                                                                                                                                                                                                                                                                                                                                                                                                     | `0`                  |
| `masterNodeInstanceType` | The hardware configuration of the computer that hosts the dedicated master node                                                                                                     | `string`                                                                                                                                                                                                                                                                                                                                                                                                                                                            | `'r7g.large.search'` |
| `volumeSize`             | The size (in GiB) of the EBS volume for each data node. The minimum and maximum size of an EBS volume depends on the EBS volume type and the instance type to which it is attached. | `number` (_≥20_)                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `20`                 |
| `volumeType`             | The EBS volume type to use with the Amazon OpenSearch Service domain                                                                                                                | _Native enum:_<ul><li>`STANDARD = 'standard'`</li><li>`IO1 = 'io1'`</li><li>`IO2 = 'io2'`</li><li>`GP2 = 'gp2'`</li><li>`GP3 = 'gp3'`</li><li>`ST1 = 'st1'`</li><li>`SC1 = 'sc1'`</li><li>`GENERAL_PURPOSE_SSD = 'gp2'`</li><li>`GENERAL_PURPOSE_SSD_GP3 = 'gp3'`</li><li>`PROVISIONED_IOPS_SSD = 'io1'`</li><li>`PROVISIONED_IOPS_SSD_IO2 = 'io2'`</li><li>`THROUGHPUT_OPTIMIZED_HDD = 'st1'`</li><li>`COLD_HDD = 'sc1'`</li><li>`MAGNETIC = 'standard'`</li></ul> | `'gp3'`              |
| `multiAzWithStandby`     | Indicates whether Multi-AZ with Standby deployment option is enabled.                                                                                                               | `boolean`                                                                                                                                                                                                                                                                                                                                                                                                                                                           | `false`              |

_All properties are optional._

## RagRepositoryConfig

Configuration schema for RAG repository. Defines settings for OpenSearch.

_Object containing the following properties:_

| Property                | Description                                                                                                                                                                                                                                         | Type                                                                                                                               | Default |
| :---------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------- | :------ |
| **`repositoryId`** (\*) | A unique identifier for the repository, used in API calls and the UI. It must be distinct across all repositories.                                                                                                                                  | `string` (_min length: 1, regex: `/^[a-z0-9-]{1,63}/`, regex: `/^(?!-).*(?<!-)$/`_)                                                |         |
| `repositoryName`        | The user-friendly name displayed in the UI.                                                                                                                                                                                                         | `string`                                                                                                                           |         |
| **`type`** (\*)         | The vector store designated for this repository.                                                                                                                                                                                                    | _Native enum:_<ul><li>`OPENSEARCH = 'opensearch'`</li><li>`PGVECTOR = 'pgvector'`</li></ul>                                        |         |
| `opensearchConfig`      |                                                                                                                                                                                                                                                     | [OpenSearchExistingClusterConfig](#opensearchexistingclusterconfig) _or_ [OpenSearchNewClusterConfig](#opensearchnewclusterconfig) |         |
| `rdsConfig`             | Configuration schema for RDS Instances needed for LiteLLM scaling or PGVector RAG operations.<br /> <br /> The optional fields can be omitted to create a new database instance, otherwise fill in all fields to use an existing database instance. | [RdsInstanceConfig](#rdsinstanceconfig)                                                                                            |         |
| `pipelines`             | Rag ingestion pipeline for automated inclusion into a vector store from S3                                                                                                                                                                          | _Array of [RagRepositoryPipeline](#ragrepositorypipeline) items_                                                                   | `[]`    |
| `allowedGroups`         | The groups provided by the Identity Provider that have access to this repository. If no groups are specified, access is granted to everyone.                                                                                                        | `Array<string (_min length: 1_)>`                                                                                                  | `[]`    |

_(\*) Required._

## RagRepositoryPipeline

_Object containing the following properties:_

| Property                  | Description                                                                                                                                                    | Type                 | Default   |
| :------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------- | :-------- |
| `chunkSize`               | The size of the chunks used for document segmentation.                                                                                                         | `number`             | `512`     |
| `chunkOverlap`            | The size of the overlap between chunks.                                                                                                                        | `number`             | `51`      |
| **`embeddingModel`** (\*) | The embedding model used for document ingestion in this pipeline.                                                                                              | `string`             |           |
| **`s3Bucket`** (\*)       | The S3 bucket monitored by this pipeline for document processing.                                                                                              | `string`             |           |
| **`s3Prefix`** (\*)       | The prefix within the S3 bucket monitored for document processing.                                                                                             | `string`             |           |
| `trigger`                 | The event type that triggers document ingestion.                                                                                                               | `'daily' \| 'event'` | `'event'` |
| `autoRemove`              | Enable removal of document from vector store when deleted from S3. This will also remove the file from S3 if file is deleted from vector store through API/UI. | `boolean`            | `true`    |

_(\*) Required._

## RdsInstanceConfig

Configuration schema for RDS Instances needed for LiteLLM scaling or PGVector RAG operations.
 
 The optional fields can be omitted to create a new database instance, otherwise fill in all fields to use an existing database instance.

_Object containing the following properties:_

| Property           | Description                                                                                   | Type     | Default      |
| :----------------- | :-------------------------------------------------------------------------------------------- | :------- | :----------- |
| `username`         | The username used for database connection.                                                    | `string` | `'postgres'` |
| `passwordSecretId` | The SecretsManager Secret ID that stores the existing database password.                      | `string` |              |
| `dbHost`           | The database hostname for the existing database instance.                                     | `string` |              |
| `dbName`           | The name of the database for the database instance.                                           | `string` | `'postgres'` |
| `dbPort`           | The port of the existing database instance or the port to be opened on the database instance. | `number` | `5432`       |

_All properties are optional._
