const tsJest = require.resolve("ts-jest");

module.exports = {
  clearMocks: true,
  rootDir: "..",
  testEnvironment: "jsdom",
  testMatch: ["<rootDir>/unit_test/tests/**/*.test.ts?(x)"],
  setupFilesAfterEnv: ["<rootDir>/unit_test/jest.setup.ts"],
  collectCoverageFrom: [
    "<rootDir>/frontend_user/src/components/chat-mini/page.tsx"
  ],
  coverageDirectory: "<rootDir>/unit_test/coverage",
  coverageReporters: ["text", "html", "lcov"],
  moduleNameMapper: {
    "^react$": "<rootDir>/unit_test/node_modules/react",
    "^react/jsx-runtime$": "<rootDir>/unit_test/node_modules/react/jsx-runtime.js",
    "^react-dom$": "<rootDir>/unit_test/node_modules/react-dom",
    "\\.(css|less|scss|sass)$": "<rootDir>/unit_test/__mocks__/styleMock.js",
    "^react-markdown$": "<rootDir>/unit_test/__mocks__/react-markdown.tsx"
  },
  transform: {
    "^.+\\.(ts|tsx)$": [
      tsJest,
      {
        tsconfig: "<rootDir>/unit_test/tsconfig.json"
      }
    ]
  }
};
