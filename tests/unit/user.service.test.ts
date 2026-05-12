/**
 * Unit Test — Profile Service (user.service.ts)
 * 30 test cases: Functional + Boundary Value Analysis
 * 
 * BUGS FOUND:
 *  BUG-1: getAll() không validate page ≤ 0 → gửi offset âm tới DB
 *  BUG-2: update() dùng COALESCE → không thể set field về NULL (vd: xóa birthday)
 *  BUG-3: update() lưu password_hash dạng plaintext, không hash
 */

jest.mock('../../backend/src/config/database', () => {
  const mockQuery = jest.fn();
  return {
    query: mockQuery,
    __esModule: true,
    default: { connect: jest.fn() },
  };
});

import UserService from '../../backend/src/services/user.service';
import { query } from '../../backend/src/config/database';

const mockQuery = query as jest.MockedFunction<typeof query>;

beforeEach(() => {
  jest.clearAllMocks();
});

// Helper: setup mock for getAll (data query + count query)
function setupGetAllMock(users: any[], total: number) {
  mockQuery
    .mockResolvedValueOnce({ rows: users } as any)
    .mockResolvedValueOnce({ rows: [{ total }] } as any);
}

// ==================================================
// getAll — Functional & Boundary Tests
// ==================================================

describe('UserService.getAll', () => {

  // PROF-01: Functional — lấy danh sách user trang 1
  test('PROF-01: getAll page=1 no filters returns users and correct totalPages', async () => {
    const fakeUsers = Array.from({ length: 12 }, (_, i) => ({
      user_id: i + 1, user_name: `User${i}`, email: `u${i}@t.com`,
      birthday: null, created_at: new Date(), available: true, role_name: 'USER',
    }));
    setupGetAllMock(fakeUsers, 25);

    const result = await UserService.getAll(1, 'All', 'All', '');

    expect(result.users).toHaveLength(12);
    expect(result.totalPages).toBe(3); // ceil(25/12)
    const params = mockQuery.mock.calls[0][1] as any[];
    expect(params).toContain(12); // limit
    expect(params).toContain(0);  // offset
  });

  // PROF-02: Functional — filter status=true
  test('PROF-02: getAll filters by status="true" adds available=true to WHERE', async () => {
    setupGetAllMock([{ user_id: 1, available: true }], 1);
    await UserService.getAll(1, 'true', 'All', '');

    const sql = mockQuery.mock.calls[0][0] as string;
    expect(sql).toContain('u.available = $');
    expect(mockQuery.mock.calls[0][1]).toContain(true);
  });

  // PROF-03: Functional — filter status=false
  test('PROF-03: getAll filters by status="false" adds available=false', async () => {
    setupGetAllMock([], 0);
    await UserService.getAll(1, 'false', 'All', '');
    expect(mockQuery.mock.calls[0][1]).toContain(false);
  });

  // PROF-04: Functional — filter role=1
  test('PROF-04: getAll with role=1 adds role_id filter', async () => {
    setupGetAllMock([{ user_id: 1, role_name: 'USER' }], 1);
    await UserService.getAll(1, 'All', 1, '');

    const sql = mockQuery.mock.calls[0][0] as string;
    expect(sql).toContain('r.role_id = $');
    expect(mockQuery.mock.calls[0][1]).toContain(1);
  });

  // PROF-05: Functional — search tiếng Việt dùng unaccent
  test('PROF-05: getAll search uses unaccent + ILIKE for Vietnamese text', async () => {
    setupGetAllMock([], 0);
    await UserService.getAll(1, 'All', 'All', 'Nguyễn');

    const sql = mockQuery.mock.calls[0][0] as string;
    expect(sql).toContain('unaccent');
    expect(sql).toContain('ILIKE');
    expect(mockQuery.mock.calls[0][1]).toContain('Nguyễn');
  });

  // PROF-06: Functional — combine status + role + search
  test('PROF-06: getAll combines all three filters correctly', async () => {
    setupGetAllMock([], 0);
    await UserService.getAll(1, 'true', 1, 'test');

    const sql = mockQuery.mock.calls[0][0] as string;
    expect(sql).toContain('u.available = $');
    expect(sql).toContain('r.role_id = $');
    expect(sql).toContain('unaccent');
    const params = mockQuery.mock.calls[0][1] as any[];
    expect(params).toContain(true);
    expect(params).toContain(1);
    expect(params).toContain('test');
  });

  // PROF-07: Functional — search by email
  test('PROF-07: getAll search matches email field via ILIKE', async () => {
    setupGetAllMock([{ user_id: 1, email: 'admin@gmail.com' }], 1);
    await UserService.getAll(1, 'All', 'All', 'admin@gmail');
    expect(mockQuery.mock.calls[0][1]).toContain('admin@gmail');
  });

  // PROF-08: Functional — pagination page 2
  test('PROF-08: getAll page=2 uses offset=12', async () => {
    setupGetAllMock([], 20);
    await UserService.getAll(2, 'All', 'All', '');

    const params = mockQuery.mock.calls[0][1] as any[];
    expect(params).toContain(12); // offset = (2-1)*12
  });

  // ──────────────────────────────────────────────
  // ★ BUG-1: page=0 → offset = -12 (invalid)
  // Service KHÔNG validate page, gửi offset âm tới PostgreSQL
  // PostgreSQL sẽ throw: "OFFSET must not be negative"
  // ──────────────────────────────────────────────
  test('PROF-09: [BUG-1] getAll page=0 should reject or default to page 1 (negative offset)', async () => {
    setupGetAllMock([], 0);

    // Service nên throw error hoặc đặt mặc định page=1 khi page ≤ 0
    // BUG: offset = (0-1)*12 = -12 → PostgreSQL error
    const params = mockQuery.mock.calls;
    await UserService.getAll(0, 'All', 'All', '');

    const queryParams = mockQuery.mock.calls[0][1] as any[];
    const offset = queryParams[queryParams.length - 1]; // last param = offset
    expect(offset).toBeGreaterThanOrEqual(0); // FAIL: offset = -12
  });

  // ★ BUG-1 (tiếp): page = -1
  test('PROF-10: [BUG-1] getAll page=-1 should reject (produces offset=-24)', async () => {
    setupGetAllMock([], 0);

    await UserService.getAll(-1, 'All', 'All', '');

    const queryParams = mockQuery.mock.calls[0][1] as any[];
    const offset = queryParams[queryParams.length - 1];
    expect(offset).toBeGreaterThanOrEqual(0); // FAIL: offset = -24
  });

  // PROF-11: BVA — page rất lớn trả danh sách rỗng
  test('PROF-11: getAll page=99999 returns empty users but valid totalPages', async () => {
    setupGetAllMock([], 5);

    const result = await UserService.getAll(99999, 'All', 'All', '');

    expect(result.users).toEqual([]);
    expect(result.totalPages).toBe(1); // ceil(5/12)
  });

  // PROF-12: BVA — searchValue chỉ khoảng trắng → skip filter
  test('PROF-12: getAll with whitespace-only search skips search filter', async () => {
    setupGetAllMock([], 0);
    await UserService.getAll(1, 'All', 'All', '   ');

    const sql = mockQuery.mock.calls[0][0] as string;
    expect(sql).not.toContain('unaccent');
  });

  // PROF-13: BVA — SQL injection an toàn qua parameterized query
  test('PROF-13: getAll with SQL injection string is safely parameterized', async () => {
    setupGetAllMock([], 0);
    const injection = "'; DROP TABLE user;--";

    await UserService.getAll(1, 'All', 'All', injection);

    const params = mockQuery.mock.calls[0][1] as any[];
    expect(params).toContain(injection); // passed as param, not in SQL
  });

  // PROF-14: BVA — searchValue dài 200 ký tự
  test('PROF-14: getAll with 200-char search executes without error', async () => {
    setupGetAllMock([], 0);
    const result = await UserService.getAll(1, 'All', 'All', 'a'.repeat(200));
    expect(result.users).toEqual([]);
    expect(result.totalPages).toBe(0);
  });

  // PROF-15: Functional — totalItems=0 → totalPages=0
  test('PROF-15: getAll with 0 total items returns totalPages=0', async () => {
    setupGetAllMock([], 0);

    const result = await UserService.getAll(1, 'All', 'All', '');

    expect(result.totalPages).toBe(0);
  });
});

