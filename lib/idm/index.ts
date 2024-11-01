import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { Construct } from 'constructs';
import { BaseProps } from '../schema';
import { StackProps } from 'aws-cdk-lib';
import * as os from 'node:os';

type LisaCognitoStackProps = BaseProps & StackProps & {
    restApiUrl: string;
    stage: string;
};

export class LisaCognitoStack extends cdk.Stack {

    addAdmin = true;
    domain = '@example.com';
    constructor (scope: Construct, id: string, props: LisaCognitoStackProps) {
        super(scope, id, props);

        const { restApiUrl, stage } = props;

        // Create a User Pool
        const userPool = new cognito.UserPool(this, 'LisaUserPool', {
            userPoolName: 'lisa-test-users',
            selfSignUpEnabled: false,
            signInAliases: {
                email: true,
                username: true,
            },
            autoVerify: {
                email: false,
            },
            standardAttributes: {
                email: {
                    required: true,
                    mutable: true,
                },
                preferredUsername: {
                    required: true,
                    mutable: false,
                },
                fullname: {
                    required: true,
                    mutable: true,
                },
            },
            passwordPolicy: {
                minLength: 8,
                requireLowercase: true,
                requireUppercase: true,
                requireDigits: true,
                requireSymbols: true,
            },
            accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
            mfa: cognito.Mfa.OFF,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
        });

        // Create a User Pool Client
        const userPoolClient = new cognito.UserPoolClient(this, 'LisaUserPoolClient', {
            userPool,
            generateSecret: false,
            authFlows: {
                adminUserPassword: true,
                userPassword: true,
                userSrp: true,
            },
        });

        // Create an App Client for the hosted UI
        const webClient = userPool.addClient('web-client', {
            userPoolClientName: 'web-client',
            generateSecret: false, // Set to true if you need a client secret
            authFlows: {
                adminUserPassword: true,
                userPassword: true,
                userSrp: true,
                custom: true,
            },
            oAuth: {
                flows: {
                    authorizationCodeGrant: true,
                    implicitCodeGrant: true,
                },
                scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callbackUrls: [
                    'http://localhost:5173',
                    'http://localhost:5173/',
                    `${restApiUrl}/*`,
                    `${restApiUrl}/${stage}`,
                    `${restApiUrl}/${stage}/`
                ],
                logoutUrls: [],
            },
            supportedIdentityProviders: [
                cognito.UserPoolClientIdentityProvider.COGNITO,
            ],
        });
        // Add domain configuration
        const domain = userPool.addDomain('CognitoDomain', {
            cognitoDomain: {
                domainPrefix: 'app-login', // Replace with your desired prefix
            },
        });

        if (this.addAdmin) {
            this.createAdminUser(userPool);
        }

        const userName = os.userInfo().username;
        [userName, 'lisatest', 'lisademo'].forEach((user) => this.createUser(user, userPool));

        // Output the User Pool ID and Client ID
        new cdk.CfnOutput(this, 'UserPoolId', {
            value: userPool.userPoolId,
            description: 'User Pool ID',
        });

        new cdk.CfnOutput(this, 'UserPoolClientId', {
            value: userPoolClient.userPoolClientId,
            description: 'User Pool Client ID',
        });

        new cdk.CfnOutput(this, 'CognitoDomain', {
            value: domain.domainName,
            description: 'Cognito Domain',
        });

        new cdk.CfnOutput(this, 'WebClientId', {
            value: webClient.userPoolClientId,
            description: 'Web Client ID',
        });
    }

    createUser (user: string, userPool: cdk.aws_cognito.UserPool): cognito.CfnUserPoolUser {
        return new cognito.CfnUserPoolUser(this, `${user}User`, {
            userPoolId: userPool.userPoolId,
            username: user,
            userAttributes: [
                {
                    name: user,
                    value: `${user}${this.domain}`,
                },
            ],
        });
    }

    createAdminUser (userPool: cognito.UserPool) {
        // Create the "admin" user
        const adminUser = this.createUser('lisaadmin', userPool);

        // Create an "admin" group
        const adminGroup = new cognito.CfnUserPoolGroup(this, 'AdminGroup', {
            userPoolId: userPool.userPoolId,
            groupName: 'admin',
            description: 'Admin group with elevated privileges',
        });

        // Add the "admin" user to the "admin" group
        const groupAttrachment = new cognito.CfnUserPoolUserToGroupAttachment(this, 'AdminUserToGroupAttachment', {
            userPoolId: userPool.userPoolId,
            groupName: adminGroup.groupName!,
            username: adminUser.username!,
        });
        groupAttrachment.addDependency(adminUser);
        groupAttrachment.addDependency(adminGroup);
    }
}
