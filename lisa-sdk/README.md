## LISA-SDK

Here we provide a tutorial of how to use the LISA SDK that leverages the LISA-serve API. LISA is an enabling service to easily deploy generative AI applications in AWS customer environments. LISA is an open-source infrastructure-as-code offering that is accessible via an API or simple user interface and provides scalable access to generative large language models and embedding language models. In order for the SDK to work properly you will need access to a deployed version of LISA and the websocket url for LISA.

```python
from lisa_sdk import Lisa
url = my_url
```

### Connect to LISA

This will start a long lasting connection with the LISA websocket. Websockets operate somewhat differently from REST APIs. Unlike a REST API, we will have an ongoing connection to LISA.

```python
# Connect to LISA. If this deployment of LISA requires authentication then you will need obtain the token and pass it to LISA.
# for example:
# l = Lisa.from_url(url, token=my_token)
lisa = Lisa.from_url(url)

```

We can get started by listing the actions that the API can perform.

```python
response = lisa.list_actions()
```

    ['listActions',
     'describeApi',
     'listTextGenModels',
     'listEmbeddingModels',
     'embeddings',
     'generate',
     'generateStream']

If we want to know what sorts of parameters are required for each of the action we can use the `describe_api` call.

```python
lisa.describe_api()
```

    [{'action': 'listActions',
      'description': 'No parameters required for this action.'},
     {'action': 'describeApi',
      'description': 'No parameters required for this action.'},
     {'action': 'listTextGenModels',
      'description': 'No parameters required for this action.'},
     {'action': 'listEmbeddingModels',
      'description': 'No parameters required for this action.'},
     {'action': 'embeddings',
      'description': 'Create text embeddings.',
      'parameters': {'provider': {'type': 'string',
        'description': 'The backend provider for the model.'},
       'modelName': {'type': 'string',
        'description': 'The unique identifier for the model to be used.'},
       'text': {'type': 'string',
        'description': 'The input text to be processed by the model.'},
       'modelKwargs': {'type': 'object',
        'description': 'Arguments to the model.'}},
      'required': ['provider', 'modelName', 'text']},
     {'action': 'generate',
      'description': 'Run text generation.',
      'parameters': {'provider': {'type': 'string',
        'description': 'The backend provider for the model.'},
       'modelName': {'type': 'string',
        'description': 'The unique identifier for the model to be used.'},
       'text': {'type': 'string',
        'description': 'The input text to be processed by the model.'},
       'modelKwargs': {'type': 'object',
        'description': 'Arguments to the model.'}},
      'required': ['provider', 'modelName', 'text']},
     {'action': 'generateStream',
      'description': 'Run text generation with streaming.',
      'parameters': {'provider': {'type': 'string',
        'description': 'The backend provider for the model.'},
       'modelName': {'type': 'string',
        'description': 'The unique identifier for the model to be used.'},
       'text': {'type': 'string',
        'description': 'The input text to be processed by the model.'},
       'modelKwargs': {'type': 'object',
        'description': 'Arguments to the model.'}},
      'required': ['provider', 'modelName', 'text']}]

Different deployments of LISA may support different models. Let's see what models we have to work with.

```python
textgen_models = lisa.list_textgen_models()
display(textgen_models)

embedding_models = lisa.list_embedding_models()
display(embedding_models)
```

    [FoundationModel(provider='ecs', model_type='textgen', model_name='falcon-40b-instruct', model_kwargs=TextGenModelKwargs(max_new_tokens=512, top_k=None, top_p=0.95, typical_p=0.95, temperature=0.8, repetition_penalty=None, return_full_text=False, truncate=None, stop_sequences=[], seed=None, timeout=120, streaming=False, do_sample=False, watermark=False))]



    [FoundationModel(provider='ecs', model_type='embedding', model_name='instructor-xl', model_kwargs=ModelKwargs())]

### Generation

Now let's ask Lisa a question!

```python
response = lisa.generate("What is Deep Learning?",
                         model=textgen_models[0],
                         )
print(response)
```

    Deep learning is a subset of machine learning that involves the use of neural networks to learn from large volumes of data. It is a type of AI that is capable of detecting patterns and making predictions based on those patterns. It is widely used in fields such as image and speech recognition, natural language processing, and recommendation systems.

Now let's customize the model kwargs

```python
model_kwargs = textgen_models[0].model_kwargs
model_kwargs.max_new_tokens = 10
model_kwargs.streaming = False
response = lisa.generate("What is Deep Learning?",
                         model=textgen_models[0],
                         model_kwargs=model_kwargs)
print(response)
```

    Deep learning is a subset of machine learning that

### Streaming

Now let's try streaming!

```python
import sys
model_kwargs.max_new_tokens = 512
for tok in lisa.generate_streaming(prompt='\n\nUser:What is Deep Learning\n\nAssistant:', model=textgen_models[0]):
    sys.stdout.write(tok)
    sys.stdout.flush()
```

    Deep Learning is a subset of Machine, where the algorithms learn from large amounts of data to identify patterns and make predictions. It is often used in computer vision, natural language processing and other fields where complex patterns need to be identified.

### Embedding

LISA also serves embedding endpoints. Let's take those for a test drive.

```python
import numpy as np
messages = ["Deep learning is awesome", "Deep learning is vaporware", "Baseball is fun"]
embeddings = [lisa.embed(m, model=embedding_models[0])['content'][0] for m in messages]
print(f"""
The similarity between:

      {messages[0]}

  and

      {messages[1]}

is {np.dot(embeddings[0], embeddings[1])}

The similarity between

      {messages[0]}

  and

      {messages[2]}

is {np.dot(embeddings[0], embeddings[2])}
      """)

```

    The similarity between:

          Deep learning is awesome

      and

          Deep learning is vaporware

    is 0.8169594735548769

    The similarity between

          Deep learning is awesome

      and

          Baseball is fun

    is 0.5663760519293721
