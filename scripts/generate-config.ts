/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';
import YAML from 'yaml';

// ============================================================================
// Interfaces
// ============================================================================

interface ValidationResult {
    isValid: boolean;
    error?: string;
}

interface BooleanValidationResult {
    isValid: boolean;
    value?: boolean;
}

type AwsPartition = 'aws' | 'aws-cn' | 'aws-us-gov' | 'aws-iso' | 'aws-iso-b' | 'aws-iso-e' | 'aws-iso-f';

interface CoreConfig {
    accountNumber: string;
    region: string;
    partition: AwsPartition;
    deploymentStage: string;
    deploymentName: string;
    s3BucketModels: string;
}

interface AuthConfig {
    authority: string;
    clientId: string;
    adminGroup?: string;
    jwtGroupsProperty?: string;
}

interface ApiGatewayConfig {
    domainName: string;
}

interface RestApiConfig {
    sslCertIamArn?: string;
    domainName?: string;
    imageConfig?: ImageConfig;
}

interface ImageConfig {
    type: 'ecr';
    repositoryArn: string;
    tag: string;
}

interface McpWorkbenchConfig {
    imageConfig: ImageConfig;
}

interface BatchIngestionConfig {
    imageConfig: ImageConfig;
}

interface LambdaLayerAssets {
    authorizerLayerPath: string;
    commonLayerPath: string;
    fastapiLayerPath: string;
    ragLayerPath: string;
    sdkLayerPath: string;
}

interface PrebuiltAssetsConfig {
    lambdaLayerAssets: LambdaLayerAssets;
    lambdaPath: string;
    webAppAssetsPath: string;
    documentsPath: string;
    ecsModelDeployerPath: string;
    vectorStoreDeployerPath: string;
    certificateAuthorityBundle: string;
    restApiImageConfig: ImageConfig;
    mcpWorkbenchImageConfig: ImageConfig;
    batchIngestionImageConfig: ImageConfig;
}

interface FeatureFlags {
    deployChat: boolean;
    deployMetrics: boolean;
    deployMcpWorkbench: boolean;
    deployRag: boolean;
    deployDocs: boolean;
    deployUi: boolean;
    deployMcp: boolean;
    deployServe: boolean;
}

type InferenceContainer = 'vllm' | 'tei' | 'tgi';

interface EcsModel {
    modelName: string;
    baseImage: string;
    inferenceContainer: InferenceContainer;
}

interface LisaConfig {
    accountNumber: string;
    region: string;
    partition: AwsPartition;
    deploymentStage: string;
    deploymentName: string;
    s3BucketModels: string;
    ragRepositories: unknown[];
    ecsModels: EcsModel[];
    authConfig?: AuthConfig;
    apiGatewayConfig?: ApiGatewayConfig;
    restApiConfig?: RestApiConfig;
    mcpWorkbenchConfig?: McpWorkbenchConfig;
    batchIngestionConfig?: BatchIngestionConfig;
    lambdaLayerAssets?: LambdaLayerAssets;
    lambdaPath?: string;
    webAppAssetsPath?: string;
    documentsPath?: string;
    ecsModelDeployerPath?: string;
    vectorStoreDeployerPath?: string;
    certificateAuthorityBundle?: string;
    deployChat: boolean;
    deployMetrics: boolean;
    deployMcpWorkbench: boolean;
    deployRag: boolean;
    deployDocs: boolean;
    deployUi: boolean;
    deployMcp: boolean;
    deployServe: boolean;
}

// ============================================================================
// Constants
// ============================================================================

const PREBUILT_ASSETS_BASE = './dist/layers';

const VALID_REGIONS = new Set([
    'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
    'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 'eu-north-1', "eu-isoe-west-1",
    'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
    'ap-southeast-1', 'ap-southeast-2', 'ap-south-1',
    'sa-east-1', 'ca-central-1',
    'me-south-1', 'af-south-1',
    'us-gov-west-1', 'us-gov-east-1',
    'us-iso-east-1', 'us-isob-east-1', 'us-isof-sout-1'
]);

const VALID_INFERENCE_CONTAINERS: InferenceContainer[] = ['vllm', 'tei', 'tgi'];

