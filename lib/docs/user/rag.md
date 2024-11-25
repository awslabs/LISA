# Automated Document Ingestion Pipeline

## Overview

The Automated Document Ingestion Pipeline is a new feature designed to enhance LISA's document processing capabilities. This feature addresses the limitations of the existing RAG ingestion process and provides customers with a flexible, scalable solution for loading documents into their vector stores.

## Key Features

### External Ingestion
- Allows customers to load documents into vector stores outside of the LISA chatbot UI
- Overcomes Lambda service restrictions on document file size and volume

### Flexible Data Source Integration
- Supports ingestion from various external mission data sources
- Designed for broad compatibility with different data formats and sources

### Pre-processing Capabilities
- Includes document pre-processing as part of the ingestion pipeline
- Leverages LISA's existing chunking and vectorizing capabilities

### Customizable Vector Store Integration
- Demonstrates integration with LISA Serve for splitting, embedding, and indexing data
- Supports easy swapping between any of LISA's supported vector stores

### Intelligent Embedding and Indexing
- Performs embedding and indexing based on configurable parameters
- Optimizes document storage and retrieval efficiency

## Configuration

The Automated Document Ingestion Pipeline is highly configurable, allowing customers to tailor the ingestion process to their specific needs. Configuration is done in YAML, adding additional optional properties to your existing RAG repository definition, which specifies various parameters for the ingestion process.

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
  - If using `event` trigger, Amazon EventBridge notifications need to be enabled in the bucket configuration
- **collectionName**: The name of the collection in the vector store (project-mainline in this example)

This configuration allows customers to:

1. Fine-tune the chunking process for optimal document segmentation
2. Select the appropriate embedding model for their use case
3. Specify the source of their documents in S3
4. Choose between scheduled or event-driven ingestion
5. Organize their data into named collections within the vector store

By adjusting these parameters, customers can optimize the ingestion pipeline for their specific document types, update frequency, and retrieval requirements.

## Benefits

1. **Scalability**: Overcomes existing limitations on document size and volume
2. **Flexibility**: Accommodates various data sources and formats
3. **Efficiency**: Streamlines the document ingestion process with pre-processing and intelligent indexing
4. **Customization**: Allows customers to choose and easily switch between preferred vector stores
5. **Integration**: Leverages existing LISA capabilities while extending functionality

## Use Cases

- Large-scale document ingestion for enterprise customers
- Integration of external mission-critical data sources
- Customized knowledge base creation for specific industries or applications

---

This new Automated Document Ingestion Pipeline significantly expands LISA's capabilities, providing customers with a powerful tool for managing and utilizing their document-based knowledge more effectively.
