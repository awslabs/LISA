# Retrieval-Augmented Generation (RAG)

Retrieval-Augmented Generation (RAG) is a technique that enhances language models by combining retrieval and generation. Instead of relying solely on pre-trained knowledge, RAG first retrieves relevant external documents (e.g., from a database, search engine, or vector store) and then uses them to generate more accurate and context-aware responses.

## RAG Repositories and Collections

LISA RAG introduces a hierarchical architecture for managing RAG content through **repositories** and **collections**:

- **Repository**: The top-level container that defines the underlying vector store implementation (OpenSearch, PGVector, or Bedrock Knowledge Base), embedding model, and access controls. Repositories are created and managed by administrators. Repository access can be restricted to specific enterprise groups.

- **Collection**: Within repositories, collections support a logical grouping of documents. One repository can support many collections. Collection access can be restricted to specific enterprise groups. Collections enable flexible organization of content with their own chunking strategies, metadata tags, and access controls. Administrators create and manage collections via API or UI. Users can view and upload documents within a collection using LISA's Document Library and RAG file upload.

### Architecture Overview

The repository-collection model provides a two-tier organizational structure analogous to filing cabinets (repositories) containing organized drawers (collections). This architecture enables:

- **Multi-Backend Support**: Unified interface across OpenSearch, PGVector, and AWS Bedrock Knowledge Base implementations
- **Configuration Isolation**: Each collection maintains independent chunking strategies, embedding models, and access controls
- **Scalable Organization**: Organize documents by department, project, content type, or security classification without infrastructure changes
- **Backward Compatibility**: Existing repositories automatically include a default collection based on the embedding model ID

### Key Benefits

- **Dynamic Management**: Create, update, and delete collections via API without infrastructure changes
- **Optimized Chunking**: Configure chunking strategies per collection to match content type (legal documents, code, customer support tickets)
- **Granular Access Control**: Enforce user group-based permissions at both the repository and collection level
- **Multi-tenancy**: Within repositories, further manage access by restricting collections access (e.g., by enterprise groups for specific organizations, departments, or teams)
- **Enhanced Metadata**: Tag documents with collection-specific metadata for powerful filtering
- **Flexible Embedding Models**: Each collection can use its own embedding model, optimizing retrieval for specific document types

### Document Ingestion Methods

Customers have two methods to load files into repositories configured with LISA:

1. **Manual Upload**: Load files via the chat assistant user interface (UI), or API
2. **Automated Pipeline**: (Admins-only) Configure LISA's ingestion pipelines for automated document processing

## Configuration

### Chat Assistant UI

Files loaded via the chat assistant UI are limited by size, and are processed through a batch job. The status of the job can be viewed within the RAG File Upload dialog. When uploading documents through the UI, you can select a specific collection within a repository. If no collection is specified, documents are ingested into the default collection, which defaults to the embedding model associated with the parent repository.

### Automated Document Repository Ingestion Pipeline

LISA's automated document ingestion pipeline supports larger files and broader file types. Supported file types include: PDF, docx, and plain text. The individual file size limit is 50 MB. LISA's pipelines offer chunking support for fixed size chunking or no chunking. For customers using Amazon Bedrock Knowledge Bases, LISA supports all chunking strategies offered by the service. LISA's automated ingestion pipelines provide customers with a flexible, scalable solution for loading documents into configured repositories and collections.

Customers can set up multiple ingestion pipelines for a repository. For each pipeline they define:
- The target repository and collection
- Embedding model (inherited from repository if not defined)
- Chunking strategy (can be customized per pipeline)
- Ingestion trigger (event-based or daily schedule)
- S3 bucket and prefix to monitor

Pipelines can be configured at both the repository level (for default collection ingestion) and at the collection level (for targeted ingestion). Each pipeline can run based on an event trigger or daily schedule. Pre-processing converts files into the necessary format, then processing ingests the files with the specified embedding model and loads the data into the designated collection within the repository.

LISA also supports deleting files and content from repositories, as well as listing the file names and dates ingested. When `autoRemove` is enabled, deleting a document from the repository will also remove it from S3, and vice versa.