const VALID_PARTITIONS: AwsPartition[] = ['aws', 'aws-cn', 'aws-us-gov', 'aws-iso', 'aws-iso-b', 'aws-iso-e', 'aws-iso-f'];

const DEFAULT_BASE_IMAGES: Record<InferenceContainer, string> = {
    vllm: 'vllm/vllm-openai:latest',
    tei: 'ghcr.io/huggingface/text-embeddings-inference:latest',
    tgi: 'ghcr.io/huggingface/text-generation-inference:latest',
};


// ============================================================================
// Input Validator
// ============================================================================

class DefaultInputValidator {
    validateAccountNumber(value: string): ValidationResult {
        const cleaned = value.trim();
        if (!/^\d+$/.test(cleaned)) {
            return { isValid: false, error: 'Account number must contain only digits' };
        }
        if (cleaned.length !== 12) {
            return { isValid: false, error: `Account number must be exactly 12 digits, got ${cleaned.length}` };
        }
        return { isValid: true };
    }

    validateRegion(value: string): ValidationResult {
        const cleaned = value.trim().toLowerCase();
        if (VALID_REGIONS.has(cleaned)) {
            return { isValid: true };
        }
        // Allow region-like patterns for future regions
        if (/^[a-z]{2}(-[a-z]+)?-[a-z]+-\d+$/.test(cleaned)) {
            return { isValid: true };
        }
        return { isValid: false, error: `'${value}' is not a recognized AWS region` };
    }

    validateNonEmpty(value: string, fieldName: string): ValidationResult {
        if (!value.trim()) {
            return { isValid: false, error: `${fieldName} cannot be empty` };
        }
        return { isValid: true };
    }

    validateBooleanInput(value: string): BooleanValidationResult {
        const cleaned = value.trim().toLowerCase();
        if (['yes', 'y', 'true', '1'].includes(cleaned)) {
            return { isValid: true, value: true };
        }
        if (['no', 'n', 'false', '0'].includes(cleaned)) {
            return { isValid: true, value: false };
        }
        return { isValid: false };
    }

    validateInferenceContainer(value: string): ValidationResult {
        const cleaned = value.trim().toLowerCase() as InferenceContainer;
        if (VALID_INFERENCE_CONTAINERS.includes(cleaned)) {
            return { isValid: true };
        }
        return {
            isValid: false,
            error: `Invalid inference container. Must be one of: ${VALID_INFERENCE_CONTAINERS.join(', ')}`,
        };
    }

    validatePartition(value: string): ValidationResult {
        const cleaned = value.trim().toLowerCase() as AwsPartition;
        if (VALID_PARTITIONS.includes(cleaned)) {
            return { isValid: true };
        }
        return {
            isValid: false,
            error: `Invalid partition. Must be one of: ${VALID_PARTITIONS.join(', ')}`,
        };
    }
}


// ============================================================================
// Config Builder
// ============================================================================

class ConfigBuilder {
    private core?: CoreConfig;
    private auth?: AuthConfig;
    private apiGateway?: ApiGatewayConfig;
    private restApi?: RestApiConfig;
    private prebuiltAssets?: PrebuiltAssetsConfig;
    private ecsModels: EcsModel[] = [];
    private featureFlags: FeatureFlags = {
        deployChat: true,
        deployMetrics: true,
        deployMcpWorkbench: true,
        deployRag: true,
        deployDocs: true,
        deployUi: true,
        deployMcp: true,
        deployServe: true,
    };

    setCoreConfig(config: CoreConfig): this {
        this.core = config;
        return this;
    }

    setAuthConfig(config: AuthConfig | undefined): this {
        this.auth = config;
        return this;
    }

    setApiGatewayConfig(config: ApiGatewayConfig | undefined): this {
        this.apiGateway = config;
        return this;
    }

    setRestApiConfig(config: RestApiConfig | undefined): this {
        this.restApi = config;
        return this;
    }

    setPrebuiltAssets(usePrebuilt: boolean, partition?: AwsPartition, region?: string, accountNumber?: string): this {
        if (usePrebuilt && partition && region && accountNumber) {
            this.prebuiltAssets = this.createPrebuiltAssetsConfig(partition, region, accountNumber);
        } else {
            this.prebuiltAssets = undefined;
        }
        return this;
    }

