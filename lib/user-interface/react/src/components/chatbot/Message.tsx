import Container from '@cloudscape-design/components/container';
import TextContent from '@cloudscape-design/components/text-content';
import ReactMarkdown from 'react-markdown';
import Spinner from '@cloudscape-design/components/spinner';
import Box from '@cloudscape-design/components/box';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import { SpaceBetween } from '@cloudscape-design/components';
import { JsonView, darkStyles } from 'react-json-view-lite';
import 'react-json-view-lite/dist/index.css';
import { LisaChatMessage } from '../types';

interface MessageProps {
  message?: LisaChatMessage;
  isRunning: boolean;
  showMetadata?: boolean;
}

export default function Message({ message, isRunning, showMetadata }: MessageProps) {
  return (
    <div className="mt-2">
      {isRunning && (
        <Container>
          <Box float="left">
            <Spinner />
          </Box>
        </Container>
      )}
      {message?.type !== 'human' && !isRunning && (
        <Container>
          <SpaceBetween size="s" direction="vertical">
            <ReactMarkdown children={message.content} />
            {message.metadata && showMetadata && (
              <ExpandableSection variant="footer" headerText="Metadata">
                <JsonView data={message.metadata} style={darkStyles} />
              </ExpandableSection>
            )}
          </SpaceBetween>
        </Container>
      )}
      {message?.type === 'human' && (
        <TextContent>
          <strong>{message.content}</strong>
        </TextContent>
      )}
    </div>
  );
}
