# RAG Evaluation

Comprehensive retrieval quality evaluation for LISA RAG backends using precision, recall, and NDCG metrics.

## Overview

The RAG evaluation suite measures how well your RAG system retrieves relevant documents for user queries. It supports:

- **Bedrock Knowledge Bases** - Evaluate AWS Bedrock KB retrieval quality
- **LISA API Backends** - Evaluate OpenSearch, PGVector, or other LISA-hosted vector stores
- **Cross-Backend Comparison** - Compare multiple backends side-by-side
- **Multiple Metrics** - Precision@k, Recall@k, NDCG@k (Normalized Discounted Cumulative Gain)

## Quick Start

### Prerequisites

1. **LISA Deployment** with RAG enabled (OpenSearch, PGVector, or Bedrock KB)
2. **AWS Credentials** configured with access to:
   - AWS Secrets Manager (for LISA management keys)
   - DynamoDB (for token registration)
   - Bedrock (if evaluating Bedrock KB)
3. **Python Environment** with LISA SDK installed:
   ```bash
   source .venv/bin/activate  # Activate LISA venv
   ```

### Setup

1. **Create your config file:**
   ```bash
   cd test/integration/rag/eval_datasets
   cp eval_config.example.yaml eval_config.yaml
   ```

2. **Edit `eval_config.yaml`** with your deployment details:
   - AWS region
   - API Gateway URLs
   - Knowledge Base IDs
   - S3 bucket paths
   - Repository and collection IDs

3. **Create your golden dataset:**
   ```bash
   cp golden-dataset.example.jsonl golden-dataset.jsonl
   ```

4. **Edit `golden-dataset.jsonl`** with your test queries (see [Golden Dataset Format](#golden-dataset-format))

### Run Evaluation

```bash
# From repo root
python -m lisapy.evaluation \
  --config test/integration/rag/eval_datasets/eval_config.yaml \
  --dataset test/integration/rag/eval_datasets/golden-dataset.jsonl
```

**With verbose logging:**
```bash
python -m lisapy.evaluation \
  --config test/integration/rag/eval_datasets/eval_config.yaml \
  --dataset test/integration/rag/eval_datasets/golden-dataset.jsonl \
  --verbose
```

## Configuration

### Config File Structure (`eval_config.yaml`)

```yaml
region: us-east-1  # AWS region
k: 5  # Evaluate top-k results

# Document registry: short names used in golden dataset
documents:
  doc1: "path/to/document1.pdf"
  doc2: "path/to/document2.pdf"

backends:
  # Bedrock Knowledge Base
  bedrock_kb:
    - name: "Bedrock KB Production"
      knowledge_base_id: "ABCDEFGHIJ"
      s3_bucket: "s3://kb-data-bucket"

  # LISA API backends (OpenSearch, PGVector)
  lisa_api:
    - name: "OpenSearch Production"
      api_url: "https://lisa-rest-api-endpoint/STAGE"
      deployment_name: "your-deployment-name"
      repo_id: "opensearch-repo"
      collection_id: "default"
      s3_bucket: "s3://docs-bucket"
```

**Key Fields:**

| Field | Description |
|-------|-------------|
| `region` | AWS region for your LISA deployment and Bedrock KB |
| `k` | Number of top results to evaluate (Precision@k, Recall@k, NDCG@k) |
| `documents` | Short name → filename mapping. Document keys referenced in golden dataset |
| `s3_bucket` | S3 bucket prefix. Combined with `documents` filenames to build full URIs |
| `api_url` | LISA API Gateway URL (find in CloudFormation outputs or AWS Console) |
| `deployment_name` | LISA deployment name used for authentication |
| `knowledge_base_id` | Bedrock Knowledge Base ID (find in Bedrock console) |

**Finding Your Values:**

- **API Gateway URL:** CloudFormation → Your LISA stack → Outputs → `RestApiUri` or `ApiUri`
- **Deployment Name:** The value you used for `deploymentName` in `config-custom.yaml`
- **Repository ID:** Check LISA UI → RAG Repositories, or via API: `GET /repository`
- **Knowledge Base ID:** AWS Console → Bedrock → Knowledge bases

### Single Backend Evaluation

You can evaluate just one backend by configuring only that section:

**OpenSearch Only:**
```yaml
backends:
  lisa_api:
    - name: "OpenSearch"
      # ... config
```

**Bedrock KB Only:**
```yaml
backends:
  bedrock_kb:
    - name: "Bedrock KB"
      # ... config
```

### Multiple Backends

Configure multiple backends to get a comparison report:

```yaml
backends:
  bedrock_kb:
    - name: "Bedrock KB"
      # ...

  lisa_api:
    - name: "OpenSearch"
      # ...
    - name: "PGVector"
      # ...
```

This generates individual reports plus a cross-backend comparison table.

## Golden Dataset Format

The golden dataset is a JSONL file (one JSON object per line) with your test queries and expected results.

### Entry Format

```json
{
  "query": "Your search query text",
  "expected": ["doc1", "doc2"],
  "relevance": {"doc1": 3, "doc2": 2},
  "type": "semantic"
}
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `query` | ✓ | The search query text |
| `expected` | ✓ | List of document keys that should be retrieved (from `documents` in config) |
| `relevance` | ✓ | Relevance scores for each expected document (1-3, where 3 = most relevant) |
| `type` | Optional | Query type for breakdown analysis (e.g., "semantic", "keyword", "exact") |

### Example Dataset

```jsonl
{"query": "How to optimize neural networks?", "expected": ["nn_paper", "opt_guide"], "relevance": {"nn_paper": 3, "opt_guide": 2}, "type": "semantic"}
{"query": "machine learning regularization techniques", "expected": ["regularization_paper"], "relevance": {"regularization_paper": 3}, "type": "keyword"}
{"query": "report.pdf", "expected": ["report"], "relevance": {"report": 3}, "type": "exact"}
```

### Best Practices

1. **Diverse Query Types:**
   - Semantic: Conceptual questions that require understanding meaning
   - Keyword: Direct keyword matches
   - Exact: Filename or precise phrase searches

2. **Relevance Scores:**
   - **3** = Highly relevant, directly answers the query
   - **2** = Moderately relevant, provides useful context
   - **1** = Marginally relevant, tangentially related

3. **Coverage:**
   - Test both common and edge-case queries
   - Include queries with 0, 1, and multiple expected documents
   - Cover different document types and topics

## Authentication

### LISA API Backends

Authentication uses **AWS Secrets Manager** for management keys:

1. Evaluation tool fetches management key from Secrets Manager using these patterns:
   - `{deployment_name}-lisa-management-key`
   - `{deployment_name}-management-key`
   - `lisa-{deployment_name}-management-key`

2. Token is registered in DynamoDB: `{deployment_name}-LISAApiBaseTokenTable`

3. Authenticated requests use both `Api-Key` and `Authorization` headers

**Required IAM Permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:*management-key*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem"
      ],
      "Resource": "arn:aws:dynamodb:REGION:ACCOUNT:table/*-LISAApiBaseTokenTable"
    }
  ]
}
```

### Bedrock Knowledge Bases

Uses standard AWS SDK authentication (boto3 default credential chain).

**Required IAM Permissions:**
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:Retrieve"
  ],
  "Resource": "arn:aws:bedrock:REGION:ACCOUNT:knowledge-base/*"
}
```

## Understanding Results

### Metrics Explained

**Precision@k:**
- Measures: What fraction of retrieved documents are relevant?
- Formula: (Relevant Retrieved) / k
- Range: 0.0 to 1.0 (higher is better)
- Example: If k=5 and 3 retrieved docs are relevant → Precision@5 = 0.6

**Recall@k:**
- Measures: What fraction of relevant documents were retrieved?
- Formula: (Relevant Retrieved) / (Total Relevant)
- Range: 0.0 to 1.0 (higher is better)
- Example: If 3 relevant docs exist and 2 were retrieved → Recall = 0.67

**NDCG@k (Normalized Discounted Cumulative Gain):**
- Measures: Ranking quality (relevant docs should rank higher)
- Penalizes relevant documents that appear lower in results
- Range: 0.0 to 1.0 (higher is better)
- Perfect score (1.0) = all relevant docs retrieved in order of relevance

### Sample Output

```
======================================================================
  OpenSearch — Evaluation Results (k=5)