    setEcsModels(models: EcsModel[]): this {
        this.ecsModels = models;
        return this;
    }

    setFeatureFlags(flags: FeatureFlags): this {
        this.featureFlags = flags;
        return this;
    }

    private createImageConfig(partition: AwsPartition, region: string, accountNumber: string, repositoryName: string): ImageConfig {
        return {
            type: 'ecr',
            repositoryArn: `arn:${partition}:ecr:${region}:${accountNumber}:repository/${repositoryName}`,
            tag: 'latest',
        };
    }

    private createPrebuiltAssetsConfig(partition: AwsPartition, region: string, accountNumber: string): PrebuiltAssetsConfig {
        const base = PREBUILT_ASSETS_BASE;
        return {
            lambdaLayerAssets: {
                authorizerLayerPath: `${base}/layers/AimlAdcLisaAuthLayer.zip`,
                commonLayerPath: `${base}/layers/AimlAdcLisaCommonLayer.zip`,
                fastapiLayerPath: `${base}/layers/AimlAdcLisaFastApiLayer.zip`,
                ragLayerPath: `${base}/layers/AimlAdcLisaRag.zip`,
                sdkLayerPath: `${base}/layers/AimlAdcLisaSdk.zip`,
            },
            lambdaPath: `${base}/layers/AimlAdcLisaLambda.zip`,
            webAppAssetsPath: `${base}/lisa-web`,
            documentsPath: `${base}/docs`,
            ecsModelDeployerPath: `${base}/ecs_model_deployer`,
            vectorStoreDeployerPath: `${base}/vector_store_deployer`,
            certificateAuthorityBundle: '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem',
            restApiImageConfig: this.createImageConfig(partition, region, accountNumber, 'lisa-rest-api'),
            mcpWorkbenchImageConfig: this.createImageConfig(partition, region, accountNumber, 'lisa-mcp-workbench'),
            batchIngestionImageConfig: this.createImageConfig(partition, region, accountNumber, 'lisa-batch-ingestion'),
        };
    }

    build(): LisaConfig {
        if (!this.core) {
            throw new Error('Core configuration is required');
        }

        const config: LisaConfig = {
            accountNumber: this.core.accountNumber,
            region: this.core.region,
            partition: this.core.partition,
            deploymentStage: this.core.deploymentStage,
            deploymentName: this.core.deploymentName,
            s3BucketModels: this.core.s3BucketModels,
            ragRepositories: [],
            ecsModels: this.ecsModels,
            ...this.featureFlags,
        };

        if (this.auth) {
            config.authConfig = { ...this.auth };
        }

        if (this.apiGateway) {
            config.apiGatewayConfig = { ...this.apiGateway };
        }

        if (this.restApi && (this.restApi.sslCertIamArn || this.restApi.domainName)) {
            config.restApiConfig = { ...this.restApi };
        }

        if (this.prebuiltAssets) {
            config.lambdaLayerAssets = this.prebuiltAssets.lambdaLayerAssets;
            config.lambdaPath = this.prebuiltAssets.lambdaPath;
            config.webAppAssetsPath = this.prebuiltAssets.webAppAssetsPath;
            config.documentsPath = this.prebuiltAssets.documentsPath;
            config.ecsModelDeployerPath = this.prebuiltAssets.ecsModelDeployerPath;
            config.vectorStoreDeployerPath = this.prebuiltAssets.vectorStoreDeployerPath;
            config.certificateAuthorityBundle = this.prebuiltAssets.certificateAuthorityBundle;

            // Add image configs - merge with existing restApiConfig if present
            config.restApiConfig = {
                ...config.restApiConfig,
                imageConfig: this.prebuiltAssets.restApiImageConfig,
            };
            config.mcpWorkbenchConfig = {
                imageConfig: this.prebuiltAssets.mcpWorkbenchImageConfig,
            };
            config.batchIngestionConfig = {
                imageConfig: this.prebuiltAssets.batchIngestionImageConfig,
            };
        }

        return config;
    }
}


// ============================================================================
// YAML Serializer
// ============================================================================

class YAMLSerializer {
    serialize(config: Record<string, unknown>): string {
        return YAML.stringify(config, {
            indent: 2,
        });
    }

    deserialize(yamlContent: string): Record<string, unknown> {
        return YAML.parse(yamlContent) ?? {};
    }
}


