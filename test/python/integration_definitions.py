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
optionally add its key to the corresponding deploy_* list.
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
        "monday":    {"startTime": "09:00", "stopTime": "18:00"},
        "tuesday":   {"startTime": "09:00", "stopTime": "18:00"},
        "wednesday": {"startTime": "09:00", "stopTime": "18:00"},
        "thursday":  {"startTime": "09:00", "stopTime": "18:00"},
        "friday":    {"startTime": "09:00", "stopTime": "18:00"},
    },
}

# ---------------------------------------------------------------------------
# Self-hosted textgen model definitions
# ---------------------------------------------------------------------------

MODEL_DEFINITIONS: dict[str, dict] = {
    "flan-t5-xxl": {
        "model_name": "google/flan-t5-xxl",
        "instance_type": "g5.xlarge",
        "blockDeviceVolumeSize": 80,
        "sharedMemorySize": 4096,
        "memoryReservation": 22000,
        "environment": {
            "VLLM_MAX_MODEL_LEN": "4096",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.90",
            "VLLM_MAX_NUM_BATCHED_TOKENS": "4096",
            "VLLM_MAX_NUM_SEQS": "64",
            "VLLM_ENABLE_PREFIX_CACHING": "true",
            "VLLM_ENABLE_CHUNKED_PREFILL": "true",
            "VLLM_DTYPE": "auto",
            "VLLM_TRUST_REMOTE_CODE": "true",
        },
    },
    "llama-2-7b-hf": {
        "model_name": "meta-llama/Llama-2-7b-hf",
        "instance_type": "g5.xlarge",
        "blockDeviceVolumeSize": 80,
        "sharedMemorySize": 4096,
        "memoryReservation": 22000,
        "environment": {
            "VLLM_MAX_MODEL_LEN": "32768",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.90",
            "VLLM_MAX_NUM_BATCHED_TOKENS": "8192",
            "VLLM_MAX_NUM_SEQS": "64",
            "VLLM_ENABLE_PREFIX_CACHING": "true",
            "VLLM_ENABLE_CHUNKED_PREFILL": "true",
            "VLLM_DTYPE": "auto",
            "VLLM_ROPE_SCALING": '{"type":"dynamic","factor":8.0}',
        },
    },
    "llama-3-2-3b-instruct": {
        "model_name": "meta-llama/Llama-3.2-3B-Instruct",
        "instance_type": "g5.xlarge",
        "blockDeviceVolumeSize": 80,
        "sharedMemorySize": 4096,
        "memoryReservation": 22000,
        "environment": {
            "VLLM_MAX_MODEL_LEN": "131072",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.90",
            "VLLM_MAX_NUM_BATCHED_TOKENS": "8192",
            "VLLM_MAX_NUM_SEQS": "32",
            "VLLM_ENABLE_PREFIX_CACHING": "true",
            "VLLM_ENABLE_CHUNKED_PREFILL": "true",
            "VLLM_DTYPE": "auto",
        },
    },
    "gpt-oss-120b": {
        "model_name": "openai/gpt-oss-120b",
        # Requires Hopper (H100/H200) for MXFP4 MoE kernels — p5.xlarge = 1x H100 80GB
        "instance_type": "g6.48xlarge",
        "blockDeviceVolumeSize": 200,
        "sharedMemorySize": 16384,
        "memoryReservation": 180000,
        "environment": {
            "VLLM_TENSOR_PARALLEL_SIZE": "8",
            "VLLM_MAX_MODEL_LEN": "8192",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.90",
            "VLLM_MAX_NUM_BATCHED_TOKENS": "8192",
            "VLLM_MAX_NUM_SEQS": "64",
            "VLLM_ENABLE_PREFIX_CACHING": "true",
            "VLLM_ENABLE_CHUNKED_PREFILL": "true",
            "VLLM_ASYNC_SCHEDULING": "true",
            "VLLM_MAX_PARALLEL_LOADING_WORKERS": "8",
        },
    },
    "gpt-oss-20b": {
        "model_name": "openai/gpt-oss-20b",
        # Requires Hopper (H100/H200) for MXFP4 MoE kernels — p5.xlarge = 1x H100 80GB
        # gptoss tag required: MXFP4 kernels were not in mainline until v0.11.0
        "instance_type": "g6.4xlarge",
        "blockDeviceVolumeSize": 100,
        "sharedMemorySize": 4096,
        "memoryReservation": 50000, # leaves ~136GB headroom
        "environment": {
            "VLLM_TENSOR_PARALLEL_SIZE": "4",
            "VLLM_MAX_MODEL_LEN": "32768",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.90",
            "VLLM_MAX_NUM_BATCHED_TOKENS": "8192",
            "VLLM_MAX_NUM_SEQS": "64",
            "VLLM_ENABLE_PREFIX_CACHING": "true",
            "VLLM_ENABLE_CHUNKED_PREFILL": "true",
            "VLLM_ASYNC_SCHEDULING": "true",
            "VLLM_MAX_PARALLEL_LOADING_WORKERS": "8",
        },
    },
    "granite-20b-code-base-8k": {
        "model_name": "ibm-granite/granite-20b-code-base-8k",
        "instance_type": "g5.12xlarge",
        "blockDeviceVolumeSize": 200,
        "sharedMemorySize": 16384,
        "memoryReservation": 180000,
        "environment": {
            "VLLM_MAX_MODEL_LEN": "8192",
            "VLLM_TENSOR_PARALLEL_SIZE": "4",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.90",
            "VLLM_MAX_NUM_BATCHED_TOKENS": "8192",
            "VLLM_MAX_NUM_SEQS": "64",
            "VLLM_ENABLE_PREFIX_CACHING": "true",
            "VLLM_ENABLE_CHUNKED_PREFILL": "true",
            "VLLM_DTYPE": "auto",
        },
    },
    "mistral-7b-v01": {
        "model_name": "mistralai/Mistral-7B-v0.1",
        "instance_type": "g5.xlarge",
        "blockDeviceVolumeSize": 80,
        "sharedMemorySize": 4096,
        "memoryReservation": 22000,
        "environment": {
            "VLLM_MAX_MODEL_LEN": "32768",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.90",
            "VLLM_MAX_NUM_BATCHED_TOKENS": "8192",
            "VLLM_MAX_NUM_SEQS": "64",
            "VLLM_ENABLE_PREFIX_CACHING": "true",
            "VLLM_ENABLE_CHUNKED_PREFILL": "true",
            "VLLM_DTYPE": "auto",
        },
    },
    "qwen2-vl-7b-instruct": {
        "model_name": "Qwen/Qwen2-VL-7B-Instruct",
        "instance_type": "g5.2xlarge",
        "blockDeviceVolumeSize": 100,
        "sharedMemorySize": 8192,
        "memoryReservation": 60000,
        "environment": {
            "VLLM_MAX_MODEL_LEN": "32768",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.88",
            "VLLM_MAX_NUM_BATCHED_TOKENS": "8192",
            "VLLM_MAX_NUM_SEQS": "32",
            "VLLM_ENABLE_PREFIX_CACHING": "true",
            "VLLM_ENABLE_CHUNKED_PREFILL": "true",
            "VLLM_DTYPE": "auto",
            "VLLM_TRUST_REMOTE_CODE": "true",
            "VLLM_LIMIT_MM_PER_PROMPT": "image=4",
        },
    },
}

