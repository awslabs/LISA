#!/usr/bin/env python3
#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Resource definitions and deploy lists for the LISA integration setup test.

To control what gets deployed, edit the deploy_* lists at the bottom of this file.
To add a new resource, add an entry to the appropriate *_DEFINITIONS dict and
optionally add its key to the corresponding deploy_* list. Feel free to use this as
an example for deploying models.
"""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_EMBEDDING_MODEL_ID = "e5-embed"
RAG_PIPELINE_BUCKET = "lisa-rag-pipeline"
BEDROCK_KB_S3_BUCKET = "bk-s3-test"

# ---------------------------------------------------------------------------
# Default auto-scaling schedule: Mon-Fri 09:00-18:00 America/Denver
# ---------------------------------------------------------------------------
DEFAULT_AUTOSCALING_SCHEDULE: dict = {
    "scheduleType": "DAILY",
    "timezone": "America/Denver",
    "scheduleEnabled": True,
    "dailySchedule": {
        "monday": {"startTime": "09:00", "stopTime": "18:00"},
        "tuesday": {"startTime": "09:00", "stopTime": "18:00"},
        "wednesday": {"startTime": "09:00", "stopTime": "18:00"},
        "thursday": {"startTime": "09:00", "stopTime": "18:00"},
        "friday": {"startTime": "09:00", "stopTime": "18:00"},
    },
}

# ---------------------------------------------------------------------------
# Self-hosted textgen model definitions
# ---------------------------------------------------------------------------

MODEL_DEFINITIONS: dict[str, dict] = {
    "llama-3-2-3b-instruct": {
        # g6.2xlarge: 1x NVIDIA L4 (24 GB GPU), 32 GiB system RAM
        # KV cache math: ~6 GB weights, ~18 GB remaining → ~85K token KV budget
        # 64K context with 16 seqs is the safe operating point on a single L4
        "description": (
            "Meta Llama-3.2 3B Instruct. Lightweight instruction-tuned model optimized for "
            "chat, summarization, and agentic tasks. Strong performance-per-dollar for its size; "
            "good default for low-latency or high-throughput workloads where a 7B+ model is overkill."
        ),
        "model_name": "meta-llama/Llama-3.2-3B-Instruct",
        "instance_type": "g6.2xlarge",
        "blockDeviceVolumeSize": 80,
        "sharedMemorySize": 2048,
        "memoryReservation": 29220,  # 32768 - 2048 shm - 1500 OS
        "environment": {
            "VLLM_MAX_MODEL_LEN": "65536",  # 64K — safe on 24 GB L4 with headroom
            "VLLM_MAX_NUM_SEQS": "16",
        },
    },
    "gpt-oss-120b": {
        "description": (
            "OpenAI GPT-OSS 120B. Large open-weight MoE model offering frontier-class reasoning, "
            "instruction following, and tool use. Best choice when maximum capability is needed "
            "for complex tasks, long-context reasoning, or agentic workflows."
        ),
        "model_name": "openai/gpt-oss-120b",
        # Requires Hopper (H100/H200) for MXFP4 MoE kernels — g6.48xlarge = 8x L4 24GB
        # MXFP4 not supported on L4, will use unquantized with tensor parallelism
        # Memory constrained: 120B unquantized ~240GB / 8 GPUs = ~30GB per 24GB GPU
        "instance_type": "g6.48xlarge",
        "blockDeviceVolumeSize": 200,
        "sharedMemorySize": 4096,
        "memoryReservation": 740000,  # 786432 - 4096 shm - 1500 OS
        "environment": {
            "VLLM_TENSOR_PARALLEL_SIZE": "8",
            "VLLM_USE_TQDM_ON_LOAD": "true",
            "VLLM_ASYNC_SCHEDULING": "true",
            "VLLM_MAX_PARALLEL_LOADING_WORKERS": "8",
            "VLLM_MAX_NUM_SEQS": "32",
        },
    },
    "gpt-oss-20b": {
        "description": (
            "OpenAI GPT-OSS 20B. Mid-size open-weight model balancing capability and cost. "
            "Good general-purpose chat, summarization, and reasoning on a single GPU. "
            "Useful when gpt-oss-120b is too expensive but llama-3-2-3b is insufficient."
        ),
        "model_name": "openai/gpt-oss-20b",
        # g6.4xlarge: 1x NVIDIA L4 (24 GB GPU), 64 GiB system RAM
        # gptoss tag required: MXFP4 kernels were not in mainline until v0.11.0
        "instance_type": "g6.4xlarge",
        "blockDeviceVolumeSize": 100,
        "sharedMemorySize": 2048,
        "memoryReservation": 61988,  # 65536 - 2048 shm - 1500 OS
        "environment": {
            # Single L4 GPU — tensor parallelism of 1
            "VLLM_TENSOR_PARALLEL_SIZE": "1",
            "VLLM_USE_TQDM_ON_LOAD": "true",
            "VLLM_ASYNC_SCHEDULING": "true",
            "VLLM_MAX_PARALLEL_LOADING_WORKERS": "1",
            "VLLM_MAX_NUM_SEQS": "32",
        },
    },
    "granite-20b-code-instruct-8k": {
        # g6.12xlarge: 4x L4 (24 GB each = 96 GB GPU), 192 GiB system RAM
        "description": (
            "IBM Granite 20B Code Instruct. Instruction-tuned decoder-only model for code "
            "generation, completion, explanation, and debugging across 116 programming languages. "
            "Includes chat template for use with /v1/chat/completions endpoint."
        ),
        "model_name": "ibm-granite/granite-20b-code-instruct-8k",
        "instance_type": "g6.12xlarge",
        "blockDeviceVolumeSize": 200,
        "sharedMemorySize": 4096,
        "memoryReservation": 180000,  # g6.12xlarge has ~186134 MiB available to ECS; reserve headroom for shm + agent
        "environment": {
            "VLLM_TENSOR_PARALLEL_SIZE": "4",  # matches 4x L4
            "VLLM_MAX_NUM_SEQS": "64",
            # Let vllm auto-detect max_model_len (native 8192)
        },
    },
    "mistral-7b-v03": {
        # g6.2xlarge: 1x L4 (24 GB GPU), 32 GiB system RAM
        "description": (
            "Mistral 7B Instruct v0.3. Instruction-tuned LLM competitive with Llama-2 13B at "
            "half the size. Good for chat, summarization, and instruction following tasks."
        ),
        "model_name": "mistralai/Mistral-7B-Instruct-v0.3",
        "instance_type": "g6.2xlarge",
        "blockDeviceVolumeSize": 80,
        "sharedMemorySize": 2048,
        "memoryReservation": 29220,  # 32768 - 2048 shm - 1500 OS
        "environment": {
            # Cap context to 16K to improve concurrency — full 32K leaves only 1.5x on 24 GB L4
            "VLLM_MAX_MODEL_LEN": "16384",
            "VLLM_MAX_NUM_SEQS": "64",
        },
    },
    "qwen2-vl-7b-instruct": {
        # g6.2xlarge: 1x L4 (24 GB GPU), 32 GiB system RAM
        "description": (
            "Qwen2-VL 7B Instruct. Multimodal vision-language model supporting image and video "
            "understanding alongside text. Excels at visual QA, document parsing, chart reading, "
            "and image captioning. Best choice when image input is required."
        ),
        "model_name": "Qwen/Qwen2-VL-7B-Instruct",
        "instance_type": "g6.2xlarge",
        "blockDeviceVolumeSize": 100,
        "sharedMemorySize": 2048,
        "memoryReservation": 29220,  # 32768 - 2048 shm - 1500 OS
        "environment": {
            # Qwen2-VL vision encoder (~1.5 GB) + LLM weights (~14 GB) leaves ~7 GB for KV cache
            # 8K context with 8 seqs is the safe operating point on a single 24 GB L4
            "VLLM_MAX_MODEL_LEN": "8192",
            "VLLM_MAX_NUM_SEQS": "8",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.90",
            "VLLM_TRUST_REMOTE_CODE": "true",
            "VLLM_LIMIT_MM_PER_PROMPT": "image=4",
        },
        "features": [
            {"name": "summarization", "overview": ""},
            {"name": "imageInput", "overview": ""},
            {"name": "reasoning", "overview": ""},
            {"name": "toolCalls", "overview": ""},
        ],
    },
}

# ---------------------------------------------------------------------------
# Self-hosted embedding model definitions
# ---------------------------------------------------------------------------

EMBEDDED_MODEL_DEFINITIONS: dict[str, dict] = {
    "e5-embed": {
        # e5-large-v2: BERT encoder, 512 token max, 1024-dim, mean pooling
        "description": (
            "intfloat E5-Large-v2. BERT-based dense retrieval model, 1024-dim embeddings. "
            "Strong general-purpose semantic search and RAG retrieval. Solid baseline for most "
            "English text similarity and document retrieval workloads."
        ),
        "model_name": "intfloat/e5-large-v2",
        "instance_type": "g6.xlarge",
        "environment": {
            "MAX_BATCH_TOKENS": "16384",
            "MAX_CONCURRENT_REQUESTS": "512",
            "MAX_CLIENT_BATCH_SIZE": "256",
            "POOLING": "mean",
            "AUTO_TRUNCATE": "true",
            "DTYPE": "float16",
        },
    },
    "baai-embed-15": {
        # bge-large-en-v1.5: BERT encoder, 512 token max, 1024-dim, cls pooling
        "description": (
            "BAAI BGE-Large-EN-v1.5. High-quality BERT-based embedding model, 1024-dim. "
            "Consistently top-ranked on MTEB English benchmarks. Excellent for semantic search, "
            "RAG retrieval, and reranking pipelines. Strong alternative to E5 with CLS pooling."
        ),
        "model_name": "BAAI/bge-large-en-v1.5",
        "instance_type": "g6.xlarge",
        "environment": {
            "MAX_BATCH_TOKENS": "16384",
            "MAX_CONCURRENT_REQUESTS": "512",
            "MAX_CLIENT_BATCH_SIZE": "256",
            "POOLING": "cls",
            "AUTO_TRUNCATE": "true",
            "DTYPE": "float16",
        },
    },
    "qwen3-embed-06b": {
        # Qwen3-Embedding-0.6B: decoder-based, 32K context, 1024-dim, last-token pooling
        "description": (
            "Qwen3-Embedding 0.6B. Lightweight decoder-based embedding model with 32K context "
            "window. Handles long documents that exceed BERT-based models' 512-token limit. "
            "Good cost-efficient option for long-context RAG and multilingual retrieval."
        ),
        "model_name": "Qwen/Qwen3-Embedding-0.6B",
        "instance_type": "g6.xlarge",
        "environment": {
            "MAX_BATCH_TOKENS": "32768",
            "MAX_CONCURRENT_REQUESTS": "512",
            "MAX_CLIENT_BATCH_SIZE": "256",
            "POOLING": "last-token",
            "AUTO_TRUNCATE": "true",
            "DTYPE": "float16",
        },
    },
    "qwen3-embed-8b": {
        # Qwen3-Embedding-8B: decoder-based, 32K context, 4096-dim, last-token pooling
        "description": (
            "Qwen3-Embedding 8B. High-capacity decoder-based embedding model with 32K context "
            "and 4096-dim output. Top-tier retrieval quality for long documents and multilingual "
            "content. Best choice when embedding quality matters more than cost."
        ),
        "model_name": "Qwen/Qwen3-Embedding-8B",
        "instance_type": "g6.2xlarge",
        "environment": {
            "MAX_BATCH_TOKENS": "32768",
            "MAX_CONCURRENT_REQUESTS": "256",
            "MAX_CLIENT_BATCH_SIZE": "128",
            "POOLING": "last-token",
            "AUTO_TRUNCATE": "true",
            "DTYPE": "float16",
        },
    },
}

# ---------------------------------------------------------------------------
# Bedrock model definitions
# ---------------------------------------------------------------------------

BEDROCK_MODEL_DEFINITIONS: dict[str, dict] = {
    "sonnet-46": {
        "description": (
            "Anthropic Claude Sonnet 4.6. Balanced frontier model with strong reasoning, tool use, "
            "image input, and long-context handling. Best general-purpose Bedrock option for most "
            "production workloads — good capability-to-cost ratio."
        ),
        "model_name": "bedrock/us.anthropic.claude-sonnet-4-6",
        "model_type": "textgen",
        "features": [
            {"name": "summarization", "overview": ""},
            {"name": "imageInput", "overview": ""},
            {"name": "reasoning", "overview": ""},
            {"name": "toolCalls", "overview": ""},
        ],
    },
    "opus-46": {
        "description": (
            "Anthropic Claude Opus 4.6. Highest-capability Claude model with advanced reasoning, "
            "extended thinking, and complex agentic task handling. Use when Sonnet is insufficient "
            "for multi-step reasoning or highly complex instructions."
        ),
        "model_name": "bedrock/us.anthropic.claude-opus-4-6-v1",
        "model_type": "textgen",
        "features": [
            {"name": "summarization", "overview": ""},
            {"name": "imageInput", "overview": ""},
            {"name": "reasoning", "overview": ""},
            {"name": "toolCalls", "overview": ""},
        ],
    },
    "nova-micro": {
        "description": (
            "Amazon Nova Micro. Ultra-low-latency text-only model optimized for speed and cost. "
            "Best for high-volume, simple tasks: classification, extraction, short summarization, "
            "and routing. Not suited for complex reasoning or image input."
        ),
        "model_name": "bedrock/us.amazon.nova-micro-v1:0",
        "model_type": "textgen",
        "features": [
            {"name": "summarization", "overview": ""},
            {"name": "imageInput", "overview": ""},
            {"name": "toolCalls", "overview": ""},
        ],
    },
    "titan-embed": {
        "description": (
            "Amazon Titan Text Embeddings v2. AWS-native embedding model with 1024-dim output "
            "and up to 8K token context. Good default for Bedrock-native RAG pipelines; no "
            "self-hosted infrastructure required."
        ),
        "model_name": "bedrock/amazon.titan-embed-text-v2:0",
        "model_type": "embedding",
        "features": [],
    },
}

# ---------------------------------------------------------------------------
# Vector store definitions
# ---------------------------------------------------------------------------

VECTOR_STORE_DEFINITIONS: dict[str, dict] = {
    "pgv-rag": {
        "description": (
            "PostgreSQL pgvector. Self-hosted relational vector store running on RDS. Best for "
            "teams already using PostgreSQL — supports hybrid SQL+vector queries, ACID transactions, "
            "and familiar tooling. Good default for most RAG workloads with moderate scale."
        ),
        "type": "pgvector",
        "config": {
            "pipelines": [
                {
                    "s3Prefix": "",
                    "trigger": "event",
                    "autoRemove": True,
                    "metadata": {"tags": ["test"]},
                    "chunkingStrategy": {"type": "fixed", "size": 1000, "overlap": 51},
                    "collectionId": "default",
                    "s3Bucket": RAG_PIPELINE_BUCKET,
                }
            ],
            "allowedGroups": [],
            "rdsConfig": {"username": "postgres", "dbName": "postgres", "dbPort": 5432},
        },
    },
    "os-rag": {
        "description": (
            "Amazon OpenSearch. Managed distributed search and vector store. Best for large-scale "
            "RAG with high query throughput, full-text + vector hybrid search, or when you need "
            "multi-AZ HA out of the box. Higher operational cost than pgvector at small scale."
        ),
        "type": "opensearch",
        "config": {
            "allowedGroups": [],
            "pipelines": [
                {
                    "s3Prefix": "",
                    "trigger": "event",
                    "autoRemove": True,
                    "metadata": {"tags": ["test"]},
                    "chunkingStrategy": {"type": "fixed", "size": 1000, "overlap": 51},
                    "collectionId": "default",
                    "s3Bucket": RAG_PIPELINE_BUCKET,
                }
            ],
            "opensearchConfig": {
                "dataNodes": 2,
                "dataNodeInstanceType": "r7g.large.search",
                "masterNodes": 0,
                "masterNodeInstanceType": "r7g.large.search",
                "volumeSize": 20,
                "volumeType": "gp3",
                "multiAzWithStandby": False,
            },
        },
    },
    "bedrock-kb-rag": {
        "description": (
            "Amazon Bedrock Knowledge Base. Fully managed serverless RAG pipeline — no vector "
            "store infrastructure to operate. Best when minimizing ops overhead is the priority "
            "or when integrating tightly with other Bedrock services. Less flexible than "
            "self-hosted options for custom chunking or retrieval logic."
        ),
        "type": "bedrock_knowledge_base",
        # knowledgeBaseId and dataSources are resolved at runtime after KB creation
        "config": {
            "allowedGroups": [],
        },
        # Controls whether to create the underlying Bedrock KB infrastructure
        "create_bedrock_kb": True,
        "bedrock_kb_options": {
            "kb_name": "bedrock-kb-e2e-test",
            "s3_bucket_name": BEDROCK_KB_S3_BUCKET,
        },
    },
}

# ---------------------------------------------------------------------------
# Deploy lists — edit these to control what gets deployed
# ---------------------------------------------------------------------------

# Self-hosted textgen models to deploy (keys from MODEL_DEFINITIONS)
# Ordered by general usefulness: frontier first, then mid-size, specialized, legacy base models
deploy_models: list[str] = [
    "gpt-oss-120b",  # frontier capability, complex reasoning & agentic tasks
    "gpt-oss-20b",  # mid-size general purpose, good cost/capability balance
    "qwen2-vl-7b-instruct",  # multimodal — only option for image input
    "llama-3-2-3b-instruct",  # lightweight instruct, low-latency / high-throughput
    "granite-20b-code-instruct-8k",  # specialized: code generation and completion
    "mistral-7b-v03",  # base model, fine-tuning or completion tasks
]

# Self-hosted embedding models to deploy (keys from EMBEDDED_MODEL_DEFINITIONS)
# Ordered by general usefulness: quality first, then cost-efficient alternatives
deploy_embedded_models: list[str] = [
    # "baai-embed-15",  # top MTEB quality, best for semantic search & RAG
    "e5-embed",  # solid general-purpose baseline (e5-large-v2)
    # "qwen3-embed-8b",  # highest quality for long-doc / multilingual retrieval
    # "qwen3-embed-06b",  # cost-efficient long-context alternative
]

# Bedrock models to deploy (keys from BEDROCK_MODEL_DEFINITIONS)
# Ordered by general usefulness: balanced first, then max capability, then cost-optimized
deploy_bedrock_models: list[str] = [
    # "sonnet-46",  # best general-purpose: reasoning, tools, image input
    # "opus-46",  # max capability for complex multi-step tasks
    # "nova-micro",  # ultra-low latency for high-volume simple tasks
    # "titan-embed",  # Bedrock-native embeddings, no self-hosted infra needed
]

# Vector stores to deploy (keys from VECTOR_STORE_DEFINITIONS)
deploy_vector_stores: list[str] = [
    # "pgv-rag",
    # "os-rag",
    # "bedrock-kb-rag",
]