// ============================================================================
// Config File Handler
// ============================================================================

class ConfigFileHandler {
    private static readonly DEFAULT_CONFIG_FILE = 'config-custom.yaml';
    private static readonly GENERATED_CONFIG_FILE = 'config-generated.yaml';
    private serializer: YAMLSerializer;

    constructor(private basePath: string = process.cwd()) {
        this.serializer = new YAMLSerializer();
    }

    configExists(): boolean {
        return fs.existsSync(path.join(this.basePath, ConfigFileHandler.DEFAULT_CONFIG_FILE));
    }

    getOutputPath(createNew: boolean): string {
        if (createNew && this.configExists()) {
            return path.join(this.basePath, ConfigFileHandler.GENERATED_CONFIG_FILE);
        }
        return path.join(this.basePath, ConfigFileHandler.DEFAULT_CONFIG_FILE);
    }

    getOutputFileName(createNew: boolean): string {
        if (createNew && this.configExists()) {
            return ConfigFileHandler.GENERATED_CONFIG_FILE;
        }
        return ConfigFileHandler.DEFAULT_CONFIG_FILE;
    }

    loadExistingConfig(): Record<string, unknown> {
        const configPath = path.join(this.basePath, ConfigFileHandler.DEFAULT_CONFIG_FILE);
        if (!fs.existsSync(configPath)) {
            return {};
        }
        const content = fs.readFileSync(configPath, 'utf-8');
        return this.serializer.deserialize(content);
    }

    mergeConfigs(
        existing: Record<string, unknown>,
        newConfig: Record<string, unknown>
    ): Record<string, unknown> {
        return { ...existing, ...newConfig };
    }

    writeConfig(config: Record<string, unknown>, outputPath: string): void {
        const yamlContent = this.serializer.serialize(config);
        fs.writeFileSync(outputPath, yamlContent, 'utf-8');
    }
}


// ============================================================================
// Config Prompter
// ============================================================================

class ConfigPrompter {
    private rl: readline.Interface;
    private validator: DefaultInputValidator;

    constructor(validator: DefaultInputValidator) {
        this.validator = validator;
        this.rl = readline.createInterface({ input, output });
    }

    async close(): Promise<void> {
        this.rl.close();
    }

    async promptWithValidation(
        prompt: string,
        validate: (value: string) => ValidationResult,
        defaultValue?: string
    ): Promise<string> {
        while (true) {
            const displayPrompt = defaultValue ? `${prompt} [${defaultValue}]: ` : `${prompt}: `;
            const answer = await this.rl.question(displayPrompt);
            const value = answer.trim() || defaultValue || '';

            const result = validate(value);
            if (result.isValid) {
                return value;
            }
            console.log(`Error: ${result.error}`);
        }
    }

    async promptYesNo(prompt: string, defaultValue = true): Promise<boolean> {
        const defaultStr = defaultValue ? 'Y/n' : 'y/N';
        while (true) {
            const answer = await this.rl.question(`${prompt} [${defaultStr}]: `);
            if (!answer.trim()) {
                return defaultValue;
            }
            const result = this.validator.validateBooleanInput(answer);
            if (result.isValid && result.value !== undefined) {
                return result.value;
            }
            console.log('Please enter yes/no or y/n');
        }
    }

    async promptCoreConfig(): Promise<CoreConfig> {
        console.log('\n📋 Core Configuration\n');

        const accountNumber = await this.promptWithValidation(
            'AWS Account Number (12 digits)',
            (v) => this.validator.validateAccountNumber(v)
        );
        const region = await this.promptWithValidation(
            'AWS Region',
            (v) => this.validator.validateRegion(v)
        );
        console.log('\nPartition options: aws, aws-cn, aws-gov, aws-iso, aws-iso-b, aws-iso-f');
        const partition = await this.promptWithValidation(
            'AWS Partition',
            (v) => this.validator.validatePartition(v),
            'aws'
        ) as AwsPartition;
        const deploymentStage = await this.promptWithValidation(
            'Deployment Stage',
            (v) => this.validator.validateNonEmpty(v, 'Deployment stage'),
            'prod'
        );
        const deploymentName = await this.promptWithValidation(
            'Deployment Name',
            (v) => this.validator.validateNonEmpty(v, 'Deployment name'),
            'prod'
        );
        const s3BucketModels = await this.promptWithValidation(
            'S3 Bucket for Models',
            (v) => this.validator.validateNonEmpty(v, 'S3 bucket')
        );

        return {
            accountNumber,
            region,
            partition,
            deploymentStage,
            deploymentName,
            s3BucketModels,
        };
    }

