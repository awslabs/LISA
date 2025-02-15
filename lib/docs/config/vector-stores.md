# Retrieval-Augmented Generation (RAG)

Retrieval-Augmented Generation (RAG) is a technique that enhances language models by combining retrieval and generation. Instead of relying solely on pre-trained knowledge, RAG first retrieves relevant external documents (e.g., from a database, search engine, or vector store) and then uses them to generate more accurate and context-aware responses.

Customers have two methods to load files into vector stores configured with LISA. Customers can either manually load files via the chatbot user interface (UI), or via an ingestion pipeline.

## Configuration

### Chat UI

Files loaded via the chatbot UI are limited by Lambda's service limits on document file size and volume.

### Automated Document Vector Store Ingestion Pipeline

The Automated Document Ingestion Pipeline is designed to enhance LISA's RAG capabilities. Documents loaded via a pipeline are not subject to these limits, further expanding LISA’s ingestion capabilities. This pipeline feature supports the following document file types: PDF, docx, and plain text. The individual file size limit is 50 MB.

This feature provides customers with a flexible, scalable solution for loading documents into configured vector stores.

Customers can set up many ingestion pipelines. For each pipeline, they define the vector store and embedding model, and ingestion trigger. Each pipeline can be set up to run based on an event trigger, or to run daily. From there, pre-processing kicks off to convert files into the necessary format. From there, processing kicks off to ingest the files with the specified embedding model and loads the data into the designated vector store. This feature leverages LISA’s existing chunking and vectorizing capabilities.

LISA also supports deleting files and content from a vector store, as well as listing the file names and dates ingested.

### Benefits
1. **Flexibility**: Accommodates various data sources and formats
2. **Efficiency**: Streamlines the document ingestion process with pre-processing and intelligent indexing
3. **Customization**: Allows customers to choose and easily switch between preferred vector stores
4. **Integration**: Leverages existing LISA capabilities while extending functionality

### Use Cases
- Large-scale document ingestion for enterprise customers
- Integration of external mission-critical data sources
- Customized knowledge base creation for specific industries or applications

This new Automated Document Ingestion Pipeline significantly expands LISA's capabilities, providing customers with a powerful tool for managing and utilizing their document-based knowledge more effectively.

> **_NOTE:_**  Event ingestion requires Amazon EventBridge to be enabled on the S3 bucket. You can enable this in the bucket's properties configuration page in the AWS Management Console.
### Configuration Example

RAG repositories and Automated Ingestion Pipelines are configurable through the chatbot web UI or programmatically via the API for managing RAG repositories, allowing customers to tailor the ingestion process to their specific needs.

#### Request Example:

```bash
curl -s -H 'Authorization: Bearer <your_token>' -XPOST -d @body.json https://<apigw_endpoint>/models
```

#### Response Example:

```json
// body.json
{
  "ragConfig": {
    "repositoryId": "my-vector-store",
    "repositoryName": "My Vector Store",
    "type": "pgvector",
    "rdsConfig": {
      "username": "postgres"
    },
    "pipelines": [
      {
        "chunkOverlap": 51,
        "chunkSize": 256,
        "embeddingModel": "titan-embed-text-v1",
        "trigger": "event",
        "s3Bucket": "my-ingestion-bucket",
        "s3Prefix": "/some/path/to/watch"
      }
    ]
  }
}
```

#### Explanation of Response Fields:

- `status`: "success" if the state machine was started successfully.
- `executionArn`: The state machine ARN used to deploy the vector store.


<!--@include: ./rag-schema.md -->