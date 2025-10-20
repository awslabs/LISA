# IAM Role Override Configuration Guide

## Overview

This guide explains how to configure IAM role overrides for your environment. Role overrides allow you to customize
permissions and policies for various service components including Lambda functions, ECS tasks, and API Gateway
integrations. By default, LISA will generate all required roles.

**NOTE**
Some roles cannot be overridden as they aren't exposed via CDK constructs:

- S3 lifecycle policy roles
- Auto Scaling Group roles attached to ECS clusters

## Configuration Example

The example provided is an export from a deployed LISA instance based on Least Privilege Access.

```json
{
  "RestApiAuthorizerRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ]
          ]
        },
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
            ]
          ]
        }
      ]
    }
  },
  "RestApiAuthorizerRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": "sqs:SendMessage",
            "Effect": "Allow",
            "Resource": {
              "Fn::GetAtt": [
                "LisaApiAuthorizerAuthorizerLambdaDLQAE1E4673",
                "Arn"
              ]
            }
          },
          {
            "Action": [
              "secretsmanager:DescribeSecret",
              "secretsmanager:GetSecretValue"
            ],
            "Effect": "Allow",
            "Resource": {
              "Fn::Join": [
                "",
                [
                  "arn:aws:secretsmanager:${REGION}:${ACCOUNT}:secret:",
                  {
                    "Ref": "LisaApiAuthorizerLisaApiAuthorizermanagementKeyStringParameterParameter5998CD79"
                  },
                  "-??????"
                ]
              ]
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "RestApiAuthorizerRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "RestApiAuthorizerRole"
        }
      ]
    }
  },
  "ECSRestApiExRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "ecs-tasks.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      }
    }
  },
  "ECSMcpWorkbenchApiExRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
              "Effect": "Allow",
              "Action": [
                  "ecr:GetAuthorizationToken",
                  "ecr:BatchCheckLayerAvailability",
                  "ecr:GetDownloadUrlForLayer",
                  "ecr:BatchGetImage",
                  "logs:CreateLogStream",
                  "logs:PutLogEvents"
              ],
              "Resource": "*"
          }
        ],
        "Version": "2012-10-17"
      }
    }
  },
  "ECSRestApiExRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": [
              "ecr:BatchCheckLayerAvailability",
              "ecr:BatchGetImage",
              "ecr:GetDownloadUrlForLayer"
            ],
            "Effect": "Allow",
            "Resource": "arn:aws:ecr:${REGION}:${ACCOUNT}:repository/cdk-hnb659fds-container-assets-${ACCOUNT}-${REGION}"
          },
          {
            "Action": "ecr:GetAuthorizationToken",
            "Effect": "Allow",
            "Resource": "*"
          },
          {
            "Action": [
              "logs:CreateLogStream",
              "logs:PutLogEvents"
            ],
            "Effect": "Allow",
            "Resource": {
              "Fn::GetAtt": [
                "RestApiECSClusterRESTEc2TaskDefinitionRESTContainerLogGroup01AB5F5D",
                "Arn"
              ]
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "ECSRestApiExRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "ECSRestApiExRole"
        }
      ]
    }
  },
  "S3ReaderRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "apigateway.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "Description": "Allows API gateway to proxy static website assets",
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/AmazonS3ReadOnlyAccess"
            ]
          ]
        }
      ],
      "RoleName": "app-lisa-ui-dev-s3-reader-role"
    }
  },
  "ECSModelDeployerRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ]
          ]
        }
      ]
    }
  },
  "ECSModelDeployerRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": [
              "s3:GetBucket*",
              "s3:GetObject*",
              "s3:List*"
            ],
            "Effect": "Allow",
            "Resource": [
              "arn:aws:s3:::cdk-hnb659fds-assets-${ACCOUNT}-${REGION}",
              "arn:aws:s3:::cdk-hnb659fds-assets-${ACCOUNT}-${REGION}/*"
            ]
          },
          {
            "Action": [
              "s3:Abort*",
              "s3:DeleteObject*",
              "s3:GetBucket*",
              "s3:GetObject*",
              "s3:List*",
              "s3:PutObject",
              "s3:PutObjectLegalHold",
              "s3:PutObjectRetention",
              "s3:PutObjectTagging",
              "s3:PutObjectVersionTagging"
            ],
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "Bucket83908E77",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "Bucket83908E77",
                        "Arn"
                      ]
                    },
                    "/*"
                  ]
                ]
              }
            ]
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "ECSModelDeployerRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "ECSModelDeployerRole"
        }
      ]
    }
  },
  "LambdaExecutionRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "Description": "Role used by LISA SessionApi lambdas to access AWS resources",
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
            ]
          ]
        }
      ],
      "Policies": [
        {
          "PolicyDocument": {
            "Statement": [
              {
                "Action": [
                  "dynamodb:BatchGetItem",
                  "dynamodb:ConditionCheckItem",
                  "dynamodb:DescribeTable",
                  "dynamodb:GetItem",
                  "dynamodb:GetRecords",
                  "dynamodb:GetShardIterator",
                  "dynamodb:Query",
                  "dynamodb:Scan"
                ],
                "Effect": "Allow",
                "Resource": [
                  {
                    "Fn::GetAtt": [
                      "SessionApiSessionsTableDA695141",
                      "Arn"
                    ]
                  },
                  {
                    "Fn::Join": [
                      "",
                      [
                        {
                          "Fn::GetAtt": [
                            "SessionApiSessionsTableDA695141",
                            "Arn"
                          ]
                        },
                        "/*"
                      ]
                    ]
                  }
                ]
              }
            ],
            "Version": "2012-10-17"
          },
          "PolicyName": "lambdaPermissions"
        }
      ],
      "RoleName": "app-LisaSessionApiLambdaExecutionRole"
    }
  },
  "LambdaExecutionRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": "sqs:SendMessage",
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "SessionApiapplisachatdevsessiondeletesessionDLQ3EEC4880",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "SessionApiapplisachatdevsessiondeleteusersessionsDLQ8138C58A",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "SessionApiapplisachatdevsessiongetsessionDLQAB1127BE",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "SessionApiapplisachatdevsessionlistsessionsDLQD00F489B",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "SessionApiapplisachatdevsessionputsessionDLQ2C63E706",
                  "Arn"
                ]
              }
            ]
          },
          {
            "Action": [
              "dynamodb:BatchGetItem",
              "dynamodb:ConditionCheckItem",
              "dynamodb:DescribeTable",
              "dynamodb:GetItem",
              "dynamodb:GetRecords",
              "dynamodb:GetShardIterator",
              "dynamodb:Query",
              "dynamodb:Scan"
            ],
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "SessionApiSessionsTableDA695141",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "SessionApiSessionsTableDA695141",
                        "Arn"
                      ]
                    },
                    "/index/*"
                  ]
                ]
              }
            ]
          },
          {
            "Action": [
              "dynamodb:BatchGetItem",
              "dynamodb:BatchWriteItem",
              "dynamodb:ConditionCheckItem",
              "dynamodb:DeleteItem",
              "dynamodb:DescribeTable",
              "dynamodb:GetItem",
              "dynamodb:GetRecords",
              "dynamodb:GetShardIterator",
              "dynamodb:PutItem",
              "dynamodb:Query",
              "dynamodb:Scan",
              "dynamodb:UpdateItem"
            ],
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "SessionApiSessionsTableDA695141",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "SessionApiSessionsTableDA695141",
                        "Arn"
                      ]
                    },
                    "/index/*"
                  ]
                ]
              }
            ]
          },
          {
            "Action": [
              "dynamodb:BatchWriteItem",
              "dynamodb:DeleteItem",
              "dynamodb:DescribeTable",
              "dynamodb:PutItem",
              "dynamodb:UpdateItem"
            ],
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "SessionApiSessionsTableDA695141",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "SessionApiSessionsTableDA695141",
                        "Arn"
                      ]
                    },
                    "/index/*"
                  ]
                ]
              }
            ]
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "LambdaExecutionRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "LambdaExecutionRole"
        }
      ]
    }
  },
  "LambdaConfigurationApiExecutionRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "Description": "Role used by LISA ConfigurationApi lambdas to access AWS resources",
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
            ]
          ]
        }
      ],
      "Policies": [
        {
          "PolicyDocument": {
            "Statement": [
              {
                "Action": [
                  "dynamodb:BatchGetItem",
                  "dynamodb:ConditionCheckItem",
                  "dynamodb:DescribeTable",
                  "dynamodb:GetItem",
                  "dynamodb:GetRecords",
                  "dynamodb:GetShardIterator",
                  "dynamodb:Query",
                  "dynamodb:Scan"
                ],
                "Effect": "Allow",
                "Resource": [
                  {
                    "Fn::GetAtt": [
                      "ConfigurationApiConfigurationTable4B2B7EE1",
                      "Arn"
                    ]
                  },
                  {
                    "Fn::Join": [
                      "",
                      [
                        {
                          "Fn::GetAtt": [
                            "ConfigurationApiConfigurationTable4B2B7EE1",
                            "Arn"
                          ]
                        },
                        "/*"
                      ]
                    ]
                  }
                ]
              }
            ],
            "Version": "2012-10-17"
          },
          "PolicyName": "lambdaPermissions"
        }
      ],
      "RoleName": "app-LisaConfigurationApiLambdaExecutionRole"
    }
  },
  "LambdaConfigurationApiExecutionRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": "sqs:SendMessage",
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "ConfigurationApiapplisachatdevconfigurationgetconfigurationDLQ62A925F5",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ConfigurationApiapplisachatdevconfigurationupdateconfigurationDLQ886900A4",
                  "Arn"
                ]
              }
            ]
          },
          {
            "Action": [
              "dynamodb:BatchGetItem",
              "dynamodb:ConditionCheckItem",
              "dynamodb:DescribeTable",
              "dynamodb:GetItem",
              "dynamodb:GetRecords",
              "dynamodb:GetShardIterator",
              "dynamodb:Query",
              "dynamodb:Scan"
            ],
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "ConfigurationApiConfigurationTable4B2B7EE1",
                  "Arn"
                ]
              },
              {
                "Ref": "AWS::NoValue"
              }
            ]
          },
          {
            "Action": [
              "dynamodb:BatchWriteItem",
              "dynamodb:DeleteItem",
              "dynamodb:DescribeTable",
              "dynamodb:PutItem",
              "dynamodb:UpdateItem"
            ],
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "ConfigurationApiConfigurationTable4B2B7EE1",
                  "Arn"
                ]
              },
              {
                "Ref": "AWS::NoValue"
              }
            ]
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "LambdaConfigurationApiExecutionRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "LambdaConfigurationApiExecutionRole"
        }
      ]
    }
  },
  "RagLambdaExecutionRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "Description": "Role used by RAG API lambdas to access AWS resources",
      "ManagedPolicyArns": [
        {
          "Ref": "appRAGPolicy07A18B09"
        }
      ],
      "RoleName": "app-LisaRagLambdaExecutionRole"
    }
  },
  "ECSRestApiRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "ecs-tasks.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "Description": "Allow REST API task access to AWS resources",
      "ManagedPolicyArns": [
        {
          "Ref": "appECSPolicy361D8A62"
        }
      ],
      "RoleName": "app-REST-Role"
    }
  },
  "ECSMcpWorkbenchApiRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "ecs-tasks.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "Description": "Allow MCP Workbench API task access to AWS resources",
      "ManagedPolicyArns": [
        {
          "Ref": "appECSPolicy361D8A62"
        }
      ],
      "RoleName": "app-REST-Role"
    }
  },
  "DocsDeployerRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ]
          ]
        }
      ]
    }
  },
  "DocsDeployerRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": [
              "s3:GetBucket*",
              "s3:GetObject*",
              "s3:List*"
            ],
            "Effect": "Allow",
            "Resource": [
              "arn:${PARTITION}:s3:::cdk-hnb659fds-assets-${ACCOUNT}-${REGION}",
              "arn:${PARTITION}:s3:::cdk-hnb659fds-assets-${ACCOUNT}-${REGION}/*"
            ]
          },
          {
            "Action": [
              "s3:Abort*",
              "s3:DeleteObject*",
              "s3:GetBucket*",
              "s3:GetObject*",
              "s3:List*",
              "s3:PutObject",
              "s3:PutObjectLegalHold",
              "s3:PutObjectRetention",
              "s3:PutObjectTagging",
              "s3:PutObjectVersionTagging"
            ],
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "DocsBucketECEA003F",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "DocsBucketECEA003F",
                        "Arn"
                      ]
                    },
                    "/*"
                  ]
                ]
              }
            ]
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "DocsDeployerRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "DocsDeployerRole"
        }
      ]
    }
  },
  "DocsRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "apigateway.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "Description": "Allows API gateway to proxy static website assets"
    }
  },
  "DocsRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": [
              "s3:GetBucket*",
              "s3:GetObject*",
              "s3:List*"
            ],
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "DocsBucketECEA003F",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "DocsBucketECEA003F",
                        "Arn"
                      ]
                    },
                    "/*"
                  ]
                ]
              }
            ]
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "DocsRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "DocsRole"
        }
      ]
    }
  },
  "UIDeploymentRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ]
          ]
        }
      ]
    }
  },
  "UIDeploymentRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": [
              "s3:GetBucket*",
              "s3:GetObject*",
              "s3:List*"
            ],
            "Effect": "Allow",
            "Resource": [
              "arn:${PARTITION}:s3:::cdk-hnb659fds-assets-${ACCOUNT}-${REGION}",
              "arn:${PARTITION}:s3:::cdk-hnb659fds-assets-${ACCOUNT}-${REGION}/*"
            ]
          },
          {
            "Action": [
              "s3:Abort*",
              "s3:DeleteObject*",
              "s3:GetBucket*",
              "s3:GetObject*",
              "s3:List*",
              "s3:PutObject",
              "s3:PutObjectLegalHold",
              "s3:PutObjectRetention",
              "s3:PutObjectTagging",
              "s3:PutObjectVersionTagging"
            ],
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "Bucket83908E77",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "Bucket83908E77",
                        "Arn"
                      ]
                    },
                    "/*"
                  ]
                ]
              }
            ]
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "UIDeploymentRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "UIDeploymentRole"
        }
      ]
    }
  },
  "DockerImageBuilderDeploymentRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
            ]
          ]
        }
      ],
      "Policies": [
        {
          "PolicyDocument": {
            "Statement": [
              {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Resource": "arn:*:iam::*:role/cdk-*"
              },
              {
                "Action": [
                  "ec2:AssignPrivateIpAddresses",
                  "ec2:CreateNetworkInterface",
                  "ec2:DeleteNetworkInterface",
                  "ec2:DescribeNetworkInterfaces",
                  "ec2:DescribeSubnets",
                  "ec2:UnassignPrivateIpAddresses"
                ],
                "Effect": "Allow",
                "Resource": "*"
              }
            ],
            "Version": "2012-10-17"
          },
          "PolicyName": "lambdaPermissions"
        }
      ]
    }
  },
  "DockerImageBuilderEC2Role": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "ec2.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "RoleName": "app-lisa-models-dev-docker-image-builder-ec2-role"
    }
  },
  "DockerImageBuilderEC2RoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": "s3:GetObject",
            "Effect": "Allow",
            "Resource": {
              "Fn::Join": [
                "",
                [
                  {
                    "Fn::GetAtt": [
                      "ModelsApidockerimagebuilderapplisamodelsdevdockerimagebuilderec2bucket08754F14",
                      "Arn"
                    ]
                  },
                  "/*"
                ]
              ]
            }
          },
          {
            "Action": "s3:ListBucket",
            "Effect": "Allow",
            "Resource": {
              "Fn::GetAtt": [
                "ModelsApidockerimagebuilderapplisamodelsdevdockerimagebuilderec2bucket08754F14",
                "Arn"
              ]
            }
          },
          {
            "Action": [
              "ecr:BatchCheckLayerAvailability",
              "ecr:CompleteLayerUpload",
              "ecr:GetAuthorizationToken",
              "ecr:InitiateLayerUpload",
              "ecr:PutImage",
              "ecr:UploadLayerPart"
            ],
            "Effect": "Allow",
            "Resource": "*"
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "DockerImageBuilderEC2RoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "DockerImageBuilderEC2Role"
        }
      ]
    }
  },
  "DockerImageBuilderRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ]
          ]
        },
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
            ]
          ]
        }
      ],
      "RoleName": "app-lisa-models-dev-docker_image_builder_role"
    }
  },
  "DockerImageBuilderRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": [
              "ec2:AssignPrivateIpAddresses",
              "ec2:CreateNetworkInterface",
              "ec2:CreateTags",
              "ec2:DeleteNetworkInterface",
              "ec2:DescribeNetworkInterfaces",
              "ec2:DescribeSubnets",
              "ec2:RunInstances",
              "ec2:UnassignPrivateIpAddresses"
            ],
            "Effect": "Allow",
            "Resource": "*"
          },
          {
            "Action": "iam:PassRole",
            "Effect": "Allow",
            "Resource": {
              "Fn::GetAtt": [
                "DockerImageBuilderEC2Role",
                "Arn"
              ]
            }
          },
          {
            "Action": "ssm:GetParameter",
            "Effect": "Allow",
            "Resource": "arn:*:ssm:*::parameter/aws/service/*"
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "DockerImageBuilderRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "DockerImageBuilderRole"
        }
      ]
    }
  },
  "DockerImageBuilderRoleSQSPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": "sqs:SendMessage",
            "Effect": "Allow",
            "Resource": {
              "Fn::GetAtt": [
                "ModelsApidockerimagebuilderdockerimagebuilderDLQC5B63450",
                "Arn"
              ]
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "DockerImageBuilderRoleSQSPolicy",
      "Roles": [
        {
          "Ref": "DockerImageBuilderRole"
        }
      ]
    }
  },
  "ModelsSfnLambdaRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
            ]
          ]
        }
      ],
      "Policies": [
        {
          "PolicyDocument": {
            "Statement": [
              {
                "Action": [
                  "dynamodb:DeleteItem",
                  "dynamodb:GetItem",
                  "dynamodb:PutItem",
                  "dynamodb:UpdateItem"
                ],
                "Effect": "Allow",
                "Resource": [
                  {
                    "Fn::GetAtt": [
                      "ModelsApiModelTable72B9582E",
                      "Arn"
                    ]
                  },
                  {
                    "Fn::Join": [
                      "",
                      [
                        {
                          "Fn::GetAtt": [
                            "ModelsApiModelTable72B9582E",
                            "Arn"
                          ]
                        },
                        "/*"
                      ]
                    ]
                  }
                ]
              },
              {
                "Action": [
                  "cloudformation:CreateStack",
                  "cloudformation:DeleteStack",
                  "cloudformation:DescribeStacks"
                ],
                "Effect": "Allow",
                "Resource": "arn:*:cloudformation:*:*:stack/*"
              },
              {
                "Action": "lambda:InvokeFunction",
                "Effect": "Allow",
                "Resource": [
                  {
                    "Fn::GetAtt": [
                      "ModelsApidockerimagebuilderapplisamodelsdevdockerimagebuilder9B580919",
                      "Arn"
                    ]
                  },
                  {
                    "Fn::GetAtt": [
                      "ModelsApiecsmodeldeployerapplisamodelsdevecsmodeldeployer6051670E",
                      "Arn"
                    ]
                  }
                ]
              },
              {
                "Action": [
                  "autoscaling:DescribeAutoScalingGroups",
                  "autoscaling:UpdateAutoScalingGroup",
                  "ec2:AssignPrivateIpAddresses",
                  "ec2:CreateNetworkInterface",
                  "ec2:DeleteNetworkInterface",
                  "ec2:DescribeNetworkInterfaces",
                  "ec2:DescribeSubnets",
                  "ec2:UnassignPrivateIpAddresses",
                  "ecr:DescribeImages"
                ],
                "Effect": "Allow",
                "Resource": "*"
              },
              {
                "Action": "ec2:TerminateInstances",
                "Condition": {
                  "StringEquals": {
                    "aws:ResourceTag/lisa_temporary_instance": "true"
                  }
                },
                "Effect": "Allow",
                "Resource": "*"
              },
              {
                "Action": "ssm:GetParameter",
                "Effect": "Allow",
                "Resource": {
                  "Fn::Join": [
                    "",
                    [
                      "arn:${PARTITION}:ssm:${REGION}:${ACCOUNT}:parameter",
                      {
                        "Fn::ImportValue": "app-lisa-serve-dev:ExportsOutputRefLisaServeRestApiUriStringParameterF8D56C8BA0E6222B"
                      }
                    ]
                  ]
                }
              },
              {
                "Action": "secretsmanager:GetSecretValue",
                "Effect": "Allow",
                "Resource": {
                  "Fn::Join": [
                    "",
                    [
                      "arn:${PARTITION}:secretsmanager:${REGION}:${ACCOUNT}:secret:",
                      {
                        "Ref": "SsmParameterValuedevapplisamanagementKeySecretNameC96584B6F00A464EAD1953AFF4B05118Parameter"
                      },
                      "-??????"
                    ]
                  ]
                }
              }
            ],
            "Version": "2012-10-17"
          },
          "PolicyName": "lambdaPermissions"
        }
      ]
    }
  },
  "ModelsSfnLambdaRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": "sqs:SendMessage",
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowAddModelToLitellmDLQ3B4AE9BA",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowHandleFailureDLQ17AD8525",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowPollCreateStackDLQB2DDE435",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowPollDockerImageAvailableDLQ682A018B",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowSetModelToCreatingDLQ5B85AD0A",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowStartCopyDockerImageDLQ6A0BAD15",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowStartCreateStackDLQ75DFA17E",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowDeleteFromDdbDLQ598B9790",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowDeleteFromLitellmDLQA9867D0B",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowDeleteStackDLQ75E2E6A7",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowMonitorDeleteStackDLQ705504AE",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowSetModelToDeletingDLQAEC29C62",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiUpdateModelWorkflowHandleFinishUpdateDLQD33B3816",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiUpdateModelWorkflowHandleJobIntakeDLQ64D8E67D",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiUpdateModelWorkflowHandlePollCapacityDLQB87E1908",
                  "Arn"
                ]
              }
            ]
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "ModelsSfnLambdaRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "ModelsSfnLambdaRole"
        }
      ]
    }
  },
  "ModelApiRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "states.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      }
    }
  },
  "ModelApiRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": "lambda:InvokeFunction",
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowAddModelToLitellmFunc6B8DBAE6",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowHandleFailureFunc7CC3D0A8",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowPollCreateStackFunc3B3660A0",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowPollDockerImageAvailableFuncF23F9A33",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowSetModelToCreatingFunc4E8D1CA0",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowStartCopyDockerImageFuncE508BA76",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiCreateModelWorkflowStartCreateStackFuncCEE91381",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiCreateModelWorkflowAddModelToLitellmFunc6B8DBAE6",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiCreateModelWorkflowHandleFailureFunc7CC3D0A8",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiCreateModelWorkflowPollCreateStackFunc3B3660A0",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiCreateModelWorkflowPollDockerImageAvailableFuncF23F9A33",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiCreateModelWorkflowSetModelToCreatingFunc4E8D1CA0",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiCreateModelWorkflowStartCopyDockerImageFuncE508BA76",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiCreateModelWorkflowStartCreateStackFuncCEE91381",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowDeleteFromDdbFuncAB2B6BFB",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowDeleteFromLitellmFunc75B8FA09",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowDeleteStackFunc0B8E2D75",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowMonitorDeleteStackFunc2CE43E62",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiDeleteModelWorkflowSetModelToDeletingFuncCA1C7F8D",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiDeleteModelWorkflowDeleteFromDdbFuncAB2B6BFB",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiDeleteModelWorkflowDeleteFromLitellmFunc75B8FA09",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiDeleteModelWorkflowDeleteStackFunc0B8E2D75",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiDeleteModelWorkflowMonitorDeleteStackFunc2CE43E62",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiDeleteModelWorkflowSetModelToDeletingFuncCA1C7F8D",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiUpdateModelWorkflowHandleFinishUpdateFunc92E550FB",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiUpdateModelWorkflowHandleJobIntakeFuncA1438F67",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiUpdateModelWorkflowHandlePollCapacityFunc5376513F",
                  "Arn"
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiUpdateModelWorkflowHandleFinishUpdateFunc92E550FB",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiUpdateModelWorkflowHandleJobIntakeFuncA1438F67",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              },
              {
                "Fn::Join": [
                  "",
                  [
                    {
                      "Fn::GetAtt": [
                        "ModelsApiUpdateModelWorkflowHandlePollCapacityFunc5376513F",
                        "Arn"
                      ]
                    },
                    ":*"
                  ]
                ]
              }
            ]
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "ModelApiRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "ModelApiRole"
        }
      ]
    }
  },
  "ModelSfnRole": {
    "Type": "AWS::IAM::Role",
    "Properties": {
      "AssumeRolePolicyDocument": {
        "Statement": [
          {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
              "Service": "lambda.amazonaws.com"
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "Description": "Role used by LISA ModelApi lambdas to access AWS resources",
      "ManagedPolicyArns": [
        {
          "Fn::Join": [
            "",
            [
              "arn:",
              {
                "Ref": "AWS::Partition"
              },
              ":iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
            ]
          ]
        }
      ],
      "Policies": [
        {
          "PolicyDocument": {
            "Statement": [
              {
                "Action": [
                  "dynamodb:BatchGetItem",
                  "dynamodb:ConditionCheckItem",
                  "dynamodb:DescribeTable",
                  "dynamodb:GetItem",
                  "dynamodb:GetRecords",
                  "dynamodb:GetShardIterator",
                  "dynamodb:Query",
                  "dynamodb:Scan"
                ],
                "Effect": "Allow",
                "Resource": [
                  {
                    "Fn::GetAtt": [
                      "ModelsApiModelTable72B9582E",
                      "Arn"
                    ]
                  },
                  {
                    "Fn::Join": [
                      "",
                      [
                        {
                          "Fn::GetAtt": [
                            "ModelsApiModelTable72B9582E",
                            "Arn"
                          ]
                        },
                        "/*"
                      ]
                    ]
                  }
                ]
              }
            ],
            "Version": "2012-10-17"
          },
          "PolicyName": "lambdaPermissions"
        }
      ],
      "RoleName": "app-LisaModelApiLambdaExecutionRole"
    }
  },
  "ModelSfnRoleDefaultPolicy": {
    "Type": "AWS::IAM::Policy",
    "Properties": {
      "PolicyDocument": {
        "Statement": [
          {
            "Action": "sqs:SendMessage",
            "Effect": "Allow",
            "Resource": [
              {
                "Fn::GetAtt": [
                  "ModelsApiapplisamodelsdevmodelsdocsDLQF4F4BAC8",
                  "Arn"
                ]
              },
              {
                "Fn::GetAtt": [
                  "ModelsApiapplisamodelsdevmodelshandlerDLQB5638333",
                  "Arn"
                ]
              }
            ]
          },
          {
            "Action": [
              "ssm:DescribeParameters",
              "ssm:GetParameter",
              "ssm:GetParameterHistory",
              "ssm:GetParameters"
            ],
            "Effect": "Allow",
            "Resource": {
              "Fn::Join": [
                "",
                [
                  "arn:${PARTITION}:ssm:${REGION}:${ACCOUNT}:parameter",
                  {
                    "Fn::ImportValue": "app-lisa-serve-dev:ExportsOutputRefLisaServeRestApiUriStringParameterF8D56C8BA0E6222B"
                  }
                ]
              ]
            }
          }
        ],
        "Version": "2012-10-17"
      },
      "PolicyName": "ModelSfnRoleDefaultPolicy",
      "Roles": [
        {
          "Ref": "ModelSfnRole"
        }
      ]
    }
  }
}

```