    async promptPrebuiltAssets(): Promise<boolean> {
        console.log('\n📦 Prebuilt Assets\n');
        return await this.promptYesNo('Use prebuilt assets from @awslabs/lisa?', true);
    }

    async promptAuthConfig(): Promise<AuthConfig | undefined> {
        console.log('\n🔐 Authentication Configuration\n');

        const configure = await this.promptYesNo('Configure Authentication?', false);
        if (!configure) {
            return undefined;
        }

        const authority = await this.promptWithValidation(
            'OIDC Authority URL',
            (v) => this.validator.validateNonEmpty(v, 'Authority URL')
        );
        const clientId = await this.promptWithValidation(
            'Client ID',
            (v) => this.validator.validateNonEmpty(v, 'Client ID')
        );
        const adminGroup = (await this.rl.question('Admin Group Name (optional): ')).trim() || undefined;
        const jwtGroupsProperty = (await this.rl.question('JWT Groups Property (optional): ')).trim() || undefined;

        return { authority, clientId, adminGroup, jwtGroupsProperty };
    }

    async promptApiGatewayConfig(): Promise<ApiGatewayConfig | undefined> {
        console.log('\n🌐 API Gateway Configuration\n');

        const configure = await this.promptYesNo('Configure API Gateway custom domain?', false);
        if (!configure) {
            return undefined;
        }

        const domainName = await this.promptWithValidation(
            'API Gateway Domain Name',
            (v) => this.validator.validateNonEmpty(v, 'Domain name')
        );

        return { domainName };
    }

    async promptRestApiConfig(): Promise<RestApiConfig | undefined> {
        console.log('\n🔧 REST API Configuration\n');

        const configure = await this.promptYesNo('Configure REST API settings?', false);
        if (!configure) {
            return undefined;
        }

        const sslCertIamArn = (await this.rl.question('SSL Certificate IAM ARN (optional): ')).trim() || undefined;
        const domainName = (await this.rl.question('REST API Domain Name (optional): ')).trim() || undefined;

        if (!sslCertIamArn && !domainName) {
            return undefined;
        }

        return { sslCertIamArn, domainName };
    }

    async promptFeatureFlags(): Promise<FeatureFlags> {
        console.log('\n🚀 Feature Deployment Flags\n');

        const useDefaults = await this.promptYesNo('Use default feature flags (all enabled)?', true);
        if (useDefaults) {
            return {
                deployChat: true,
                deployMetrics: true,
                deployMcpWorkbench: true,
                deployRag: true,
                deployDocs: true,
                deployUi: true,
                deployMcp: true,
                deployServe: true,
            };
        }

        return {
            deployChat: await this.promptYesNo('Deploy Chat?'),
            deployMetrics: await this.promptYesNo('Deploy Metrics?'),
            deployMcpWorkbench: await this.promptYesNo('Deploy MCP Workbench?'),
            deployRag: await this.promptYesNo('Deploy RAG?'),
            deployDocs: await this.promptYesNo('Deploy Docs?'),
            deployUi: await this.promptYesNo('Deploy UI?'),
            deployMcp: await this.promptYesNo('Deploy MCP?'),
            deployServe: await this.promptYesNo('Deploy Serve?'),
        };
    }

