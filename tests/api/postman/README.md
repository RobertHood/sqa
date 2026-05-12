# Postman API Test Suite — Educational Platform

Comprehensive API test suite covering 60+ endpoints across 16 modules with automatic cleanup and DB verification via API calls.

## Overview

| Metric | Count |
|--------|-------|
| Total test cases | ~130 |
| Modules covered | 16 |
| Test types | Happy path, Validation, Authorization, Edge cases |
| Cleanup strategy | Automatic via API DELETE after each CREATE test |
| DB verification | Via GET API after CREATE operations |

## Files

```
tests/postman/
├── collections/
│   └── Educational_Platform_API_Tests.postman_collection.json
├── environments/
│   └── Educational_Platform_Dev.postman_environment.json
├── test_cases/
│   └── test_cases_comprehensive.csv
└── README.md
```

## Prerequisites

- **Postman** v10+ (or Newman CLI for headless runs)
- Backend running on `http://localhost:3000`
- Microservice running on `http://localhost:8000` (for microservice tests)
- PostgreSQL database seeded with `data.sql`
- Test users present in DB:
  - Admin: `admin@example.com` / `admin123`
  - User: `user1@example.com` / `User123!`

## Setup Instructions

### 1. Import into Postman

1. Open Postman → **Import**
2. Import `collections/Educational_Platform_API_Tests.postman_collection.json`
3. Import `environments/Educational_Platform_Dev.postman_environment.json`
4. Select environment **Educational Platform - Dev** in top-right dropdown

### 2. Configure Environment Variables

Update these if your setup differs:

| Variable | Default | Description |
|----------|---------|-------------|
| `base_url` | `http://localhost:3000` | Backend API base URL |
| `microservice_url` | `http://localhost:8000` | FastAPI microservice URL |
| `admin_email` | `admin@example.com` | Admin account email |
| `admin_password` | `admin123` | Admin account password |
| `user_email` | `user1@example.com` | Regular user email |
| `user_password` | `User123!` | Regular user password |

### 3. Start the Backend

```bash
cd backend
npm run dev
```

## Running Tests

### Cách 1: Script tự động (ghi pass/fail vào CSV)

```bash
cd tests/postman

# Chạy toàn bộ collection → kết quả ghi vào test_cases/test_results.csv
node run_tests.js

# Chỉ chạy một folder cụ thể
node run_tests.js --folder 01_Authentication
node run_tests.js --folder 07_Exams

# Dùng npm script
npm test
```

Sau khi chạy xong, file **`test_cases/test_results.csv`** sẽ có thêm 3 cột:
- `Result` — **PASS** / **FAIL** / **ERROR** / **NOT RUN**
- `Run Time` — Thời điểm chạy
- `Details` — Chi tiết assertion nào pass/fail

### Cách 2: Postman UI

1. Import collection và environment vào Postman
2. Click **Run collection**
3. Xem kết quả trong Postman Collection Runner

### Cách 3: Newman CLI trực tiếp

```bash
cd tests/postman

# Chạy và xem output trong terminal
./node_modules/.bin/newman run collections/Educational_Platform_API_Tests.postman_collection.json \
  -e environments/Educational_Platform_Dev.postman_environment.json

# Chạy folder cụ thể
./node_modules/.bin/newman run collections/Educational_Platform_API_Tests.postman_collection.json \
  -e environments/Educational_Platform_Dev.postman_environment.json \
  --folder "01_Authentication"
```

## Test Structure

### Folder Organization

| Folder | Module | Test Count | Auth Required |
|--------|--------|-----------|---------------|
| `00_Setup` | Environment validation | 3 | Mixed |
| `01_Authentication` | Register/Login | 8 | No |
| `02_Users` | User CRUD | 7 | Admin/User |
| `04_Subjects` | Subject management | 8 | Mixed |
| `05_Topics` | Topic management | 5 | Admin |
| `06_Questions` | Question management | 6 | Mixed |
| `07_Exams` | Exam schedules + CRUD + user ops | 20 | Mixed |
| `08_Banks` | Question bank management | 10 | Mixed |
| `09_Flashcards` | Deck + flashcard + quiz | 17 | User |
| `10_Documents` | Document management | 3 | Mixed |
| `11_Files` | File upload/serving | 4 | Mixed |
| `12_Roadmap` | Roadmap management | 5 | Mixed |
| `13_Study_Schedule` | Study schedule CRUD | 5 | User |
| `14_User_Goals` | User goals CRUD | 4 | User |
| `15_Dashboard` | Admin analytics | 6 | Admin |
| `16_Microservice` | LLM/BERT endpoints | 4 | Mixed |

