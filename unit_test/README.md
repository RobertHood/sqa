# Chatbot Unit Tests

These Jest tests cover the clean unit-test candidates from `4_System Test - Chatbot module.pdf`.

## Install Jest

From this folder:

```powershell
cd D:\sqa\unit_test
npm install
```

The install uses the dev dependencies listed in `package.json`.

## Run Tests

```powershell
npm test
```

## Add More Tests

Add more `*.test.ts` or `*.test.tsx` files under `unit_test/tests`.

## Covered Chatbot Cases

The current suite covers deterministic widget behavior from:

`CB-04`, `CB-11`, `CB-18`, `CB-19`, `CB-21`, `CB-22`, `CB-23`, `CB-24`, `CB-26`, `CB-28`, `CB-29`, `CB-30`, `CB-32`, `CB-35`, `CB-36`, `CB-37`, `CB-38`, `CB-39`, `CB-40`, `CB-41`.

Cases such as `CB-02`, `CB-03`, `CB-05`, `CB-06`, `CB-07`, `CB-08`, `CB-13`, `CB-15`, `CB-16`, `CB-17`, and `CB-20` are intentionally skipped here because they validate LLM/RAG answer quality rather than deterministic unit behavior.
