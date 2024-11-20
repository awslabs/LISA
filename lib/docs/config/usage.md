# Usage and Features

The LISA Serve endpoint can be used independently of the Chat UI, and the following shows a few examples of how to do
that. The Serve endpoint
will still validate user auth, so if you have a Bearer token from the IdP configured with LISA, we will honor it, or if
you've set up an API
token using the [DynamoDB instructions](/config/api-tokens), we will also accept that. This diagram shows the LISA Serve
components that
would be utilized during direct REST API requests.

## OpenAI Specification Compatibility

We now provide greater support for the [OpenAI specification](https://platform.openai.com/docs/api-reference) for model
inference and embeddings.
We utilize LiteLLM as a proxy for both models we spin up on behalf of the user and additional models configured through
the config.yaml file, and because of that, the
LISA REST API endpoint allows for a central location for making text generation and embeddings requests. We support, and
are not limited to, the following popular endpoint
routes as long as your underlying models can also respond to them.

- /models
- /chat/completions
- /completions
- /embeddings

By supporting the OpenAI spec, we can more easily allow users to integrate their collection of models into their LLM
applications and workflows. In LISA, users can authenticate
using their OpenID Connect Identity Provider, or with an API token created through the DynamoDB token workflow as
described in [API Tokens](/config/api-tokens). Once the token
is retrieved, users can use that in direct requests to the LISA Serve REST API. If using the IdP, users must set the '
Authorization' header, otherwise if using the API token,
either the 'Api-Key' header or the 'Authorization' header. After that, requests to `https://${lisa_serve_alb}/v2/serve`
will handle the OpenAI API calls. As an example, the following call can list all
models that LISA is aware of, assuming usage of the API token. If you are using a self-signed cert, you must also
provide the `--cacert $path` option to specify a CA bundle to trust for SSL verification.

```shell
curl -s -H 'Api-Key: your-token' -X GET https://${lisa_serve_alb}/v2/serve/models
```

If using the IdP, the request would look like the following:

```shell
curl -s -H 'Authorization: Bearer your-token' -X GET https://${lisa_serve_alb}/v2/serve/models
```

When using a library that requests an OpenAI-compatible base_url, you can provide `https://${lisa_serve_alb}/v2/serve`
here. All of the OpenAI routes will
automatically be added to the base URL, just as we appended `/models` to the `/v2/serve` route for listing all models
tracked by LISA.

## Continue JetBrains and VS Code Plugin

For developers that desire an LLM assistant to help with programming tasks, we support adding LISA as an LLM provider
for the [Continue plugin](https://www.continue.dev).
To add LISA as a provider, open up the Continue plugin's `config.json` file and locate the `models` list. In this list,
add the following block, replacing the placeholder URL
with your own REST API domain or ALB. The `/v2/serve` is required at the end of the `apiBase`. This configuration
requires an API token as created through the [DynamoDB workflow](/config/api-tokens).

```json
{
  "model": "AUTODETECT",
  "title": "LISA",
  "apiBase": "https://<lisa_serve_alb>/v2/serve",
  "provider": "openai",
  "apiKey": "your-api-token"
  // pragma: allowlist-secret
}
```

Once you save the `config.json` file, the Continue plugin will call the `/models` API to get a list of models at your
disposal. The ones provided by LISA will be prefaced
with "LISA" or with the string you place in the `title` field of the config above. Once the configuration is complete
and a model is selected, you can use that model to
generate code and perform AI assistant tasks within your development environment. See
the [Continue documentation](https://docs.continue.dev/how-to-use-continue) for more
information about its features, capabilities, and usage.

### Usage in LLM Libraries

If your workflow includes using libraries, such as [LangChain](https://python.langchain.com/v0.2/docs/introduction/)
or [OpenAI](https://github.com/openai/openai-python),
then you can place LISA right in your application by changing only the endpoint and headers for the client objects. As
an example, using the OpenAI library, the client would
normally be instantiated and invoked with the following block.

```python
from openai import OpenAI

client = OpenAI(
    api_key="my_key"  # pragma: allowlist-secret not a real key
)
client.models.list()
```

To use the models being served by LISA, the client needs only a few changes:

1. Specify the `base_url` as the LISA Serve ALB, using the /v2/serve route at the end, similar to the apiBase in
   the [Continue example](#continue-jetbrains-and-vs-code-plugin)
2. Add the API key that you generated from the [token generation steps](/config/api-tokens) as your `api_key` field.
3. If using a self-signed cert, you must provide a certificate path for validating SSL. If you're using an ACM or public
   cert, then this may be omitted.
1. We provide a convenience function in the `lisa-sdk` for generating a cert path from an IAM certificate ARN if one is
   provided in the `RESTAPI_SSL_CERT_ARN` environment variable.

The Code block will now look like this and you can continue to use the library without any other modifications.

```python
# for self-signed certificates
import boto3
from lisapy.utils import get_cert_path
# main client library
from openai import DefaultHttpxClient, OpenAI

iam_client = boto3.client("iam")
cert_path = get_cert_path(iam_client)

client = OpenAI(
    api_key="my_key", # pragma: allowlist-secret not a real key
    base_url="https://<lisa_serve_alb>/v2/serve",
    http_client=DefaultHttpxClient(verify=cert_path), # needed for self-signed certs on your ALB, can be omitted otherwise
)
client.models.list()