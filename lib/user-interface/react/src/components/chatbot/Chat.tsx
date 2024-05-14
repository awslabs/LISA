import { useState, useRef, useCallback, useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import Form from '@cloudscape-design/components/form';
import Button from '@cloudscape-design/components/button';
import Container from '@cloudscape-design/components/container';
import TextareaAutosize from 'react-textarea-autosize';
import Box from '@cloudscape-design/components/box';
import { v4 as uuidv4 } from 'uuid';
import Select from '@cloudscape-design/components/select';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Modal from '@cloudscape-design/components/modal';
import Input from '@cloudscape-design/components/input';
import FormField from '@cloudscape-design/components/form-field';
import Toggle from '@cloudscape-design/components/toggle';
import {
  Alert,
  ColumnLayout,
  ExpandableSection,
  FileUpload,
  Flashbar,
  Grid,
  Header,
  ProgressBar,
  TextContent,
  Textarea,
} from '@cloudscape-design/components';
import { SelectProps } from '@cloudscape-design/components/select';
import StatusIndicator from '@cloudscape-design/components/status-indicator';

import Message from './Message';
import {
  LisaChatMessage,
  LisaChatSession,
  ModelProvider,
  Model,
  ModelKwargs,
  LisaChatMessageMetadata,
  FileTypes,
  StatusTypes,
} from '../types';
import {
  getSession,
  putSession,
  describeModels,
  isModelInterfaceHealthy,
  RESTAPI_URI,
  RESTAPI_VERSION,
  listRagRepositories,
  getPresignedUrl,
  uploadToS3,
  ingestDocuments,
  parseDescribeModelsResponse,
  formatDocumentsAsString,
} from '../utils';
import { Lisa, LisaContentHandler, LisaRAGRetriever } from '../adapters/lisa';
import { LisaChatMessageHistory } from '../adapters/lisa-chat-history';
import ModelKwargsEditor from './ModelKwargs';
import { PromptTemplate } from '@langchain/core/prompts';
import { RunnableSequence } from '@langchain/core/runnables';
import { StringOutputParser } from '@langchain/core/output_parsers';
import { BufferWindowMemory } from 'langchain/memory';

export default function Chat({ sessionId }) {
  const [userPrompt, setUserPrompt] = useState('');
  const [humanPrefix, setHumanPrefix] = useState('User');
  const [aiPrefix, setAiPrefix] = useState('Assistant');
  const [fileContext, setFileContext] = useState('');
  const [promptTemplate, setPromptTemplate] = useState(
    `The following is a friendly conversation between a human and an AI. The AI is talkative and provides lots of specific details from its context. If the AI does not know the answer to a question, it truthfully says it does not know.

          Current conversation:
          {history}
          ${humanPrefix}: {input}
          ${aiPrefix}:`,
  );
  const [modelProviders, setModelProviders] = useState<ModelProvider[]>([]);
  const [embeddingModelProviders, setEmbeddingModelProviders] = useState<ModelProvider[]>([]);
  const [modelsOptions, setModelsOptions] = useState<SelectProps.Options>([]);
  const [embeddingOptions, setEmbeddingOptions] = useState<SelectProps.Options>([]);
  const [repositoryOptions, setRepositoryOptions] = useState<SelectProps.Options>([]);
  const [textgenModelMap, setTextgenModelMap] = useState<Map<string, Model> | undefined>(undefined);
  const [embeddingModelMap, setEmbeddingModelMap] = useState<Map<string, Model> | undefined>(undefined);
  const [modelKwargs, setModelKwargs] = useState<ModelKwargs | undefined>(undefined);
  const [selectedModel, setSelectedModel] = useState<Model | undefined>(undefined);
  const [selectedModelOption, setSelectedModelOption] = useState<SelectProps.Option | undefined>(undefined);
  const [selectedEmbeddingOption, setSelectedEmbeddingOption] = useState<SelectProps.Option | undefined>(undefined);
  const [selectedRepositoryOption, setSelectedRepositoryOption] = useState<SelectProps.Option | undefined>(undefined);
  const [session, setSession] = useState<LisaChatSession>({
    history: [],
    sessionId: '',
    userId: '',
    startTime: new Date(Date.now()).toISOString(),
  });
  const [chain, setChain] = useState<RunnableSequence | undefined>(undefined);
  const [streamingEnabled, setStreamingEnabled] = useState(false);
  const [chatHistoryBufferSize, setChatHistoryBufferSize] = useState<number>(3);
  const [modelCanStream, setModelCanStream] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [isLoadingEmbeddingModels, setIsLoadingEmbeddingModels] = useState(false);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(false);
  const [metadata, setMetadata] = useState<LisaChatMessageMetadata>({});
  const [showMetadata, setShowMetadata] = useState(false);
  const [internalSessionId, setInternalSessionId] = useState<string | null>(null);
  const [modelKwargsModalVisible, setModelKwargsModalVisible] = useState(false);
  const [promptTemplateModalVisible, setPromptTemplateModalVisible] = useState(false);
  const [fileContextModalVisible, setFileContextModalVisible] = useState(false);
  const [ragUploadModalVisible, setRAGUploadModalVisible] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [flashbarItems, setFlashbarItems] = useState([]);
  const [displayProgressBar, setDisplayProgressBar] = useState(false);
  const [progressBarValue, setProgressBarValue] = useState(0);
  const [progressBarDescription, setProgressBarDescription] = useState('');
  const [progressBarLabel, setProgressBarLabel] = useState('');
  const [alerts, setAlerts] = useState<string[] | undefined>([]);
  const [ingestingFiles, setIngestingFiles] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState('');
  const [ingestionType, setIngestionType] = useState(StatusTypes.LOADING);
  const [repositoryMap, setRepositoryMap] = useState(new Map());
  const [ragContext, setRagContext] = useState('');
  const [useRag, setUseRag] = useState(false);
  const [memory, setMemory] = useState(
    new BufferWindowMemory({
      chatHistory: new LisaChatMessageHistory(session),
      returnMessages: false,
      memoryKey: 'history',
      k: chatHistoryBufferSize,
      aiPrefix: aiPrefix,
      humanPrefix: humanPrefix,
    }),
  );
  const [chunkSize, setChunkSize] = useState(512);
  const [chunkOverlap, setChunkOverlap] = useState(51);
  const bottomRef = useRef(null);
  const auth = useAuth();

  useEffect(() => {
    describeTextGenModels();
    describeEmbeddingModels();
    describeRagRepositories();
    isBackendHealthy().then((flag) => setIsConnected(flag));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedModelOption) {
      const model = textgenModelMap[selectedModelOption.value];
      setModelCanStream(model.streaming);
      setSelectedModel(model);
      // TODO: the backend should set more reasonable default modelkwargs for chat
      // until then, we won't use them as defaults in the UI
      // setModelKwargs(model.modelKwargs);
      updateModelKwargs('streaming', streamingEnabled);
    }
  }, [selectedModelOption, textgenModelMap, streamingEnabled]);

  useEffect(() => {
    setModelsOptions(createModelOptions(modelProviders));
    setTextgenModelMap(createModelMap(modelProviders));
    // Disabling exhaustive-deps here because we only want to update
    // the textgenModelMap and modelOptions when modelProviders changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelProviders]);

  useEffect(() => {
    setEmbeddingOptions(createModelOptions(embeddingModelProviders));
    setEmbeddingModelMap(createModelMap(embeddingModelProviders));
    // Disabling exhaustive-deps here because we only want to update
    // the embeddingModelMap and embeddingOptions when embeddingModelProviders changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [embeddingModelProviders]);

  useEffect(() => {
    if (modelKwargs) {
      updateModelKwargs('streaming', streamingEnabled);
    }
    // Disabling exhaustive-deps here because we are updating modelKwargs so we can't trigger
    // this on modelKwargs updating or we would end up in a render loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamingEnabled]);

  useEffect(() => {
    if (selectedModel) {
      selectedModel.modelKwargs = modelKwargs;
      setSelectedModel(selectedModel);
    }
  }, [modelKwargs, selectedModel]);

  useEffect(() => {
    if (!isRunning && session.history.length) {
      if (session.history.at(-1).type == 'ai' && !auth.isLoading) {
        putSession(session, auth.user?.id_token);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRunning, session, auth.isLoading]);

  useEffect(() => {
    if (sessionId) {
      setInternalSessionId(sessionId);
      getSession(sessionId, auth.user?.id_token).then((sess) => {
        // session doesn't exist so we create it
        if (sess.history == undefined) {
          sess = {
            history: [],
            sessionId: sessionId,
            userId: auth.user?.profile.sub,
            startTime: new Date(Date.now()).toISOString(),
          };
        }
        setSession(sess);
      });
    } else {
      const newSessionId = uuidv4();
      setInternalSessionId(newSessionId);
      const newSession = {
        history: [],
        sessionId: newSessionId,
        userId: auth.user?.profile.sub,
        startTime: new Date(Date.now()).toISOString(),
      };
      setSession(newSession);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    const promptNeedsContext = fileContext || (selectedEmbeddingOption && selectedRepositoryOption);
    const promptIncludesContext = promptTemplate.indexOf('{context}') > -1;

    setUseRag(!!selectedEmbeddingOption && !!selectedRepositoryOption);

    if (promptNeedsContext && !promptIncludesContext) {
      // Add context parameter to prompt if using local file context or RAG
      // New lines included to maintain formatting in the prompt template UI
      const modifiedText = promptTemplate.replace(
        `
          Current conversation:`,
        ` {context}

          Current conversation:`,
      );
      setPromptTemplate(modifiedText);
    } else if (!promptNeedsContext && promptIncludesContext) {
      // Remove context from the prompt
      const modifiedText = promptTemplate.replace('{context}', '');
      setPromptTemplate(modifiedText);
    }
    // Disabling exhaustive-deps here because we are updating the promptTemplate so we can't trigger
    // this on promptTemplate updating or we would end up in a render loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileContext, selectedRepositoryOption, selectedEmbeddingOption]);

  useEffect(() => {
    if (selectedModel && !isRunning) {
      setMemory(
        new BufferWindowMemory({
          chatHistory: new LisaChatMessageHistory(session),
          returnMessages: false,
          memoryKey: 'history',
          k: chatHistoryBufferSize,
          aiPrefix: aiPrefix,
          humanPrefix: humanPrefix,
        }),
      );
      const llm = new Lisa({
        uri: `${RESTAPI_URI}/${RESTAPI_VERSION}`,
        idToken: auth.user?.id_token,
        modelName: selectedModel.modelName,
        providerName: selectedModel.provider,
        modelKwargs: modelKwargs,
        streaming: streamingEnabled,
        contentHandler: new LisaContentHandler(),
        callbacks: [
          {
            handleLLMNewToken: async (token) => {
              setSession((prev) => {
                const lastMessage = prev.history[prev.history.length - 1];
                const newMessage = new LisaChatMessage({
                  ...lastMessage,
                  content: lastMessage.content + token,
                });
                return {
                  ...prev,
                  history: prev.history.slice(0, -1).concat(newMessage),
                };
              });
            },
          },
        ],
      });
      const useContext = fileContext || useRag;
      const inputVariables = ['history', 'input'];

      if (useContext) {
        inputVariables.push('context');
      }
      const questionPrompt = new PromptTemplate({
        template: promptTemplate,
        inputVariables: inputVariables,
      });

      if (useRag) {
        const embeddingModel = embeddingModelMap[selectedEmbeddingOption.value];
        const retriever = new LisaRAGRetriever({
          uri: '/',
          idToken: auth.user?.id_token,
          repositoryId: selectedRepositoryOption.value,
          repositoryType: repositoryMap.get(selectedRepositoryOption.value),
          modelName: embeddingModel.modelName,
          providerName: embeddingModel.provider,
        });

        const chain = RunnableSequence.from([
          {
            input: (input: { input: string; chatHistory?: string }) => input.input,
            chatHistory: () => memory.loadMemoryVariables({}),
            context: async (input: { input: string; chatHistory?: string }) => {
              const relevantDocs = await retriever._getRelevantDocuments(input.input);
              const serialized = `${fileContext}\n${formatDocumentsAsString(relevantDocs)}`;
              setRagContext(serialized);
              setSession((prev) => {
                const lastMessage = prev.history[prev.history.length - 1];
                const newMessage = new LisaChatMessage({
                  ...lastMessage,
                  metadata: {
                    ...lastMessage.metadata,
                    ragContext: formatDocumentsAsString(relevantDocs, true),
                  },
                });
                return {
                  ...prev,
                  history: prev.history.slice(0, -1).concat(newMessage),
                };
              });
              return serialized;
            },
          },
          {
            input: (previousOutput) => previousOutput.input,
            context: (previousOutput) => previousOutput.context,
            history: (previousOutput) => previousOutput.chatHistory.history,
          },
          questionPrompt,
          llm,
          new StringOutputParser(),
        ]);
        setChain(chain);
      } else if (useContext) {
        const chain = RunnableSequence.from([
          {
            input: (initialInput) => initialInput.input,
            memory: () => memory.loadMemoryVariables({}),
            context: () => fileContext,
          },
          {
            input: (previousOutput) => previousOutput.input,
            context: (previousOutput) => previousOutput.context,
            history: (previousOutput) => previousOutput.memory.history,
          },
          questionPrompt,
          llm,
          new StringOutputParser(),
        ]);
        setChain(chain);
      } else {
        const chain = RunnableSequence.from([
          {
            input: (initialInput) => initialInput.input,
            memory: () => memory.loadMemoryVariables({}),
          },
          {
            input: (previousOutput) => previousOutput.input,
            history: (previousOutput) => previousOutput.memory.history,
          },
          questionPrompt,
          llm,
          new StringOutputParser(),
        ]);
        setChain(chain);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    selectedModel,
    useRag,
    modelKwargs,
    streamingEnabled,
    promptTemplate,
    aiPrefix,
    humanPrefix,
    isRunning,
    session,
    chatHistoryBufferSize,
  ]);

  useEffect(() => {
    if (selectedModel && auth.isAuthenticated && chain) {
      memory.loadMemoryVariables({}).then(async (formattedHistory) => {
        const promptValues = {
          input: userPrompt,
          history: formattedHistory.history,
        };
        // If context is included in template then add value here
        if (promptTemplate.indexOf('{context}') > -1) {
          if (useRag) {
            promptValues['context'] = ragContext;
          } else {
            promptValues['context'] = fileContext;
          }
        }
        const prompt = await PromptTemplate.fromTemplate(promptTemplate).format(promptValues);
        const metadata: LisaChatMessageMetadata = {
          modelName: selectedModel.modelName,
          modelKwargs: modelKwargs,
          userId: auth.user.profile.sub,
          prompt,
        };
        setMetadata(metadata);
      });
    }
  }, [selectedModel, modelKwargs, auth, chain, userPrompt]);

  useEffect(() => {
    if (bottomRef) {
      bottomRef?.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [session]);

  const isBackendHealthy = useCallback(async () => {
    return isModelInterfaceHealthy(auth.user?.id_token);
  }, []);

  const createFlashbarError = () => {
    return {
      header: 'Something Went Wrong',
      type: 'error',
      content: 'An error occurred while processing your request.',
      dismissible: true,
      dismissLabel: 'Dismiss message',
      onDismiss: () => {
        setFlashbarItems([]);
      },
      id: 'error_message',
    };
  };

  const processFileUpload = async (allowedFileTypes: FileTypes[], fileSizeLimit: number, isFileContext: boolean) => {
    if (selectedFiles.length > 0) {
      const successfulUploads: string[] = [];

      for (const file of selectedFiles) {
        setProgressBarDescription(`Uploading ${file.name}`);
        let fileIsValid = true;
        let error = '';
        if (!allowedFileTypes.includes(file.type as FileTypes)) {
          error = `${file.name} has an unsupported file type for this operation. `;
          fileIsValid = false;
        }
        if (file.size > fileSizeLimit) {
          error += `File ${file.name} is too big for this operation. Max file size is ${fileSizeLimit}`;
          fileIsValid = false;
        }

        if (fileIsValid) {
          if (isFileContext) {
            //File context currently only supports single files
            await file.text().then((fileContext) => {
              setFileContext(`File context: ${fileContext}`);
            });
            setSelectedFiles([file]);
          } else {
            try {
              const urlResponse = await getPresignedUrl(auth.user?.id_token, file.name);
              const s3UploadStatusCode = await uploadToS3(urlResponse, file);

              if (s3UploadStatusCode === 204) {
                successfulUploads.push(file.name);
                setProgressBarValue((selectedFiles.length / successfulUploads.length) * 100);
              } else {
                throw new Error(`File ${file.name} failed to upload.`);
              }
            } catch (err) {
              setAlerts((oldItems) => [...oldItems, `Error encountered while uploading file ${file.name}`]);
            }
          }
        }
        if (error) {
          setAlerts((oldItems) => [...oldItems, error]);
        }
      }
      setDisplayProgressBar(false);
      if (!isFileContext && successfulUploads.length > 0) {
        setIngestingFiles(true);
        setIngestionType(StatusTypes.LOADING);
        setIngestionStatus('Ingesting documents into RAG...');
        try {
          // Ingest all of the documents which uploaded successfully

          const ingestResponseStatusCode = await ingestDocuments(
            auth.user?.id_token,
            successfulUploads,
            selectedRepositoryOption.value,
            embeddingModelMap[selectedEmbeddingOption.value],
            repositoryMap.get(selectedRepositoryOption.value),
            chunkSize,
            chunkOverlap,
          );
          if (ingestResponseStatusCode === 200) {
            setIngestionType(StatusTypes.SUCCESS);
            setIngestionStatus('Successly ingested documents into RAG');
            setFlashbarItems((oldItems) => [
              ...oldItems,
              {
                header: 'Success',
                type: 'success',
                content: `Successly ingested ${successfulUploads.length} document(s) into the selected RAG repository.`,
                dismissible: true,
                dismissLabel: 'Dismiss message',
                onDismiss: () => {
                  setFlashbarItems([]);
                },
                id: 'rag_success',
              },
            ]);
            setRAGUploadModalVisible(false);
          } else {
            throw new Error('Failed to ingest documents into RAG');
          }
        } catch (err) {
          setIngestionType(StatusTypes.ERROR);
          setIngestionStatus('Failed to ingest documents into RAG');
        } finally {
          setIngestingFiles(false);
        }
      }
    }
  };

  const handleSendGenerateRequest = useCallback(async () => {
    const userMessage = new LisaChatMessage({
      type: 'human',
      content: userPrompt,
      metadata: {},
    });
    setSession((prev) => ({
      ...prev,
      history: prev.history.concat(userMessage),
    }));

    setIsRunning(true);
    const inputs = {
      input: userPrompt,
    };
    if (streamingEnabled) {
      setIsStreaming(true);
      setSession((prev) => ({
        ...prev,
        history: prev.history.concat(
          new LisaChatMessage({
            type: 'ai',
            content: '',
            metadata: metadata,
          }),
        ),
      }));
      try {
        const result = await chain.invoke({
          input: userPrompt,
        });
        await memory.saveContext(inputs, {
          output: result,
        });
      } catch (exception) {
        setFlashbarItems((oldItems) => [...oldItems, createFlashbarError()]);
      }

      setIsStreaming(false);
    } else {
      try {
        const result = await chain.invoke(inputs);
        await memory.saveContext(inputs, {
          output: result,
        });
        setSession((prev) => ({
          ...prev,
          history: prev.history.concat(
            new LisaChatMessage({
              type: 'ai',
              content: result,
              metadata: metadata,
            }),
          ),
        }));
      } catch (exception) {
        setFlashbarItems((oldItems) => [...oldItems, createFlashbarError()]);
      }
    }

    setIsRunning(false);
    setUserPrompt('');
  }, [chain, userPrompt, metadata, streamingEnabled]);

  const describeTextGenModels = useCallback(async () => {
    setIsLoadingModels(true);
    const resp = await describeModels(['textgen'], auth.user?.id_token);
    setModelProviders(parseDescribeModelsResponse(resp, 'textgen'));
    setIsLoadingModels(false);
  }, []);

  const describeEmbeddingModels = useCallback(async () => {
    setIsLoadingEmbeddingModels(true);
    const resp = await describeModels(['embedding'], auth.user?.id_token);
    setEmbeddingModelProviders(parseDescribeModelsResponse(resp, 'embedding'));
    setIsLoadingEmbeddingModels(false);
  }, []);

  const describeRagRepositories = useCallback(async () => {
    setIsLoadingRepositories(true);
    const repositories = await listRagRepositories(auth.user?.id_token);
    setRepositoryOptions(
      repositories.map((repo) => {
        setRepositoryMap((map) => new Map(map.set(repo.repositoryId, repo.type)));
        return {
          label: `${repo.repositoryId} (${repo.type})`,
          value: repo.repositoryId,
        };
      }),
    );
    setIsLoadingRepositories(false);
  }, []);

  const formatModelKey = (providerName: string, modelName: string): string => {
    return `${providerName}.${modelName}`;
  };

  const createModelOptions = (providers: ModelProvider[]): SelectProps.Options => {
    const optionGroups: SelectProps.OptionGroup[] = [];
    for (const modelProvider of providers) {
      const options: SelectProps.Option[] = [];
      for (const model of modelProvider.models) {
        const modelKey = formatModelKey(modelProvider.name, model.modelName);
        let label = '';
        if (model.modelType === 'textgen') {
          label = `${model.modelName} ${model.streaming ? '(streaming supported)' : ''}`;
        } else if (model.modelType === 'embedding') {
          label = `${model.modelName}`;
        }
        options.push({
          label,
          value: modelKey,
        });
      }
      optionGroups.push({
        label: modelProvider.name,
        options: options,
      });
    }
    return optionGroups;
  };

  const createModelMap = (providers: ModelProvider[]): Map<string, Model> => {
    const modelMap: Map<string, Model> = new Map<string, Model>();
    for (const modelProvider of providers) {
      for (const model of modelProvider.models) {
        modelMap[formatModelKey(modelProvider.name, model.modelName)] = model;
      }
    }
    return modelMap;
  };

  const updateModelKwargs = (key, value) => {
    setModelKwargs((prevModelKwargs) => ({
      ...prevModelKwargs,
      [key]: value,
    }));
  };

  return (
    <>
      <ModelKwargsEditor
        setModelKwargs={setModelKwargs}
        visible={modelKwargsModalVisible}
        setVisible={setModelKwargsModalVisible}
      />
      <Modal
        onDismiss={() => setPromptTemplateModalVisible(false)}
        visible={promptTemplateModalVisible}
        header="Prompt Editor"
        footer=""
        size="large"
      >
        <TextContent>
          <h4>Prompt Template</h4>
          <p>
            <small>
              Sets the prompt used in a LangChain ConversationChain to converse with an LLM. The <code>`history`</code>{' '}
              and <code>`input`</code> keys are available for use in the prompt like:
              <br />
              <br />
              <code>
                ```
                <br />
                Current conversation:
                <br />
                &#123;history&#125;
                <br />
                ```
              </code>
            </small>
          </p>
        </TextContent>
        <SpaceBetween direction="vertical" size="xs">
          <Textarea
            rows={10}
            disableBrowserAutocorrect={false}
            autoFocus
            onChange={(e) => setPromptTemplate(e.detail.value)}
            onKeyDown={(e) => {
              if (e.detail.key == 'Enter' && !e.detail.shiftKey) {
                e.preventDefault();
              }
            }}
            value={promptTemplate}
          />
          <FormField description="Sets the prefix representing the user in the LLM prompt." label="Human Prefix">
            <Input
              value={humanPrefix}
              onChange={(e) => setHumanPrefix(e.detail.value)}
              onKeyDown={(e) => {
                if (e.detail.key == 'Enter' && !e.detail.shiftKey) {
                  e.preventDefault();
                }
              }}
            />
          </FormField>
          <FormField description="Sets the prefix representing the AI in the LLM prompt." label="AI Prefix">
            <Input
              value={aiPrefix}
              onChange={(e) => setAiPrefix(e.detail.value)}
              onKeyDown={(e) => {
                if (e.detail.key == 'Enter' && !e.detail.shiftKey) {
                  e.preventDefault();
                }
              }}
            />
          </FormField>
        </SpaceBetween>
      </Modal>
      <Modal
        onDismiss={() => {
          setFileContextModalVisible(false);
          setSelectedFiles([]);
          setAlerts([]);
        }}
        visible={fileContextModalVisible}
        header="Manage File Context"
        size="large"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button
                onClick={async () => {
                  setAlerts([]);
                  await processFileUpload([FileTypes.TEXT], 10240, true);
                  if (alerts.length === 0) {
                    setFileContextModalVisible(false);
                    setSelectedFiles([]);
                  }
                }}
                disabled={selectedFiles.length === 0}
              >
                Set file context
              </Button>
              <Button
                onClick={() => {
                  setFileContextModalVisible(false);
                  setFileContext('');
                  setSelectedFiles([]);
                  setAlerts([]);
                }}
                disabled={!fileContext}
              >
                Clear file context
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween direction="vertical" size="s">
          <TextContent>
            <h4>File Context</h4>
            <p>
              <small>
                Upload files for LISA to use as context in this session. This additional context will be referenced to
                answer your questions.
              </small>
            </p>
          </TextContent>
          <FileUpload
            onChange={({ detail }) => setSelectedFiles(detail.value)}
            value={selectedFiles}
            i18nStrings={{
              uploadButtonText: (e) => (e ? 'Choose files' : 'Choose file'),
              dropzoneText: (e) => (e ? 'Drop files to upload' : 'Drop file to upload'),
              removeFileAriaLabel: (e) => `Remove file ${e + 1}`,
              limitShowFewer: 'Show fewer files',
              limitShowMore: 'Show more files',
              errorIconAriaLabel: 'Error',
            }}
            showFileSize
            tokenLimit={3}
            constraintText="Allowed file type is plain text. File size limit is 10 KB"
          />
          {alerts.map(function (error: string) {
            if (error !== '') {
              return (
                <Alert
                  type="error"
                  statusIconAriaLabel="Error"
                  header="File upload error:"
                  dismissible
                  onDismiss={() => {
                    setAlerts([]);
                  }}
                >
                  {error}
                </Alert>
              );
            }
          })}
        </SpaceBetween>
      </Modal>
      <Modal
        onDismiss={() => {
          setRAGUploadModalVisible(false);
          setSelectedFiles([]);
          setAlerts([]);
          setIngestingFiles(false);
        }}
        visible={ragUploadModalVisible}
        header="Upload to RAG"
        size="large"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button
                onClick={async () => {
                  setAlerts([]);
                  //Initialize the progress bar values
                  setProgressBarLabel('Uploading files to S3');
                  setDisplayProgressBar(true);
                  setProgressBarValue(0);

                  //Allowed file types are plain text, docx, and pdf. File size limit is 50 MB
                  await processFileUpload([FileTypes.TEXT, FileTypes.DOCX, FileTypes.PDF], 52428800, false);
                  if (alerts.length === 0) {
                    setRAGUploadModalVisible(false);
                    setSelectedFiles([]);
                  }
                }}
                disabled={selectedFiles.length === 0}
              >
                Upload
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween direction="vertical" size="s">
          <TextContent>
            <h4>Upload to RAG</h4>
            <p>
              <small>
                Upload files to the RAG repository leveraged by LISA. This will provide LISA with trusted information
                for answering prompts.
              </small>
            </p>
          </TextContent>
          <Grid gridDefinition={[{ colspan: { default: 12, xxs: 6 } }, { colspan: { default: 12, xxs: 6 } }]}>
            <FormField label="Chunk Size" description="Size of chunks that will be persisted in the RAG repository">
              <Input
                value={chunkSize.toString()}
                type="number"
                step={1}
                inputMode="numeric"
                disableBrowserAutocorrect={true}
                onChange={(event) => {
                  const intVal = parseInt(event.detail.value);
                  if (intVal >= 0) {
                    setChunkSize(intVal);
                  }
                }}
              />
            </FormField>
            <FormField label="Chunk Overlap" description="Size of the overlap used when generating content chunks">
              <Input
                value={chunkOverlap.toString()}
                type="number"
                step={1}
                inputMode="numeric"
                disableBrowserAutocorrect={true}
                onChange={(event) => {
                  const intVal = parseInt(event.detail.value);
                  if (intVal >= 0) {
                    setChunkOverlap(intVal);
                  }
                }}
              />
            </FormField>
          </Grid>
          <FileUpload
            onChange={({ detail }) => setSelectedFiles(detail.value)}
            value={selectedFiles}
            multiple
            i18nStrings={{
              uploadButtonText: (e) => (e ? 'Choose files' : 'Choose file'),
              dropzoneText: (e) => (e ? 'Drop files to upload' : 'Drop file to upload'),
              removeFileAriaLabel: (e) => `Remove file ${e + 1}`,
              limitShowFewer: 'Show fewer files',
              limitShowMore: 'Show more files',
              errorIconAriaLabel: 'Error',
            }}
            showFileSize
            tokenLimit={3}
            constraintText="Allowed file types are plain text, PDF, and docx. File size limit is 50 MB"
          />
          {alerts.map(function (error: string) {
            if (error !== '') {
              return (
                <Alert
                  type="error"
                  statusIconAriaLabel="Error"
                  header="File upload error:"
                  dismissible
                  onDismiss={() => {
                    setAlerts([]);
                  }}
                >
                  {error}
                </Alert>
              );
            }
          })}
          {displayProgressBar && (
            <ProgressBar
              status="in-progress"
              value={progressBarValue}
              description={progressBarDescription}
              label={progressBarLabel}
            />
          )}
          {ingestingFiles && <StatusIndicator type={ingestionType}>{ingestionStatus}</StatusIndicator>}
        </SpaceBetween>
      </Modal>
      <div className=" overflow-y-auto p-2 mb-96">
        <SpaceBetween direction="vertical" size="xs">
          {session.history.map((message, idx) => (
            <Message key={idx} message={message} showMetadata={showMetadata} isRunning={false} />
          ))}
          <div ref={bottomRef} />
          <Flashbar items={flashbarItems} />
          {isRunning && !isStreaming && <Message isRunning={isRunning} />}
        </SpaceBetween>
      </div>
      <div className="fixed bottom-0 left-0 w-full">
        <form onSubmit={(e) => e.preventDefault()}>
          <Form variant="embedded">
            <Container>
              <SpaceBetween size="m" direction="vertical">
                <div className="flex">
                  <div className="w-2/4">
                    <TextareaAutosize
                      className="float-left  min-w-[300px] w-2/3 border-none rounded-md p-2 focus:outline-none focus:ring-none bg-transparent resize-none p-5"
                      maxRows={4}
                      minRows={1}
                      spellCheck={true}
                      placeholder={
                        !selectedModel ? 'You must select a model before sending a message' : 'Send a message'
                      }
                      disabled={!selectedModel}
                      onChange={(e) => setUserPrompt(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key == 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSendGenerateRequest();
                        }
                      }}
                      value={userPrompt}
                    />
                  </div>
                  <div className="w-2/4">
                    <div className="flex mb-2 justify-end mt-3">
                      <div>
                        <Button
                          disabled={!modelProviders.length || isRunning || !selectedModel || userPrompt === ''}
                          onClick={handleSendGenerateRequest}
                          iconAlign="right"
                          iconName="angle-right-double"
                          variant="primary"
                        >
                          <span className="md:inline hidden">{isRunning ? 'Loading' : 'Send'}</span>
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
                <Container
                  variant="stacked"
                  header={
                    <Header
                      variant="h2"
                      description={`Select the model to use for this chat session.${
                        window.env.RAG_ENABLED &&
                        'Optionally select a RAG repository and embedding model to use when chatting.'
                      }`}
                      actions={
                        <SpaceBetween direction="horizontal" size="m">
                          <Box float="left" variant="div">
                            <Button
                              onClick={() => setFileContextModalVisible(true)}
                              disabled={isRunning || !selectedModelOption}
                            >
                              Manage file context
                            </Button>
                          </Box>
                          <Box float="left" variant="div">
                            <Button
                              onClick={() => setRAGUploadModalVisible(true)}
                              disabled={
                                isRunning ||
                                selectedRepositoryOption === undefined ||
                                selectedEmbeddingOption === undefined
                              }
                            >
                              Upload files to RAG
                            </Button>
                          </Box>
                        </SpaceBetween>
                      }
                    >
                      Model configuration
                    </Header>
                  }
                >
                  <SpaceBetween size="l" direction="vertical">
                    <Grid
                      gridDefinition={[
                        { colspan: { default: 10, xxs: 3 } },
                        { colspan: { default: 2, xxs: 1 } },
                        { colspan: { default: 12, xxs: 3 } },
                        { colspan: { default: 2, xxs: 1 } },
                        { colspan: { default: 12, xxs: 3 } },
                        { colspan: { default: 2, xxs: 1 } },
                      ]}
                    >
                      <Select
                        disabled={isRunning}
                        statusType={isLoadingModels ? 'loading' : 'finished'}
                        loadingText="Loading models (might take few seconds)..."
                        placeholder="Select a model"
                        empty={<div className="text-gray-500">No models available.</div>}
                        filteringType="auto"
                        selectedOption={selectedModelOption}
                        onChange={({ detail }) => setSelectedModelOption(detail.selectedOption)}
                        options={modelsOptions}
                      />
                      <div style={{ paddingTop: 4 }}>
                        <Toggle
                          onChange={({ detail }) => setStreamingEnabled(detail.checked)}
                          checked={streamingEnabled}
                          disabled={!modelCanStream || isRunning}
                        >
                          Streaming
                        </Toggle>
                      </div>
                      {window.env.RAG_ENABLED && (
                        <>
                          <Select
                            disabled={isRunning}
                            statusType={isLoadingRepositories ? 'loading' : 'finished'}
                            loadingText="Loading repositories (might take few seconds)..."
                            placeholder="Select a RAG Repository"
                            empty={<div className="text-gray-500">No repositories available.</div>}
                            filteringType="auto"
                            selectedOption={selectedRepositoryOption}
                            onChange={({ detail }) => setSelectedRepositoryOption(detail.selectedOption)}
                            options={repositoryOptions}
                          />
                          <Button
                            disabled={selectedRepositoryOption === undefined}
                            onClick={() => setSelectedRepositoryOption(undefined)}
                          >
                            Clear
                          </Button>
                          <Select
                            disabled={isRunning}
                            statusType={isLoadingEmbeddingModels ? 'loading' : 'finished'}
                            loadingText="Loading embedding models (might take few seconds)..."
                            placeholder="Select an embedding model"
                            empty={<div className="text-gray-500">No embedding models available.</div>}
                            filteringType="auto"
                            selectedOption={selectedEmbeddingOption}
                            onChange={({ detail }) => setSelectedEmbeddingOption(detail.selectedOption)}
                            options={embeddingOptions}
                          />
                          <Button
                            disabled={selectedEmbeddingOption === undefined}
                            onClick={() => setSelectedEmbeddingOption(undefined)}
                          >
                            Clear
                          </Button>
                        </>
                      )}
                    </Grid>
                    <ExpandableSection headerText="Advanced configuration" variant="footer">
                      <ColumnLayout columns={5}>
                        <Toggle onChange={({ detail }) => setShowMetadata(detail.checked)} checked={showMetadata}>
                          Show metadata
                        </Toggle>
                        <Button onClick={() => setModelKwargsModalVisible(true)}>Edit Model Kwargs</Button>
                        <Button onClick={() => setPromptTemplateModalVisible(true)}>Edit Prompt Template</Button>
                        <Box float="left" textAlign="center" variant="awsui-key-label" padding={{ vertical: 'xxs' }}>
                          Chat history buffer size:
                        </Box>
                        <Box float="left" variant="div">
                          <Select
                            disabled={isRunning}
                            filteringType="auto"
                            selectedOption={{
                              value: chatHistoryBufferSize.toString(),
                              label: chatHistoryBufferSize.toString(),
                            }}
                            onChange={({ detail }) => setChatHistoryBufferSize(parseInt(detail.selectedOption.value))}
                            options={[...Array(10).keys()].map((i) => {
                              i = i + 1;
                              return {
                                value: i.toString(),
                                label: i.toString(),
                              };
                            })}
                          />
                        </Box>
                      </ColumnLayout>
                    </ExpandableSection>
                  </SpaceBetween>
                </Container>
                <SpaceBetween direction="vertical" size="xs">
                  <Box float="right" variant="div">
                    <StatusIndicator type={isConnected ? 'success' : 'error'}>
                      {isConnected ? 'Connected' : 'Disconnected'}
                    </StatusIndicator>
                  </Box>
                  <Box float="right" variant="div">
                    <TextContent>
                      <div style={{ paddingBottom: 8 }} className="text-xs text-gray-500">
                        Session ID: {internalSessionId}
                      </div>
                    </TextContent>
                  </Box>
                </SpaceBetween>
              </SpaceBetween>
            </Container>
          </Form>
        </form>
      </div>
    </>
  );
}
