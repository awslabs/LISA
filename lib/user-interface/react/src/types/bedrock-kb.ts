/**
 Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

 Licensed under the Apache License, Version 2.0 (the "License").
 You may not use this file except in compliance with the License.
 You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 */

/**
 * Metadata for a Bedrock Knowledge Base
 */
export type KnowledgeBase = {
    knowledgeBaseId: string;
    name: string;
    description?: string;
    status: string;
    available?: boolean;
    unavailableReason?: string;
    createdAt?: string;
    updatedAt?: string;
};

/**
 * Metadata for a Bedrock Knowledge Base data source
 */
export type DataSource = {
    dataSourceId: string;
    name: string;
    description?: string;
    status: string;
    s3Bucket: string;
    s3Prefix?: string;
    createdAt?: string;
    updatedAt?: string;
    managed?: boolean;
    collectionId?: string;
};

/**
 * User selection of a data source for collection creation
 * Frontend sends this to backend, which creates pipelines and collections
 */
export type DataSourceSelection = {
    dataSourceId: string;
    dataSourceName: string;
    s3Bucket: string;
    s3Prefix?: string;
};

/**
 * Response from discovery API when listing Knowledge Bases
 */
export type DiscoverKnowledgeBasesResponse = {
    knowledgeBases: KnowledgeBase[];
    totalKnowledgeBases: number;
};

/**
 * Response from discovery API when listing data sources
 */
export type DiscoverDataSourcesResponse = {
    knowledgeBase: {
        id: string;
        name: string;
        status?: string;
        description?: string;
    };
    dataSources: DataSource[];
    totalDataSources?: number;
};

/**
 * Collection impact analysis for deletion
 */
export type CollectionImpactAnalysis = {
    collectionId: string;
    collectionName: string;
    documentCount: number;
    createdAt: string;
    lastModified: string;
    recentlyUsed: boolean;
};

/**
 * Helper function to generate a valid collection ID from a data source name
 */
export function generateCollectionId (dataSourceName: string): string {
    // Convert to lowercase
    let collectionId = dataSourceName.toLowerCase();

    // Replace spaces and underscores with hyphens
    collectionId = collectionId.replace(/[\s_]+/g, '-');

    // Remove invalid characters (keep only alphanumeric and hyphens)
    collectionId = collectionId.replace(/[^a-z0-9-]/g, '');

    // Remove leading/trailing hyphens and collapse multiple hyphens
    collectionId = collectionId
        .split('-')
        .filter((part) => part.length > 0)
        .join('-');

    // Ensure it's not empty
    if (!collectionId) {
        collectionId = 'collection';
    }

    return collectionId;
}

/**
 * Validate data source selection
 */
export function validateDataSourceSelection (selection: DataSourceSelection): string | null {
    if (!selection.dataSourceId) {
        return 'Data source ID is required';
    }
    if (!selection.s3Bucket) {
        return 'S3 bucket is required';
    }
    return null;
}
