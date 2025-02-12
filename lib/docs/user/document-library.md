# RAG Document Library Management

## Overview

Through LISA's Chat UI Document Library, users manage files that were uploaded automatically via the ingestion pipeline,
or manually by users in chat sessions.

## Features

### Document Viewing

- Users choose from vector stores that they have access to. Then they may view the list of documents in that vector
  store
- Documents are displayed in a searchable and sortable table format
- Document metadata displayed includes file name, size, upload date, and owner.
- Users may also download documents

### Document Management

- **Delete Operations**: Users may delete documents that they own. Admins can delete any document
- **Download Operations**: Users may download documents that they have access to.
- **Batch Operations**: Multiple documents can be selected for bulk actions: deletion or download

### Repository-based Organization

- Documents are organized by repositories
- Users can only see and interact with documents in repositories that they have access to. Documents are loaded either
  directly by users during chat sessions or via ingestion pipelines that Admins configure
- Repository-specific permissions determine user capabilities

## Configuration

### Visibility Control

Admins can hide the Document Library from the UI by toggling off the `Show Document Library` configuration
under [Configuration](/admin/ui-configuration.md)