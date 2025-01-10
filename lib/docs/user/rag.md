# Automated Document Vector Store Ingestion Pipeline

## Overview
The Automated Document Ingestion Pipeline is designed to enhance LISA's RAG capabilities. This feature provides customers with a flexible, scalable solution for loading documents into configured vector stores. Customers have two methods to load files into vector stores configured with LISA. Customers can either manually load files via the chatbot user interface (UI), or via an ingestion pipeline. Files loaded via the chatbot UI are limited by Lambda's service limits on document file size and volume. Documents loaded via a pipeline are not subject to these limits, further expanding LISA’s ingestion capabilities. This pipeline feature supports the following document file types: PDF, docx, and plain text. The individual file size limit is 50 MB.

Customers can set up many ingestion pipelines. For each pipeline, they define the vector store and embedding model, and ingestion trigger. Each pipeline can be set up to run based on an event trigger, or to run daily. From there, pre-processing kicks off to convert files into the necessary format. From there, processing kicks off to ingest the files with the specified embedding model and loads the data into the designated vector store. This feature leverages LISA’s existing chunking and vectorizing capabilities.

An upcoming release will add support for deleting files and content, as well as listing the file names and date loaded into the vector store.

## Configuration

The Automated Document Ingestion Pipeline is configurable, allowing customers to tailor the ingestion process to their specific needs. Configuration is done in YAML, adding additional optional properties to your existing RAG repository definition, which specifies various parameters for the ingestion process.

### Sample Configuration

Below is a sample configuration snippet:

```yaml
ragRepositories:
  - repositoryId: pgvector-rag
    type: pgvector
    rdsConfig:
      username: postgres
    pipelines:
    - chunkOverlap: 51
      chunkSize: 512
      embeddingModel: ${your embedding model ID}
      s3Bucket: ${your source s3 bucket}
      s3Prefix: /
      trigger: ${daily or event (on upload)}
      collectionName: project-mainline
```

### Configuration Parameters

- **chunkOverlap**: The number of tokens to overlap between chunks (51 in this example)
- **chunkSize**: The size of each document chunk (512 tokens in this example)
- **embeddingModel**: The ID of the embedding model to be used
- **s3Bucket**: The source S3 bucket where documents are stored
- **s3Prefix**: The prefix within the S3 bucket (root directory in this example)
- **trigger**: Specifies when the ingestion should occur (daily or on upload event)
- **collectionName**: The name of the collection in the vector store (project-mainline in this example)

This configuration allows customers to:
1. Define the chunking process for optimal document segmentation
2. Select the appropriate embedding model for their use case
3. Specify the source of their documents in S3
4. Choose between scheduled or event-driven ingestion
> **_NOTE:_**  Event ingestion requires Amazon EventBridge to be enabled on the S3 bucket. You can enable this in the bucket's properties configuration page in the AWS Management Console.
5. Organize their data into named collections within the vector store

By adjusting these parameters, customers can optimize the ingestion pipeline for their specific document types, update frequency, and retrieval requirements.

## Benefits
1. **Flexibility**: Accommodates various data sources and formats
2. **Efficiency**: Streamlines the document ingestion process with pre-processing and intelligent indexing
3. **Customization**: Allows customers to choose and easily switch between preferred vector stores
4. **Integration**: Leverages existing LISA capabilities while extending functionality

## Use Cases
- Large-scale document ingestion for enterprise customers
- Integration of external mission-critical data sources
- Customized knowledge base creation for specific industries or applications

This new Automated Document Ingestion Pipeline significantly expands LISA's capabilities, providing customers with a powerful tool for managing and utilizing their document-based knowledge more effectively.