#### Benefits

The automated ingestion pipeline provides:

1. **Flexibility**: Accommodates various data sources and formats
2. **Efficiency**: Streamlines the document ingestion process with pre-processing and intelligent indexing
3. **Customization**: Allows customers to choose and easily switch between preferred vector stores
4. **Integration**: Leverages existing LISA capabilities while extending functionality

#### Use Cases

Common use cases for automated ingestion include:

- Large-scale document ingestion for enterprise customers
- Integration of external mission-critical data sources
- Customized knowledge base creation for specific industries or applications
- Department or project-specific document collections with isolated access
- Content-type optimized chunking strategies (legal, technical, conversational)

> **_NOTE:_**  Event ingestion requires Amazon EventBridge to be enabled on the S3 bucket. You can enable this in the bucket's properties configuration page in the AWS Management Console.

## Managing Collections

### Collection Lifecycle

Collections can be created, updated, and deleted through the LISA UI or API. Each collection maintains:

- **Chunking Strategy**: Optimized for the content type (fixed size or none)
- **Embedding Model**: Inherited from repository or customized per collection
- **Access Control**: User group restrictions inherited from the repository or customized per collection
- **Metadata Tags**: Custom tags for organizing and filtering documents
- **Privacy Settings**: Collections can be marked as private for restricted visibility
- **Ingestion Pipelines**: Dedicated pipelines for automated document ingestion

Collections support flexible chunking configuration with multiple override levels:

- **Default Strategy**: Inherited from the repository configuration
- **Collection Strategy**: Override at the collection level for content-specific optimization
- **Pipeline Strategy**: Further override at the ingestion pipeline level
- **API Override**: Optionally allow per-document chunking strategy via API (controlled by `allowChunkingOverride` flag)

### Default Collections

Every repository includes a default collection based on the embedding model ID. This ensures backward compatibility with existing LISA deployments (pre v6.0). When no collection is specified during document ingestion or retrieval, the default collection is used.

Default collections provide:

- **Automatic Creation**: Generated automatically during repository creation with no additional configuration
- **Zero Downtime Migration**: Existing documents remain accessible through default collections without database migrations
- **Optional Adoption**: Collections are completely optional—repositories continue to function without explicit collection configuration
- **Preserved Documents**: All existing documents remain accessible through default collections after upgrade

### Document Lifecycle Management

LISA implements intelligent document lifecycle management that respects how content is created and maintained:

- **Ingestion Type Tracking**: The system distinguishes between LISA-managed documents, pipeline-generated content, and user-managed documents in Bedrock Knowledge Bases
- **Asynchronous Deletion**: Collection deletion operations execute asynchronously with optimized cleanup strategies per repository type:
  - OpenSearch: Drops the entire index before document deletion
  - PGVector: Drops the collection table/schema
  - Bedrock Knowledge Base: Performs bulk document deletion
- **Document Preservation**: User-managed documents in Bedrock Knowledge Bases are automatically preserved during collection operations, ensuring external content is not inadvertently removed
- **Status Tracking**: Collections maintain status indicators (ACTIVE, DELETE_IN_PROGRESS, DELETE_FAILED) for monitoring lifecycle operations

### Collection Permissions

Collection access is controlled through user groups:

- **Repository-level Groups**: Collections inherit allowed groups from their parent repository by default
- **Collection-level Groups**: Collections can override with their own group restrictions for finer control
- **Admin Access**: Administrators have full access to all collections across all repositories
- **User Collection Creation**: Repositories can be configured to allow or restrict user-created collections via the `allowUserCollections` flag

## Configuration Examples

RAG repositories and collections are configurable through the chat assistant web UI or programmatically via the API, allowing customers to tailor the ingestion process to their specific needs.

### Creating a Repository

Repositories are created by administrators and define the underlying vector store implementation, embedding model, and default access controls.

#### Request Example:

```bash
curl -s -H 'Authorization: Bearer <your_token>' -XPOST -d @repository.json https://<apigw_endpoint>/repository
```

