# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
name: "LISA Documentation"
text: "LLM Inference Solution for Amazon Dedicated Cloud (LISA)"
actions:
- theme: brand
text: Getting Started
link: /admin/getting-started

features:
- title: Authentication and Authorization
  details: via AWS Cognito or OpenID Connect (OIDC) providers, ensuring secure access to both the REST API and Chat UI through token-based authentication and role-based access control.
- title: Model Hosting
  details: on AWS ECS with autoscaling and efficient traffic management using Application Load Balancers (ALBs), providing scalable and high-performance model inference.
- title: Model Management
  details: using AWS Step Functions to orchestrate complex workflows for creating, updating, and deleting models, automatically managing underlying ECS infrastructure.
- title: Inference Requests
  details: served via both the REST API and the Chat UI, dynamically routing user inputs to the appropriate ECS-hosted models for real-time inference.
- title: Chat Interface
  details: enabling users to interact with LISA through a user-friendly web interface, offering seamless real-time model interaction and session continuity.
- title: Retrieval-Augmented Generation (RAG) Operations
  details: leveraging either OpenSearch or PGVector for efficient retrieval of relevant external data to enhance model responses.


### License Notice

Although this repository is released under the Apache 2.0 license, when configured to use PGVector as a RAG store it uses
the third party `psycopg2-binary` library. The `psycopg2-binary` project's licensing includes the [LGPL with exceptions](https://github.com/psycopg/psycopg2/blob/master/LICENSE) license.