### Test ID Convention

```
TC_<MODULE>_<NUMBER>  -  <Short description>

Examples:
  TC_AUTH_001  -  Register - Success
  TC_EXAM_005  -  Get Exam By ID - User
  TC_FLASH_007  -  Update Flashcard
```

### Test Pattern per Request

Each request has test scripts that verify:
1. **HTTP status code** — exact match or range
2. **Response structure** — `{status, message, data}` format
3. **Response data** — field presence, types, values
4. **Business rules** — e.g., `is_correct` hidden for non-admins
5. **DB verification** — follow-up GET request after CREATE
6. **Cleanup** — automatic DELETE after CREATE tests

## Authentication Flow

The collection uses a **collection-level pre-request script** that:
1. Checks if `admin_token` and `user_token` exist
2. Auto-logs in to get tokens if missing
3. Tokens are stored in environment variables

Individual requests use either `{{admin_token}}` or `{{user_token}}` Bearer tokens.

## Cleanup Strategy

After each **CREATE** test (status 201):
- The created resource ID is saved to `pm.environment.set('test_<resource>_id', id)`
- A follow-up **DELETE** test request is included in the folder
- After delete, `pm.environment.unset('test_<resource>_id')` clears the variable

This ensures no test data accumulates across runs.

## DB Verification Strategy

Since Postman cannot directly query PostgreSQL, DB state is verified by:

1. **After CREATE**: `pm.sendRequest(GET endpoint)` to confirm record exists
2. **After DELETE**: GET request to confirm 404/not found
3. **After UPDATE**: GET request to confirm new values

Example from `TC_SUBJ_002`:
```javascript
pm.sendRequest({
  url: pm.environment.get('base_url') + '/subjects',
  method: 'GET'
}, (err, res) => {
  pm.test('DB verification - subject exists in list', () => {
    const found = res.json().data.find(s => s.subject_id == pm.environment.get('test_subject_id'));
    pm.expect(found).to.not.be.undefined;
  });
});
```

## Test Case Reference (CSV)

The file `test_cases/test_cases_comprehensive.csv` contains all test cases in the format:

| Column | Description |
|--------|-------------|
| Test case ID | Unique ID (e.g., TC_AUTH_001) |
| File Name | Postman request name |
| Method name | HTTP method + path |
| Purpose | What is being tested |
| Input | Request body/params |
| Expected output | HTTP status + response structure |

## Troubleshooting

### Tokens not being set
- Check that `admin_email`/`admin_password` environment variables are correct
- Run `00_Setup > Admin Login - Setup` manually first

### Test fails with 401 on admin endpoints
- Ensure admin user has `role_id = 2` in the database
- Re-run `00_Setup` folder to refresh tokens

### Microservice tests fail
- Tests in `16_Microservice` expect 200 or 5xx — they pass even if microservice is offline
- Start the Python microservice: `cd backend/microservice && python api.py`

### test_*_id variables empty
- Run tests in folder order (e.g., CREATE before UPDATE/DELETE)
- Each folder handles its own setup/cleanup

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Run API Tests
  run: |
    npm install -g newman newman-reporter-htmlextra
    newman run tests/postman/collections/Educational_Platform_API_Tests.postman_collection.json \
      -e tests/postman/environments/Educational_Platform_Dev.postman_environment.json \
      --bail \
      --reporters cli,htmlextra \
      --reporter-htmlextra-export tests/postman/reports/report.html
  
- name: Upload Test Report
  uses: actions/upload-artifact@v3
  with:
    name: postman-test-report
    path: tests/postman/reports/report.html
```
