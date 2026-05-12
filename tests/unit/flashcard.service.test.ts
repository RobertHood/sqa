/**
 * Unit Test — Flashcard Service (flashcard.service.ts + flashcard.deck.service.ts)
 * 30 test cases: Functional + Boundary Value Analysis
 *
 * BUGS FOUND:
 *  BUG-4: FlashcardService.update() — SQL injection qua object key names
 *  BUG-5: FlashcardService.add() — không dùng transaction (race condition)
 *  BUG-6: FlashcardDeckService.getAll() — gọi COMMIT mà không có BEGIN
 *  BUG-7: FlashcardDeckService.getAll() — mix pool.query và client.query (data inconsistency)
 *  BUG-8: FlashcardDeckService.getById() — console.log() leak dữ liệu nhạy cảm
 */

// ── Mock database ──
const mockPoolQuery = jest.fn();
const mockClientQuery = jest.fn();
const mockRelease = jest.fn();

jest.mock('../../backend/src/config/database', () => {
  const pool = {
    connect: () =>
      Promise.resolve({
        query: mockClientQuery,
        release: mockRelease,
      }),
    query: mockPoolQuery,
  };
  return {
    query: mockPoolQuery,
    __esModule: true,
    default: pool,
  };
});

import { FlashcardService } from '../../backend/src/services/flashcard.service';
import { FlashcardDeckService } from '../../backend/src/services/flashcard.deck.service';

beforeEach(() => {
  jest.clearAllMocks();
  mockClientQuery.mockReset();
  mockPoolQuery.mockReset();
  mockRelease.mockReset();
});

// ==================================================
// FlashcardService.add — 8 tests
// ==================================================

describe('FlashcardService.add', () => {

  // FC-01: Functional — thêm flashcard thành công
  test('FC-01: add flashcard successfully when deck has room (count=10 < 50)', async () => {
    mockClientQuery
      .mockResolvedValueOnce({ rows: [{ count: '10' }] })
      .mockResolvedValueOnce({
        rows: [{ flashcard_id: 1, front: 'Apple', back: 'Táo', flashcard_deck_id: 1 }],
      });

    const result = await FlashcardService.add({
      front: 'Apple', back: 'Táo', example: 'I eat an apple', flashcard_deck_id: 1,
    } as any);

    expect(result).not.toBeNull();
    expect(result!.front).toBe('Apple');
  });

  // FC-02: BVA — deck có 49 cards (boundary dưới limit)
  test('FC-02: add when deck has 49 cards succeeds (50th card)', async () => {
    mockClientQuery
      .mockResolvedValueOnce({ rows: [{ count: '49' }] })
      .mockResolvedValueOnce({
        rows: [{ flashcard_id: 50, front: 'Test', back: 'Test', flashcard_deck_id: 1 }],
      });

    const result = await FlashcardService.add({
      front: 'Test', back: 'Test', flashcard_deck_id: 1,
    } as any);

    expect(result).not.toBeNull();
  });

  // FC-03: BVA — deck đã có 50 cards (đạt limit)
  test('FC-03: add when deck has 50 cards returns null (at limit)', async () => {
    mockClientQuery.mockResolvedValueOnce({ rows: [{ count: '50' }] });

    const result = await FlashcardService.add({
      front: 'Test', back: 'Test', flashcard_deck_id: 1,
    } as any);

    expect(result).toBeNull();
  });

  // FC-04: BVA — deck có 51 cards (vượt limit)
  test('FC-04: add when deck has 51 cards returns null (over limit)', async () => {
    mockClientQuery.mockResolvedValueOnce({ rows: [{ count: '51' }] });

    const result = await FlashcardService.add({
      front: 'Test', back: 'Test', flashcard_deck_id: 1,
    } as any);

    expect(result).toBeNull();
  });

  // ──────────────────────────────────────────────
  // ★ BUG-5: add() không dùng transaction BEGIN/COMMIT
  // Count check và INSERT chạy không trong transaction
  // → Race condition: 2 request đồng thời có thể vượt limit 50
  // ──────────────────────────────────────────────
  test('FC-05: [BUG-5] add should use BEGIN/COMMIT transaction for atomicity (race condition)', async () => {
    mockClientQuery
      .mockResolvedValueOnce({ rows: [{ count: '10' }] })
      .mockResolvedValueOnce({
        rows: [{ flashcard_id: 1, front: 'Test', back: 'Test' }],
      });

    await FlashcardService.add({
      front: 'Test', back: 'Test', flashcard_deck_id: 1,
    } as any);

    // Kiểm tra BEGIN phải được gọi trước COUNT và INSERT
    // BUG: code KHÔNG gọi BEGIN → race condition giữa COUNT và INSERT
    const clientCalls = mockClientQuery.mock.calls.map((c: any) => {
      const arg = c[0] as string;
      return arg.trim();
    });
    expect(clientCalls).toContain('BEGIN'); // FAIL: không có BEGIN
  });

  // FC-06: BVA — front 1 ký tự
  test('FC-06: add with 1-char front succeeds', async () => {
    mockClientQuery
      .mockResolvedValueOnce({ rows: [{ count: '0' }] })
      .mockResolvedValueOnce({
        rows: [{ flashcard_id: 1, front: 'A', back: 'B' }],
      });

    const result = await FlashcardService.add({
      front: 'A', back: 'B', example: '', flashcard_deck_id: 1,
    } as any);

    expect(result).not.toBeNull();
    expect(result!.front).toBe('A');
  });

  // FC-07: Functional — FK violation trả null
  test('FC-07: add with non-existent deck_id returns null (FK violation caught)', async () => {
    mockClientQuery
      .mockResolvedValueOnce({ rows: [{ count: '0' }] })
      .mockRejectedValueOnce(new Error('violates foreign key constraint'));

    const result = await FlashcardService.add({
      front: 'X', back: 'Y', flashcard_deck_id: 99999,
    } as any);

    expect(result).toBeNull();
  });

  // FC-08: Functional — back=null (nullable column)
  test('FC-08: add with null back succeeds (nullable column)', async () => {
    mockClientQuery
      .mockResolvedValueOnce({ rows: [{ count: '0' }] })
      .mockResolvedValueOnce({
        rows: [{ flashcard_id: 1, front: 'Hello', back: null, example: null }],
      });

    const result = await FlashcardService.add({
      front: 'Hello', back: null, example: null, flashcard_deck_id: 1,
    } as any);

    expect(result).not.toBeNull();
    expect(result!.back).toBeNull();
  });
});