```json
// repository.json
{
  "repositoryId": "my-rag-repository",
  "repositoryName": "My RAG Repository",
  "type": "pgvector",
  "embeddingModelId": "amazon.titan-embed-text-v1",
  "rdsConfig": {
    "username": "postgres"
  },
  "allowedGroups": ["engineering", "data-science"],
  "metadata": {
    "tags": ["production", "customer-docs"]
  },
  "allowUserCollections": true,
  "pipelines": [
    {
      "chunkingStrategy": {
        "type": "fixed",
        "size": 512,
        "overlap": 51
      },
      "trigger": "event",
      "s3Bucket": "my-ingestion-bucket",
      "s3Prefix": "documents/",
      "autoRemove": true
    }
  ]
}
```

#### Response Fields:

- `status`: "success" if the state machine was started successfully
- `executionArn`: The state machine ARN used to deploy the repository

### Creating a Collection

Collections can be created by users with appropriate permissions within an existing repository.

#### Request Example:

```bash
curl -s -H 'Authorization: Bearer <your_token>' -XPOST -d @collection.json https://<apigw_endpoint>/repository/my-rag-repository/collection
```

```json
// collection.json
{
  "name": "Legal Documents",
  "description": "Collection for legal contracts and agreements",
  "chunkingStrategy": {
    "type": "fixed",
    "size": 512,
    "overlap": 51
  },
  "allowChunkingOverride": false,
  "metadata": {
    "tags": ["legal", "contracts", "confidential"]
  },
  "allowedGroups": ["legal-team", "compliance"],
  "private": true,
  "pipelines": [
    {
      "s3Bucket": "legal-docs-bucket",
      "s3Prefix": "contracts/",
      "trigger": "event",
      "autoRemove": true
    }
  ]
}
```

#### Response Fields:

- `collectionId`: Unique identifier for the created collection (UUID)
- `repositoryId`: Parent repository identifier
- `name`: User-friendly collection name
- `embeddingModel`: Inherited from parent repository
- `createdBy`: User ID of collection creator
- `createdAt`: Creation timestamp (ISO 8601)
- `status`: Collection status (ACTIVE)

### Listing Collections

Retrieve all collections accessible to the current user within a repository.

#### Request Example:

```bash
curl -s -H 'Authorization: Bearer <your_token>' \
  'https://<apigw_endpoint>/repository/my-rag-repository/collections?page=1&pageSize=20&sortBy=name&sortOrder=asc'
```

#### Query Parameters:

- `page`: Page number (default: 1)
- `pageSize`: Items per page (default: 20, max: 100)
- `filter`: Filter by name or description (optional)
- `sortBy`: Sort field - `name`, `createdAt`, or `updatedAt` (default: `createdAt`)
- `sortOrder`: Sort order - `asc` or `desc` (default: `desc`)

## UI Components

### RAG Repository Management (Admin)

Administrators access repository management through the Admin Configurations page. This interface provides:

- Create, update, and delete repositories
- Configure vector store implementation (OpenSearch, PGVector, Bedrock Knowledge Base)
- Set default embedding models and chunking strategies
- Define repository-level access controls
- Configure metadata tags
- Enable or disable user-created collections

### RAG Collection Library

The Collection Library is accessible from the Document Library page and provides:

- Browse collections within accessible repositories
- Create new collections (if permitted)
- Update collection settings
- Delete collections (if permitted)
- View collection metadata and statistics
- Filter document collection

Collections are organized in a tree structure, similar to folders, making it intuitive to navigate and manage documents.

### Chat Interface

The chat interface includes repository and collection selection:

- Select a repository from available options
- Choose a specific collection within the repository
- Default collection is used if none specified
- Embedding model is automatically determined by the collection

### Document Library

The Document Library displays documents organized by collection:

- Tree view showing repository → collection → documents hierarchy
- Filter and search within specific collections
- Upload documents to selected collections
- View document metadata including collection assignment
- Delete documents with optional S3 removal (when `autoRemove` is enabled)

<!--@include: ./rag-schema.md -->