# ---------------------------------------------------------------------------
# Self-hosted embedding model definitions
# ---------------------------------------------------------------------------

EMBEDDED_MODEL_DEFINITIONS: dict[str, dict] = {
    DEFAULT_EMBEDDING_MODEL_ID: {
        # e5-large-v2: BERT encoder, 512 token max, 1024-dim, mean pooling
        "model_name": "intfloat/e5-large-v2",
        "instance_type": "g5.xlarge",
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
        "model_name": "BAAI/bge-large-en-v1.5",
        "instance_type": "g5.xlarge",
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
        "model_name": "Qwen/Qwen3-Embedding-0.6B",
        "instance_type": "g5.xlarge",
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
        "model_name": "Qwen/Qwen3-Embedding-8B",
        "instance_type": "g5.2xlarge",
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
        "model_name": "bedrock/us.amazon.nova-micro-v1:0",
        "model_type": "textgen",
        "features": [
            {"name": "summarization", "overview": ""},
            {"name": "imageInput", "overview": ""},
            {"name": "toolCalls", "overview": ""},
        ],
    },
    "titan-embed": {
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
deploy_models: list[str] = [
    "flan-t5-xxl",
    "llama-2-7b-hf",
    "llama-3-2-3b-instruct",
    "gpt-oss-120b",
    "gpt-oss-20b",
    "granite-20b-code-base-8k",
    "mistral-7b-v01",
    "qwen2-vl-7b-instruct",
]

# Self-hosted embedding models to deploy (keys from EMBEDDED_MODEL_DEFINITIONS)
deploy_embedded_models: list[str] = [
    DEFAULT_EMBEDDING_MODEL_ID,
    "baai-embed-15",
    "qwen3-embed-06b",
    "qwen3-embed-8b",
]

# Bedrock models to deploy (keys from BEDROCK_MODEL_DEFINITIONS)
deploy_bedrock_models: list[str] = [
    "sonnet-46",
    "opus-46",
    "titan-embed",
    "nova-micro",
]

# Vector stores to deploy (keys from VECTOR_STORE_DEFINITIONS)
deploy_vector_stores: list[str] = [
    "pgv-rag",
    "os-rag",
    "bedrock-kb-rag",
]
