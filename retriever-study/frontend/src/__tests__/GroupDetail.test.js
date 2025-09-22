
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import WS from 'jest-websocket-mock';
import GroupDetail from '../pages/GroupDetail';

// Mock react-router-dom
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useParams: () => ({
    groupId: '123',
  }),
}));

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = jest.fn();

describe('GroupDetail WebSocket Chat', () => {
  let server;

  beforeEach(() => {
    // Set up a mock WebSocket server before each test
    server = new WS('ws://localhost:8000/ws/chat/123?token=test-token', { jsonProtocol: true });
    // Mock localStorage
    Storage.prototype.getItem = jest.fn((key) => {
      if (key === 'token') {
        return 'test-token';
      }
      return null;
    });
  });

  afterEach(() => {
    // Close the server and restore mocks after each test
    WS.clean();
    jest.restoreAllMocks();
  });

  test('verifies WebSocket connection is attempted with correct URL and token', async () => {
    render(<GroupDetail />);
    // The connection happens in a useEffect, so we wait for it
    await server.connected;
    // No direct way to check URL with jest-websocket-mock, but connection implies correct URL
    // We can check that the token was retrieved from localStorage
    expect(localStorage.getItem).toHaveBeenCalledWith('token');
  });

  test('closes the WebSocket connection on component unmount', async () => {
    const { unmount } = render(<GroupDetail />);
    await server.connected;

    unmount();

    await expect(server.closed).resolves.toBeUndefined();
  });

  test('receives and displays messages from the server', async () => {
    render(<GroupDetail />);
    await server.connected;

    const message1 = { sender: 'Alice', content: 'Hello, world!' };
    const message2 = { sender: 'Bob', content: 'Hi there!' };

    // Simulate server sending messages
    server.send(message1);
    server.send(message2);

    // Check if messages are rendered
    expect(await screen.findByText('Hello, world!')).toBeInTheDocument();
    expect(screen.getByText('Alice:')).toBeInTheDocument();

    expect(await screen.findByText('Hi there!')).toBeInTheDocument();
    expect(screen.getByText('Bob:')).toBeInTheDocument();
  });

  test('sends a message and displays it in the UI', async () => {
    render(<GroupDetail />);
    await server.connected;

    const input = screen.getByLabelText('Type a message');
    const sendButton = screen.getByText('Send');
    const testMessage = 'This is a test message';

    // Simulate user typing a message
    fireEvent.change(input, { target: { value: testMessage } });
    expect(input.value).toBe(testMessage);

    // Simulate user clicking send
    fireEvent.click(sendButton);

    // Assert that the message was sent to the server
    await expect(server).toReceiveMessage({ content: testMessage });

    // The component does not currently display the user's own sent messages immediately
    // without receiving them back from the server. Let's test that it appears after being "broadcast" back.
    server.send({ sender: 'Me', content: testMessage });

    expect(await screen.findByText(testMessage)).toBeInTheDocument();
    expect(screen.getByText('Me:')).toBeInTheDocument();

    // Assert that the input is cleared after sending
    expect(input.value).toBe('');
  });
});
