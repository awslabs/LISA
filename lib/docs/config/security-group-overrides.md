# Security Group Overrides User Guide

## Overview
This guide explains how to configure security group overrides in your environment. When you enable security group overrides, you'll need to override all security groups that are deployed across your stacks.

## Prerequisites
Before configuring security groups, you'll need the following values ready:

- Private VPC ID `[PRIVATE_VPC_ID]`
- Private Subnet CIDR 1/2 `[PRIVATE_SUBNET_CIDR_1, PRIVATE_SUBNET_CIDR_2]`
- Private Isolated Subnet CIDR 1/2 `[PRIVATE_ISOLATED_SUBNET_CIDR_1, PRIVATE_ISOLATED_SUBNET_CIDR_2]`

## Configuration Example

```json
{
  "liteLlmDbSecurityGroup": {
    "Type": "AWS::EC2::SecurityGroup",
    "Properties": {
      "GroupDescription": "Security group for LiteLLM dynamic model management database",
      "SecurityGroupEgress": [
        {
          "CidrIp": "0.0.0.0/0",
          "Description": "Allow all outbound traffic by default",
          "IpProtocol": "-1"
        }
      ],
      "SecurityGroupIngress": [
        {
          "CidrIp": "PRIVATE_ISOLATED_SUBNET_CIDR_1",
          "Description": "Allow REST API private subnets to communicate with LISA-LiteLLMScalingSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        },
        {
          "CidrIp": "PRIVATE_ISOLATED_SUBNET_CIDR_2",
          "Description": "Allow REST API private subnets to communicate with LISA-LiteLLMScalingSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        },
        {
          "CidrIp": "PRIVATE_SUBNET_CIDR_1",
          "Description": "Allow REST API private subnets to communicate with LISA-LiteLLMScalingSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        },
        {
          "CidrIp": "PRIVATE_SUBNET_CIDR_2",
          "Description": "Allow REST API private subnets to communicate with LISA-LiteLLMScalingSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        }
      ],
      "VpcId": {
        "Ref": "PRIVATE_VPC_ID"
      }
    }
  },
  "modelSecurityGroup": {
    "Type": "AWS::EC2::SecurityGroup",
    "Properties": {
      "GroupDescription": "Security group for ECS model application load balancer",
      "GroupName": "app-ECS-ALB-SG",
      "SecurityGroupEgress": [
        {
          "CidrIp": "0.0.0.0/0",
          "Description": "Allow all outbound traffic by default",
          "IpProtocol": "-1"
        }
      ],
      "SecurityGroupIngress": [
        {
          "CidrIp": {
            "Fn::GetAtt": [
              "PRIVATE_VPC_ID",
              "CidrBlock"
            ]
          },
          "Description": "Allow VPC traffic on port 80",
          "FromPort": 80,
          "IpProtocol": "tcp",
          "ToPort": 80
        },
        {
          "CidrIp": "0.0.0.0/0",
          "Description": "Allow any traffic on port 443",
          "FromPort": 443,
          "IpProtocol": "tcp",
          "ToPort": 443
        }
      ],
      "VpcId": {
        "Ref": "PRIVATE_VPC_ID"
      }
    }
  },
  "restAlbSecurityGroup": {
    "Type": "AWS::EC2::SecurityGroup",
    "Properties": {
      "GroupDescription": "Security group for REST API application load balancer",
      "GroupName": "app-RestAPI-ALB-SG",
      "SecurityGroupEgress": [
        {
          "CidrIp": "0.0.0.0/0",
          "Description": "Allow all outbound traffic by default",
          "IpProtocol": "-1"
        }
      ],
      "SecurityGroupIngress": [
        {
          "CidrIp": "0.0.0.0/0",
          "Description": "Allow from anyone on port 443",
          "FromPort": 443,
          "IpProtocol": "tcp",
          "ToPort": 443
        }
      ],
      "VpcId": {
        "Ref": "PRIVATE_VPC_ID"
      }
    }
  },
  "lambdaSecurityGroup": {
    "Type": "AWS::EC2::SecurityGroup",
    "Properties": {
      "GroupDescription": "Security group for authorizer and API Lambdas",
      "GroupName": "app-Lambda-SG",
      "SecurityGroupEgress": [
        {
          "CidrIp": "0.0.0.0/0",
          "Description": "Allow all outbound traffic by default",
          "IpProtocol": "-1"
        }
      ],
      "VpcId": {
        "Ref": "PRIVATE_VPC_ID"
      }
    }
  },
  "pgVectorSecurityGroup": {
    "Type": "AWS::EC2::SecurityGroup",
    "Properties": {
      "GroupDescription": "Security group for RAG PGVector database",
      "GroupName": "LISA-PGVector-SG",
      "SecurityGroupEgress": [
        {
          "CidrIp": "0.0.0.0/0",
          "Description": "Allow all outbound traffic by default",
          "IpProtocol": "-1"
        }
      ],
      "SecurityGroupIngress": [
        {
          "CidrIp": "PRIVATE_ISOLATED_SUBNET_CIDR_1",
          "Description": "Allow REST API private subnets to communicate with LISA-PGVectorSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        },
        {
          "CidrIp": "PRIVATE_ISOLATED_SUBNET_CIDR_2",
          "Description": "Allow REST API private subnets to communicate with LISA-PGVectorSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        },
        {
          "CidrIp": "PRIVATE_SUBNET_CIDR_1",
          "Description": "Allow REST API private subnets to communicate with LISA-PGVectorSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        },
        {
          "CidrIp": "PRIVATE_SUBNET_CIDR_2",
          "Description": "Allow REST API private subnets to communicate with LISA-PGVectorSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        }
      ],
      "VpcId": {
        "Ref": "PRIVATE_VPC_ID"
      }
    }
  },
  "openSearchSecurityGroup": {
    "Type": "AWS::EC2::SecurityGroup",
    "Properties": {
      "GroupDescription": "Security group for RAG OpenSearch database",
      "GroupName": "LISA-OpenSearch-SG",
      "SecurityGroupEgress": [
        {
          "CidrIp": "0.0.0.0/0",
          "Description": "Allow all outbound traffic by default",
          "IpProtocol": "-1"
        }
      ],
      "SecurityGroupIngress": [
        {
          "CidrIp": "PRIVATE_ISOLATED_SUBNET_CIDR_1",
          "Description": "Allow REST API private subnets to communicate with LISA-PGVectorSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        },
        {
          "CidrIp": "PRIVATE_ISOLATED_SUBNET_CIDR_2",
          "Description": "Allow REST API private subnets to communicate with LISA-PGVectorSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        },
        {
          "CidrIp": "PRIVATE_SUBNET_CIDR_1",
          "Description": "Allow REST API private subnets to communicate with LISA-PGVectorSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        },
        {
          "CidrIp": "PRIVATE_SUBNET_CIDR_2",
          "Description": "Allow REST API private subnets to communicate with LISA-PGVectorSg",
          "FromPort": 5432,
          "IpProtocol": "tcp",
          "ToPort": 5432
        }
      ],
      "VpcId": {
        "Ref": "PRIVATE_VPC_ID"
      }
    }
  }
}
```