// ==================================================
// getById — Tests
// ==================================================

describe('UserService.getById', () => {
  // PROF-16: Functional — found
  test('PROF-16: getById returns user object when found', async () => {
    const fakeUser = {
      user_id: 1, user_name: 'Test', email: 'test@test.com',
      birthday: '2000-01-15', created_at: new Date(), role_id: 1, available: true,
    };
    mockQuery.mockResolvedValueOnce({ rows: [fakeUser] } as any);

    const result = await UserService.getById(1);
    expect(result).toEqual(fakeUser);
  });

  // PROF-17: BVA — ID không tồn tại
  test('PROF-17: getById throws USER_NOT_FOUND for non-existent id', async () => {
    mockQuery.mockResolvedValueOnce({ rows: [] } as any);
    await expect(UserService.getById(99999)).rejects.toThrow('USER_NOT_FOUND');
  });

  // PROF-18: BVA — ID = 0
  test('PROF-18: getById with id=0 throws USER_NOT_FOUND', async () => {
    mockQuery.mockResolvedValueOnce({ rows: [] } as any);
    await expect(UserService.getById(0)).rejects.toThrow('USER_NOT_FOUND');
  });

  // PROF-19: BVA — ID âm
  test('PROF-19: getById with negative id throws USER_NOT_FOUND', async () => {
    mockQuery.mockResolvedValueOnce({ rows: [] } as any);
    await expect(UserService.getById(-1)).rejects.toThrow('USER_NOT_FOUND');
  });
});

// ==================================================
// update — Tests
// ==================================================

