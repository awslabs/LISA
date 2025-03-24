import { Construct } from 'constructs';
import { BaseProps } from '../../schema';
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { AttributeType, BillingMode, ProjectionType, Table } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { getDefaultRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../../api-base/utils';
import { createLambdaRole } from '../../core/utils';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Vpc } from '../../networking/vpc';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';

type PromptTemplateApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

// Construct for managing API endpoints related to prompt templates
export class PromptTemplateApi extends Construct {
    constructor (scope: Construct, id: string, props: PromptTemplateApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'session-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        const fastapiLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'models-fastapi-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/fastapi`),
        );

        const promptTemplatesTable = new Table(this, 'PromptTemplatesTable', {
            partitionKey: {
                name: 'id',
                type: AttributeType.STRING
            },
            sortKey: {
                name: 'created',
                type: AttributeType.STRING
            },
            removalPolicy: config.removalPolicy,
            billingMode: BillingMode.PAY_PER_REQUEST,
            pointInTimeRecovery: true
        });

        const byOwnerIndexName = 'byOwner';
        promptTemplatesTable.addGlobalSecondaryIndex({
            indexName: byOwnerIndexName,
            projectionType: ProjectionType.ALL,
            partitionKey: {
                name: 'owner',
                type: AttributeType.STRING
            },
            sortKey: {
                name: 'created',
                type: AttributeType.STRING
            }
        });

        const byLatestIndexName = 'byLatest';
        promptTemplatesTable.addGlobalSecondaryIndex({
            indexName: byLatestIndexName,
            projectionType: ProjectionType.ALL,
            partitionKey: {
                name: 'id',
                type: AttributeType.STRING
            },
            sortKey: {
                name: 'created',
                type: AttributeType.STRING
            }
        });

        const apis: PythonLambdaFunction[] = [
            {
                name: 'create',
                resource: 'prompt_templates',
                description: 'Creates prompt template',
                path: 'prompt-templates',
                method: 'POST',
                environment: {
                    PROMPT_TEMPLATES_TABLE_NAME: promptTemplatesTable.tableName,
                },
            },
            {
                name: 'get',
                resource: 'prompt_templates',
                description: 'Creates or updates prompt template',
                path: 'prompt-templates/{promptTemplateId}',
                method: 'GET',
                environment: {
                    PROMPT_TEMPLATES_TABLE_NAME: promptTemplatesTable.tableName,
                },
            },
            {
                name: 'list',
                resource: 'prompt_templates',
                description: 'Lists available prompt templates',
                path: 'prompt-templates',
                method: 'GET',
                environment: {
                    PROMPT_TEMPLATES_TABLE_NAME: promptTemplatesTable.tableName,
                    PROMPT_TEMPLATES_BY_LATEST_INDEX_NAME: byOwnerIndexName,
                },
            },
            {
                name: 'update',
                resource: 'prompt_templates',
                description: 'Updates prompt template',
                path: 'prompt-templates/{promptTemplateId}',
                method: 'PUT',
                environment: {
                    PROMPT_TEMPLATES_TABLE_NAME: promptTemplatesTable.tableName,
                },
            },
            {
                name: 'delete',
                resource: 'prompt_templates',
                description: 'Creates or updates prompt template',
                path: 'prompt-templates/{promptTemplateId}',
                method: 'DELETE',
                environment: {
                    PROMPT_TEMPLATES_TABLE_NAME: promptTemplatesTable.tableName,
                },
            },
        ];

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'PromptTemplatesApi', promptTemplatesTable.tableArn, config.roles?.LambdaExecutionRole);

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        apis.forEach((f) => {
            const lambdaFunction = registerAPIEndpoint(
                this,
                restApi,
                authorizer,
                './lambda',
                [commonLambdaLayer, fastapiLambdaLayer],
                f,
                getDefaultRuntime(),
                vpc,
                securityGroups,
                lambdaRole,
            );

            if (f.method === 'POST' || f.method === 'PUT') {
                promptTemplatesTable.grantWriteData(lambdaFunction);
            } else if (f.method === 'GET') {
                promptTemplatesTable.grantReadData(lambdaFunction);
            } else if (f.method === 'DELETE') {
                promptTemplatesTable.grantReadWriteData(lambdaFunction);
            }
        });
    }
}