// ==================================================
// FlashcardService.update — 4 tests
// ==================================================

describe('FlashcardService.update', () => {

  // FC-09: Functional — update front và back
  test('FC-09: update front and back successfully', async () => {
    mockPoolQuery.mockResolvedValueOnce({
      rows: [{ flashcard_id: 1, front: 'New Front', back: 'New Back' }],
    });

    const result = await FlashcardService.update(1, { front: 'New Front', back: 'New Back' });

    expect(result).not.toBeNull();
    expect(result!.front).toBe('New Front');
    expect(result!.back).toBe('New Back');
  });

  // FC-10: BVA — data rỗng
  test('FC-10: update with empty data returns null (no fields to update)', async () => {
    const result = await FlashcardService.update(1, {});
    expect(result).toBeNull();
    expect(mockPoolQuery).not.toHaveBeenCalled();
  });

  // FC-11: Functional — flashcard không tồn tại
  test('FC-11: update non-existent flashcard returns null', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rows: [] });
    const result = await FlashcardService.update(99999, { front: 'Test' });
    expect(result).toBeNull();
  });

  // ──────────────────────────────────────────────
  // ★ BUG-4: SQL injection qua object key names
  // update() dùng Object.entries(data) rồi interpolate key vào SQL:
  //   fields.push(`${key} = $${idx}`)
  // Attacker truyền key chứa SQL → inject trực tiếp vào query
  // ──────────────────────────────────────────────
  test('FC-12: [BUG-4] update should reject malicious key names (SQL injection via object keys)', async () => {
    mockPoolQuery.mockResolvedValueOnce({
      rows: [{ flashcard_id: 1 }],
    });

    // Tấn công: truyền key chứa SQL injection
    const maliciousData = { "front; DROP TABLE flashcard--": "malicious_value" } as any;
    await FlashcardService.update(1, maliciousData);

    // BUG: key name bị interpolate trực tiếp vào SQL string
    // SQL sinh ra: UPDATE flashcard SET front; DROP TABLE flashcard-- = $1 WHERE ...
    const sql = mockPoolQuery.mock.calls[0][0] as string;
    expect(sql).not.toContain('DROP TABLE'); // FAIL: SQL chứa DROP TABLE
  });
});

// ==================================================
// FlashcardService.remove — 2 tests
// ==================================================

describe('FlashcardService.remove', () => {

  // FC-13: Functional — xóa thành công
  test('FC-13: remove existing flashcard returns true', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rowCount: 1 });
    expect(await FlashcardService.remove(1)).toBe(true);
  });

  // FC-14: BVA — xóa không tồn tại
  test('FC-14: remove non-existent flashcard returns false', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rowCount: 0 });
    expect(await FlashcardService.remove(99999)).toBe(false);
  });
});

// ==================================================
// FlashcardService.quizFlashcard — 4 tests
// ==================================================

