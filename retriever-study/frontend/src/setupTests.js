// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

// Mock localStorage with proper jest functions
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: jest.fn((key) => store[key] || null),
    setItem: jest.fn((key, value) => store[key] = value.toString()),
    removeItem: jest.fn((key) => delete store[key]),
    clear: jest.fn(() => store = {}),
  };
})();
global.localStorage = localStorageMock;

// Mock fetch globally
global.fetch = jest.fn();

// Mock console methods to reduce test noise
const originalError = console.error;
const originalWarn = console.warn;

beforeEach(() => {
  // Reset all mocks before each test
  jest.clearAllMocks();
  localStorageMock.getItem.mockReturnValue(null);

  // Mock console.error and console.warn to avoid noise in tests
  console.error = jest.fn();
  console.warn = jest.fn();
});

afterEach(() => {
  // Restore console methods after each test
  console.error = originalError;
  console.warn = originalWarn;
});