======================================================================
  Precision@5:  0.742
  Recall@5:     0.856
  NDCG@5:       0.821

  By Query Type:
  Type         Count    P@5     R@5    NDCG@5
  ------------ ----- -------- -------- --------
  semantic        42    0.714    0.833    0.798
  keyword         15    0.800    0.900    0.867
  exact            8    0.775    0.875    0.845

  Per-Query Breakdown:
  Type       Query                                             P     R   NDCG  Retrieved
  ---------- ----------------------------------------------- ----- ----- ------  ------------------------------
  semantic   How to optimize neural networks?                1.00  1.00  1.00  nn_paper.pdf, opt_guide.pdf
  keyword    machine learning regularization                 0.80  0.80  0.92  regularization_paper.pdf, ...
  ...
```

### Cross-Backend Comparison

When evaluating multiple backends:

```
======================================================================
  Cross-Backend Comparison (k=5)
======================================================================
  Metric            OpenSearch    PGVector  Bedrock KB
  --------------- ------------ ------------ ------------
  precision@5            0.742        0.698        0.755
  recall@5               0.856        0.812        0.867
  ndcg@5                 0.821        0.784        0.835

  Pairwise Deltas:
  Comparison                       P@5     R@5    NDCG@5
  ---------------------------- -------- -------- --------
  PGVector vs OpenSearch          -0.044   -0.044   -0.037
  Bedrock KB vs OpenSearch        +0.013   +0.011   +0.014
  Bedrock KB vs PGVector          +0.057   +0.055   +0.051
```

## Troubleshooting

### Config Errors

**Error:** `FileNotFoundError`
- **Fix:** Use absolute paths or run from repo root

**Error:** `ValidationError: region field required`
- **Fix:** Ensure `region:` is set in your config file

**Error:** `ValidationError: documents field required`
- **Fix:** Must define at least one document in `documents:` section

### Runtime Errors

**Error:** `Repository not found`
- **Fix:** Verify `repo_id` matches an existing repository. List repos:
  ```bash
  curl -H "Authorization: YOUR_TOKEN" \
    https://YOUR-API-URL/repository
  ```

**Error:** `Bedrock knowledge base not found`
- **Fix:** Verify `knowledge_base_id` is correct. List KBs:
  ```bash
  aws bedrock-agent list-knowledge-bases
  ```

**Error:** `S3 object not found`
- **Fix:** Documents must exist at `{s3_bucket}/{filename}`. Verify with:
  ```bash
  aws s3 ls s3://your-bucket/ --recursive
  ```