describe('UserService.update', () => {
  // PROF-20: Functional — cập nhật user_name
  test('PROF-20: update user_name successfully', async () => {
    const updated = { user_id: 1, user_name: 'New Name', email: 'old@test.com' };
    mockQuery.mockResolvedValueOnce({ rows: [updated] } as any);

    const result = await UserService.update(1, { user_name: 'New Name' });
    expect(result.user_name).toBe('New Name');
  });

  // PROF-21: Functional — cập nhật email
  test('PROF-21: update email successfully', async () => {
    const updated = { user_id: 1, email: 'new@email.com' };
    mockQuery.mockResolvedValueOnce({ rows: [updated] } as any);

    const result = await UserService.update(1, { email: 'new@email.com' });
    expect(result.email).toBe('new@email.com');
  });

  // PROF-22: Functional — cập nhật nhiều fields
  test('PROF-22: update multiple fields simultaneously', async () => {
    const updated = { user_id: 1, user_name: 'ABC', email: 'abc@t.com', available: false };
    mockQuery.mockResolvedValueOnce({ rows: [updated] } as any);

    const result = await UserService.update(1, {
      user_name: 'ABC', email: 'abc@t.com', available: false,
    });
    expect(result.user_name).toBe('ABC');
    expect(result.available).toBe(false);
  });

  // PROF-23: BVA — user_name 1 ký tự
  test('PROF-23: update with 1-char user_name succeeds', async () => {
    mockQuery.mockResolvedValueOnce({ rows: [{ user_id: 1, user_name: 'A' }] } as any);
    const result = await UserService.update(1, { user_name: 'A' });
    expect(result.user_name).toBe('A');
  });

  // PROF-24: BVA — user_name 100 ký tự (max VARCHAR)
  test('PROF-24: update with 100-char user_name (max VARCHAR) succeeds', async () => {
    const name100 = 'A'.repeat(100);
    mockQuery.mockResolvedValueOnce({ rows: [{ user_id: 1, user_name: name100 }] } as any);
    const result = await UserService.update(1, { user_name: name100 });
    expect(result.user_name.length).toBe(100);
  });

  // ──────────────────────────────────────────────
  // ★ BUG-2: COALESCE ngăn set field về NULL
  // birthday = COALESCE($4, birthday) → nếu pass null → giữ giá trị cũ
  // → User không thể XÓA birthday đã set
  // ──────────────────────────────────────────────
  test('PROF-25: [BUG-2] update birthday to null should clear it (COALESCE prevents this)', async () => {
    mockQuery.mockResolvedValueOnce({
      rows: [{ user_id: 1, user_name: 'Test', email: 't@t.com', birthday: null }],
    } as any);

    await UserService.update(1, { birthday: null as any });

    const sql = mockQuery.mock.calls[0][0] as string;
    // BUG: SQL dùng COALESCE($4, birthday) → COALESCE(NULL, birthday) = birthday (giữ giá trị cũ)
    // Đúng ra phải cho phép set birthday = NULL trực tiếp
    expect(sql).not.toMatch(/birthday\s*=\s*COALESCE/i); // FAIL: SQL chứa COALESCE
  });

  // ──────────────────────────────────────────────
  // ★ BUG-3: password_hash lưu plaintext, không hash
  // update() nhận password_hash và ghi thẳng vào DB
  // không qua bcrypt.hash() như register()
  // ──────────────────────────────────────────────
  test('PROF-26: [BUG-3] update password_hash should hash before storing (stores plaintext)', async () => {
    mockQuery.mockResolvedValueOnce({ rows: [{ user_id: 1 }] } as any);

    await UserService.update(1, { password_hash: 'newpassword123' });

    const params = mockQuery.mock.calls[0][1] as any[];
    // params[2] = password_hash (thứ 3 trong mảng tham số)
    // BUG: password gửi thẳng plaintext vào DB, không hash
    // Đúng ra phải là bcrypt hash (bắt đầu bằng $2b$ hoặc $2a$)
    expect(params[2]).not.toBe('newpassword123'); // FAIL: params[2] === 'newpassword123'
  });

  // PROF-27: Functional — update user không tồn tại
  test('PROF-27: update non-existent user throws USER_NOT_FOUND', async () => {
    mockQuery.mockResolvedValueOnce({ rows: [] } as any);
    await expect(UserService.update(99999, { user_name: 'Ghost' })).rejects.toThrow('USER_NOT_FOUND');
  });
});

// ==================================================
// remove — Tests
// ==================================================

describe('UserService.remove', () => {
  // PROF-28: Functional — xóa thành công
  test('PROF-28: remove existing user succeeds', async () => {
    mockQuery.mockResolvedValueOnce({ rowCount: 1 } as any);
    await expect(UserService.remove(1)).resolves.toBeUndefined();
  });

  // PROF-29: BVA — xóa user không tồn tại
  test('PROF-29: remove non-existent user throws USER_NOT_FOUND', async () => {
    mockQuery.mockResolvedValueOnce({ rowCount: 0 } as any);
    await expect(UserService.remove(99999)).rejects.toThrow('USER_NOT_FOUND');
  });

  // PROF-30: BVA — xóa id=0
  test('PROF-30: remove with id=0 throws USER_NOT_FOUND', async () => {
    mockQuery.mockResolvedValueOnce({ rowCount: 0 } as any);
    await expect(UserService.remove(0)).rejects.toThrow('USER_NOT_FOUND');
  });
});