    async promptEcsModels(s3BucketModels: string): Promise<EcsModel[]> {
        console.log('\n🤖 ECS Model Configuration\n');
        console.log(`Models will be deployed from S3 bucket: ${s3BucketModels}`);
        console.log('The model name corresponds to the path in S3 where the model is stored.');
        console.log('Example: "openai/gpt-oss-20b" means s3://' + s3BucketModels + '/openai/gpt-oss-20b\n');

        const addModels = await this.promptYesNo('Would you like to add ECS models?', false);
        if (!addModels) {
            return [];
        }

        const models: EcsModel[] = [];
        let addMore = true;

        while (addMore) {
            console.log(`\n--- Model ${models.length + 1} ---`);

            const modelName = await this.promptWithValidation(
                'Model name (S3 path, e.g., openai/gpt-oss-20b)',
                (v) => this.validator.validateNonEmpty(v, 'Model name')
            );

            console.log('\nInference container options: vllm, tei, tgi');
            const inferenceContainer = await this.promptWithValidation(
                'Inference container type',
                (v) => this.validator.validateInferenceContainer(v),
                'vllm'
            ) as InferenceContainer;

            const defaultImage = DEFAULT_BASE_IMAGES[inferenceContainer];
            const baseImage = await this.promptWithValidation(
                `Base image`,
                (v) => this.validator.validateNonEmpty(v, 'Base image'),
                defaultImage
            );

            models.push({
                modelName,
                baseImage,
                inferenceContainer,
            });

            console.log(`\n✓ Added model: ${modelName} (${inferenceContainer})`);
            addMore = await this.promptYesNo('\nAdd another model?', false);
        }

        return models;
    }

    async promptFileHandling(configExists: boolean): Promise<boolean> {
        if (!configExists) {
            return false; // Will create config-custom.yaml
        }

        console.log('\n📁 File Handling\n');
        console.log('An existing config-custom.yaml was found.');

        const createNew = await this.promptYesNo('Create new config-generated.yaml instead of merging?', false);
        return createNew;
    }
}

// ============================================================================
// Main Entry Point
// ============================================================================

async function main(): Promise<void> {
    console.log('╔════════════════════════════════════════════════════════════════╗');
    console.log('║           LISA Configuration Generator                         ║');
    console.log('║   Generate a config-custom.yaml for LISA deployment            ║');
    console.log('╚════════════════════════════════════════════════════════════════╝');

    const validator = new DefaultInputValidator();
    const builder = new ConfigBuilder();
    const fileHandler = new ConfigFileHandler();
    const prompter = new ConfigPrompter(validator);

    try {
        // Check for existing config and determine file handling
        const configExists = fileHandler.configExists();
        const createNew = await prompter.promptFileHandling(configExists);

        // Collect configuration through prompts
        const coreConfig = await prompter.promptCoreConfig();
        const usePrebuiltAssets = await prompter.promptPrebuiltAssets();
        const authConfig = await prompter.promptAuthConfig();
        const apiGatewayConfig = await prompter.promptApiGatewayConfig();
        const restApiConfig = await prompter.promptRestApiConfig();
        const featureFlags = await prompter.promptFeatureFlags();
        const ecsModels = await prompter.promptEcsModels(coreConfig.s3BucketModels);

        // Build the configuration
        builder
            .setCoreConfig(coreConfig)
            .setPrebuiltAssets(usePrebuiltAssets, coreConfig.partition, coreConfig.region, coreConfig.accountNumber)
            .setAuthConfig(authConfig)
            .setApiGatewayConfig(apiGatewayConfig)
            .setRestApiConfig(restApiConfig)
            .setFeatureFlags(featureFlags)
            .setEcsModels(ecsModels);

        const newConfig = builder.build() as unknown as Record<string, unknown>;

        // Determine final config (merge or new)
        let finalConfig: Record<string, unknown>;
        if (configExists && !createNew) {
            const existingConfig = fileHandler.loadExistingConfig();
            finalConfig = fileHandler.mergeConfigs(existingConfig, newConfig);
        } else {
            finalConfig = newConfig;
        }

        // Write the configuration
        const outputPath = fileHandler.getOutputPath(createNew);
        const outputFileName = fileHandler.getOutputFileName(createNew);
        fileHandler.writeConfig(finalConfig, outputPath);

        console.log('\n✅ Configuration generated successfully!');
        console.log(`📄 Output file: ${outputFileName}`);

        if (configExists && !createNew) {
            console.log('ℹ️  Merged with existing configuration');
        }
    } catch (error) {
        if (error instanceof Error) {
            console.error(`\n❌ Error: ${error.message}`);
        } else {
            console.error('\n❌ An unexpected error occurred');
        }
        process.exit(1);
    } finally {
        await prompter.close();
    }
}

// Run the main function
main().catch((error) => {
    console.error('Fatal error:', error);
    process.exit(1);
});
