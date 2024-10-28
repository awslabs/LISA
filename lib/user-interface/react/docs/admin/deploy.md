
# Deployment
## Using pre-built resources

A default configuration will build the necessary containers, lambda layers, and production optimized
web application at build time. In the event that you would like to use pre-built resources due to
network connectivity reasons or other concerns with the environment where you'll be deploying LISA
you can do so.

- For ECS containers (Models, APIs, etc) you can modify the `containerConfig` block of
  the corresponding entry in `config.yaml`. For container images you can provide a path to a directory
  from which a docker container will be built (default), a path to a tarball, an ECR repository arn and
  optional tag, or a public registry path.
    - We provide immediate support for HuggingFace TGI and TEI containers and for vLLM containers. The `example_config.yaml`
      file provides examples for TGI and TEI, and the only difference for using vLLM is to change the
      `inferenceContainer`, `baseImage`, and `path` options, as indicated in the snippet below. All other options can
      remain the same as the model definition examples we have for the TGI or TEI models. vLLM can also support embedding
      models in this way, so all you need to do is refer to the embedding model artifacts and remove the `streaming` field
      to deploy the embedding model.
    - vLLM has support for the OpenAI Embeddings API, but model support for it is limited because the feature is new. Currently,
      the only supported embedding model with vLLM is [intfloat/e5-mistral-7b-instruct](https://huggingface.co/intfloat/e5-mistral-7b-instruct),
      but this list is expected to grow over time as vLLM updates.
      ```yaml
      ecsModels:
        - modelName: your-model-name
          inferenceContainer: tgi
          baseImage: ghcr.io/huggingface/text-generation-inference:2.0.1
      ```
- If you are deploying the LISA Chat User Interface you can optionally specify the path to the pre-built
  website assets using the top level `webAppAssetsPath` parameter in `config.yaml`. Specifying this path
  (typically `lib/user-interface/react/dist`) will avoid using a container to build and bundle the assets
  at CDK build time.
- For the lambda layers you can specify the path to a local zip archive of the layer code by including
  the optional `lambdaLayerAssets` block in `config.yaml` similar to the following:

```
lambdaLayerAssets:
  authorizerLayerPath: lib/core/layers/authorizer_layer.zip
  commonLayerPath: lib/core/layers/common_layer.zip
  fastapiLayerPath: /path/to/fastapi_layer.zip
  sdkLayerPath: lib/rag/layers/sdk_layer.zip
```
---

## Deploying

Now that we have everything setup we are ready to deploy.

```bash
make deploy
```

By default, all stacks will be deployed but a particular stack can be deployed by providing the `STACK` argument to the `deploy` target.

```bash
make deploy STACK=LisaServe
```

Available stacks can be listed by running:

```bash
make listStacks
```

After the `deploy` command is run, you should see many docker build outputs and eventually a CDK progress bar. The deployment should take about 10-15 minutes and will produce a single cloud formation output for the websocket URL.

You can test the deployment with the integration test:

```bash
pytest lisa-sdk/tests --url <rest-url-from-cdk-output> --verify <path-to-server.crt> | false
```