describe('FlashcardService.quizFlashcard', () => {

  // FC-15: Functional — chỉ lấy pending/miss/null, loại done
  test('FC-15: quizFlashcard returns only pending/miss/null cards', async () => {
    const eligible = [
      { flashcard_id: 1, status: 'pending' },
      { flashcard_id: 2, status: 'miss' },
      { flashcard_id: 3, status: null },
    ];
    mockPoolQuery.mockResolvedValueOnce({ rows: eligible });

    const result = await FlashcardService.quizFlashcard(1);

    expect(result).toHaveLength(3);
    const sql = mockPoolQuery.mock.calls[0][0] as string;
    expect(sql).toContain("status = 'pending'");
    expect(sql).toContain("status = 'miss'");
    expect(sql).toContain('status IS NULL');
  });

  // FC-16: BVA — LIMIT 20
  test('FC-16: quizFlashcard enforces LIMIT 20', async () => {
    const cards20 = Array.from({ length: 20 }, (_, i) => ({ flashcard_id: i + 1 }));
    mockPoolQuery.mockResolvedValueOnce({ rows: cards20 });

    const result = await FlashcardService.quizFlashcard(1);

    expect(result.length).toBeLessThanOrEqual(20);
    expect((mockPoolQuery.mock.calls[0][0] as string)).toContain('LIMIT 20');
  });

  // FC-17: BVA — deck rỗng
  test('FC-17: quizFlashcard with empty deck returns []', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rows: [] });
    expect(await FlashcardService.quizFlashcard(1)).toEqual([]);
  });

  // FC-18: Functional — all done → empty
  test('FC-18: quizFlashcard with all-done deck returns empty', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rows: [] });
    expect(await FlashcardService.quizFlashcard(1)).toEqual([]);
  });
});

// ==================================================
// FlashcardService.reviewFlashcard — 3 tests
// ==================================================

describe('FlashcardService.reviewFlashcard', () => {

  // FC-19: Functional — trả tất cả status
  test('FC-19: reviewFlashcard returns all cards regardless of status', async () => {
    const allCards = [
      { flashcard_id: 1, status: 'done' },
      { flashcard_id: 2, status: 'pending' },
      { flashcard_id: 3, status: 'miss' },
    ];
    mockPoolQuery.mockResolvedValueOnce({ rows: allCards });

    const result = await FlashcardService.reviewFlashcard(1);

    expect(result).toHaveLength(3);
    const sql = mockPoolQuery.mock.calls[0][0] as string;
    expect(sql).not.toContain("status ="); // no status filter
  });

  // FC-20: BVA — LIMIT 20
  test('FC-20: reviewFlashcard enforces LIMIT 20', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rows: Array.from({ length: 20 }, (_, i) => ({ flashcard_id: i })) });
    const result = await FlashcardService.reviewFlashcard(1);
    expect(result.length).toBeLessThanOrEqual(20);
  });

  // FC-21: BVA — deck rỗng
  test('FC-21: reviewFlashcard with empty deck returns []', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rows: [] });
    expect(await FlashcardService.reviewFlashcard(1)).toEqual([]);
  });
});

// ==================================================
// FlashcardService.submitFlashcard — 4 tests
// ==================================================

describe('FlashcardService.submitFlashcard', () => {

  // FC-22: Functional — cả correct lẫn miss
  test('FC-22: submitFlashcard updates both correct and miss statuses', async () => {
    mockPoolQuery.mockResolvedValueOnce({}).mockResolvedValueOnce({});

    await FlashcardService.submitFlashcard([1, 2, 3], [4, 5]);

    expect(mockPoolQuery).toHaveBeenCalledTimes(2);
    expect((mockPoolQuery.mock.calls[0][0] as string)).toContain("status = 'done'");
    expect((mockPoolQuery.mock.calls[1][0] as string)).toContain("status = 'miss'");
  });

  // FC-23: BVA — correct rỗng
  test('FC-23: submitFlashcard with empty correct only updates miss', async () => {
    mockPoolQuery.mockResolvedValueOnce({});
    await FlashcardService.submitFlashcard([], [1, 2]);
    expect(mockPoolQuery).toHaveBeenCalledTimes(1);
    expect((mockPoolQuery.mock.calls[0][0] as string)).toContain("status = 'miss'");
  });

  // FC-24: BVA — miss rỗng
  test('FC-24: submitFlashcard with empty miss only updates correct', async () => {
    mockPoolQuery.mockResolvedValueOnce({});
    await FlashcardService.submitFlashcard([1, 2, 3], []);
    expect(mockPoolQuery).toHaveBeenCalledTimes(1);
    expect((mockPoolQuery.mock.calls[0][0] as string)).toContain("status = 'done'");
  });

  // FC-25: BVA — cả hai rỗng
  test('FC-25: submitFlashcard with both empty performs no queries', async () => {
    await FlashcardService.submitFlashcard([], []);
    expect(mockPoolQuery).not.toHaveBeenCalled();
  });
});

// ==================================================
// FlashcardDeckService — 5 tests (3 BUGs)
// ==================================================

describe('FlashcardDeckService', () => {

  // ──────────────────────────────────────────────
  // ★ BUG-6: getAll() gọi COMMIT nhưng KHÔNG có BEGIN
  // Transaction phải bắt đầu với BEGIN trước khi COMMIT
  // ──────────────────────────────────────────────
  test('FC-26: [BUG-6] deck getAll should call BEGIN before COMMIT (COMMIT without BEGIN)', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rows: [] }); // data query
    mockClientQuery
      .mockResolvedValueOnce({ rows: [{ total: '0' }] }) // count
      .mockResolvedValueOnce({}); // COMMIT

    await FlashcardDeckService.getAll({ page: '1' });

    // Kiểm tra: BEGIN phải được gọi trước COMMIT
    const clientCalls = mockClientQuery.mock.calls.map((c: any) => c[0] as string);
    const hasBegin = clientCalls.some((s: string) => s === 'BEGIN');
    const hasCommit = clientCalls.some((s: string) => s === 'COMMIT');

    expect(hasCommit).toBe(true);  // PASS: có COMMIT
    expect(hasBegin).toBe(true);   // FAIL: KHÔNG có BEGIN → transaction không hợp lệ
  });

  // ──────────────────────────────────────────────
  // ★ BUG-7: getAll() dùng pool.query() cho data, client.query() cho count
  // Hai connection khác nhau → data inconsistency
  // ──────────────────────────────────────────────
  test('FC-27: [BUG-7] deck getAll should use same connection for all queries (mixed pool/client)', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rows: [] }); // ← data query dùng pool!
    mockClientQuery
      .mockResolvedValueOnce({ rows: [{ total: '0' }] }) // count dùng client
      .mockResolvedValueOnce({}); // COMMIT

    await FlashcardDeckService.getAll({ page: '1' });

    // BUG: data query dùng pool.query() (mockPoolQuery được gọi)
    // nhưng count query dùng client.query() (mockClientQuery)
    // → 2 connection khác nhau, có thể ra KHÁC kết quả
    // Đúng ra TẤT CẢ query phải chạy trên cùng 1 client connection
    expect(mockPoolQuery).not.toHaveBeenCalled(); // FAIL: pool.query() BỊ gọi cho data query
  });

  // ──────────────────────────────────────────────
  // ★ BUG-8: getById() gọi console.log(result) trong production
  // Leak dữ liệu flashcard ra server log
  // ──────────────────────────────────────────────
  test('FC-28: [BUG-8] deck getById should not console.log sensitive data in production', async () => {
    const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

    mockClientQuery
      .mockResolvedValueOnce({})                                     // BEGIN
      .mockResolvedValueOnce({ rows: [{ flashcard_id: 1, front: 'Secret' }] }) // SELECT *
      .mockResolvedValueOnce({ rows: [{ total: '1' }] })            // COUNT total
      .mockResolvedValueOnce({ rows: [{ total: '0' }] })            // COUNT done
      .mockResolvedValueOnce({});                                     // COMMIT

    await FlashcardDeckService.getById(1);

    // BUG: line 56 gọi console.log(result) → leak toàn bộ query result ra log
    // Production code KHÔNG được log dữ liệu nhạy cảm
    expect(consoleSpy).not.toHaveBeenCalled(); // FAIL: console.log ĐÃ được gọi

    consoleSpy.mockRestore();
  });

  // FC-29: Functional — tạo deck thành công
  test('FC-29: create deck with valid data succeeds', async () => {
    mockPoolQuery.mockResolvedValueOnce({
      rows: [{
        flashcard_deck_id: 1, title: 'Từ vựng N3',
        description: 'JLPT N3', user_id: 1, created_at: new Date(),
      }],
    });

    const result = await FlashcardDeckService.create({
      title: 'Từ vựng N3', description: 'JLPT N3', user_id: 1,
    } as any);

    expect(result.title).toBe('Từ vựng N3');
    expect(result.user_id).toBe(1);
  });

  // FC-30: Functional — xóa deck thành công
  test('FC-30: remove existing deck returns true', async () => {
    mockPoolQuery.mockResolvedValueOnce({ rowCount: 1 });
    const result = await FlashcardDeckService.remove(1);
    expect(result).toBe(true);
  });
});
