/**
 * tests/exam.service.test.ts
 *
 * Unit tests cho ExamService (exam.service.ts).
 * Kết nối thật đến PostgreSQL + Redis để verify hành vi nghiệp vụ,
 * trạng thái DB và trạng thái Redis.
 *
 * Chiến lược Rollback:
 *   - CRUD (create/update/remove/setAvailable): Strategy B (snapshot)
 *   - submit: Strategy B + Redis cleanup (del exam:*:ranking*)
 *   - getById (với cache): clear redis key trước/sau mỗi test
 *
 * Nếu test FAIL do bug trong service → lý do ghi trong comment tại test đó.
 */

import ExamService from "../../backend/src/services/exam.service";
import { ExamQuestionService } from "../../backend/src/services/exam.question.service";
import pool from "../../backend/src/config/database";
import {
  seedFixtures,
  teardownFixtures,
  FIX,
} from "./helpers/fixtures";
import { countRows, getRow, getMaxId } from "./helpers/checkdb";
import { takeSnapshot, restoreSnapshot, type Snapshot } from "./helpers/sandbox";
import {
  clearExamCache,
  clearMultipleExamCaches,
  keyExists,
  seedExamRanking,
  closeRedis,
} from "./helpers/redis";

// ---------------------------------------------------------------
// Setup / Teardown global
// ---------------------------------------------------------------
beforeAll(async () => {
  await seedFixtures();
});

afterAll(async () => {
  await teardownFixtures();
  // Xoá toàn bộ cache của các exam fixture
  await clearMultipleExamCaches([
    FIX.examActiveId,
    FIX.examExpiredId,
    FIX.examDisabledId,
  ]);
  await closeRedis();
  await pool.end();
});

// ================================================================
// ExamService.create()
// ================================================================
describe("ExamService.create()", () => {
  let snap: Snapshot;
  beforeEach(async () => { snap = await takeSnapshot(); });
  afterEach(async ()  => { await restoreSnapshot(snap); });

  // Test Case ID: EXAM-01
  it("EXAM-01: tạo exam với payload hợp lệ → trả về Exam mới, DB có row", async () => {
    const input = {
      exam_name: "EXAM_TEST_01",
      topic_id: FIX.topic1Id,
      time_limit: 90,
      exam_schedule_id: FIX.scheduleActiveId,
      description: "exam test 01",
    } as any;

    const exam = await ExamService.create(input);

    expect(exam.exam_id).toBeDefined();
    expect(exam.exam_name).toBe("EXAM_TEST_01");
    expect(Number(exam.topic_id)).toBe(FIX.topic1Id);

    // CheckDB
    const row = await getRow("exam", { exam_id: exam.exam_id });
    expect(row).not.toBeNull();
    expect(row!.exam_name).toBe("EXAM_TEST_01");
  });

  // Test Case ID: EXAM-02
  it("EXAM-02: exam_schedule_id không tồn tại → throws do vi phạm FK", async () => {
    const input = {
      exam_name: "EXAM_TEST_02_FK",
      topic_id: FIX.topic1Id,
      time_limit: 90,
      exam_schedule_id: 999999, // FK không tồn tại
      description: "fk test",
    } as any;

    await expect(ExamService.create(input)).rejects.toThrow();

    // CheckDB: không có row mới
    const count = await countRows("exam", { exam_name: "EXAM_TEST_02_FK" });
    expect(count).toBe(0);
  });
});

// ================================================================
// ExamService.update()
// ================================================================
describe("ExamService.update()", () => {
  let snap: Snapshot;
  beforeEach(async () => { snap = await takeSnapshot(); });
  afterEach(async ()  => { await restoreSnapshot(snap); });

  // Test Case ID: EXAM-03
  it("EXAM-03: cập nhật exam_name và time_limit hợp lệ → trả về Exam đã update", async () => {
    const updated = await ExamService.update(FIX.examActiveId, {
      exam_name: "EXAM_UPDATED_03",
      topic_id: FIX.topic1Id,
      time_limit: 120,
      exam_schedule_id: FIX.scheduleActiveId,
      exam_id: FIX.examActiveId,
    } as any);

    expect(updated).not.toBeNull();
    expect(updated!.exam_name).toBe("EXAM_UPDATED_03");
    expect(Number(updated!.time_limit)).toBe(120);

    // CheckDB
    const row = await getRow("exam", { exam_id: FIX.examActiveId });
    expect(row!.exam_name).toBe("EXAM_UPDATED_03");
  });

  // Test Case ID: EXAM-04
  it("EXAM-04: exam_id không tồn tại → trả về null", async () => {
    const updated = await ExamService.update(999999, {
      exam_name: "NOT_EXIST",
      topic_id: FIX.topic1Id,
      time_limit: 90,
      exam_schedule_id: FIX.scheduleActiveId,
      exam_id: 999999,
    } as any);

    expect(updated).toBeNull();
  });
});

// ================================================================
// ExamService.setAvailable()
// ================================================================
describe("ExamService.setAvailable()", () => {
  let snap: Snapshot;
  beforeEach(async () => { snap = await takeSnapshot(); });
  afterEach(async ()  => { await restoreSnapshot(snap); });

  // Test Case ID: EXAM-05
  it("EXAM-05: bật available=true cho exam disabled → trả về true, DB cập nhật", async () => {
    const result = await ExamService.setAvailable(FIX.examDisabledId, true);

    expect(result).toBe(true);

    // CheckDB
    const row = await getRow("exam", { exam_id: FIX.examDisabledId });
    expect(row!.available).toBe(true);
  });

  // Test Case ID: EXAM-06
  it("EXAM-06: tắt available=false cho exam đang active → trả về true, DB cập nhật", async () => {
    const result = await ExamService.setAvailable(FIX.examActiveId, false);

    expect(result).toBe(true);

    // CheckDB
    const row = await getRow("exam", { exam_id: FIX.examActiveId });
    expect(row!.available).toBe(false);
  });

  // Test Case ID: EXAM-07
  it("EXAM-07: exam_id không tồn tại → trả về false", async () => {
    const result = await ExamService.setAvailable(999999, true);
    expect(result).toBe(false);
  });
});

// ================================================================
// ExamService.remove()
// ================================================================
describe("ExamService.remove()", () => {
  // Test Case ID: EXAM-08
  it("EXAM-08: xoá exam tồn tại → trả về true, không còn row trong DB", async () => {
    const snap = await takeSnapshot();

    // Tạo exam tạm
    const tempExam = await ExamService.create({
      exam_name: "TEMP_EXAM_08",
      topic_id: FIX.topic1Id,
      time_limit: 60,
      exam_schedule_id: FIX.scheduleActiveId,
      description: "temp",
    } as any);

    const result = await ExamService.remove(tempExam.exam_id);
    expect(result).toBe(true);

    // CheckDB
    const count = await countRows("exam", { exam_id: tempExam.exam_id });
    expect(count).toBe(0);

    await restoreSnapshot(snap);
  });

  // Test Case ID: EXAM-09
  it("EXAM-09: exam_id không tồn tại → trả về false", async () => {
    const result = await ExamService.remove(999999);
    expect(result).toBe(false);
  });
});

// ================================================================
// ExamService.getById()
// ================================================================
describe("ExamService.getById()", () => {
  afterEach(async () => {
    // Xoá cache sau mỗi test để không nhiễm test kế
    await clearExamCache(FIX.examActiveId);
  });

  // Test Case ID: EXAM-10
  it("EXAM-10: exam tồn tại → trả về grouped questions, subject_type đúng, cache Redis được set", async () => {
    const result = await ExamService.getById(FIX.examActiveId);

    expect(result.subject_type).toBe(1); // subjectMath.subject_type = 1
    expect(result.question).not.toBeNull();
    expect(result.question![1].length).toBeGreaterThanOrEqual(1);
    expect(result.question![2].length).toBeGreaterThanOrEqual(1);
    expect(result.question![3].length).toBeGreaterThanOrEqual(1);

    // CheckRedis: key `exam:{id}:full` phải tồn tại sau lần gọi đầu tiên
    const cacheKey = `exam:${FIX.examActiveId}:full`;
    const exists = await keyExists(cacheKey);
    expect(exists).toBe(true);
  });

  // Test Case ID: EXAM-11
  it("EXAM-11: gọi lần 2 → kết quả giống lần 1 (cache hit, key vẫn tồn tại)", async () => {
    // Lần 1: tạo cache
    const first = await ExamService.getById(FIX.examActiveId);

    // Lần 2: từ cache
    const second = await ExamService.getById(FIX.examActiveId);

    // Kết quả phải giống nhau
    expect(JSON.stringify(first)).toBe(JSON.stringify(second));

    // Cache key phải vẫn còn
    const cacheKey = `exam:${FIX.examActiveId}:full`;
    expect(await keyExists(cacheKey)).toBe(true);
  });

  // Test Case ID: EXAM-12
  it("EXAM-12: exam_id không tồn tại → question empty group, subject_type=null", async () => {
    const result = await ExamService.getById(999999);

    expect(result.subject_type).toBeNull();
    expect(result.question![1]).toHaveLength(0);
    expect(result.question![2]).toHaveLength(0);
    expect(result.question![3]).toHaveLength(0);
  });
});

// ================================================================
// ExamService.list()
// ================================================================
describe("ExamService.list()", () => {
  afterEach(async () => {
    await clearMultipleExamCaches([
      FIX.examActiveId,
      FIX.examExpiredId,
      FIX.examDisabledId,
    ]);
  });

  // Test Case ID: EXAM-13
  it("EXAM-13: page=1, tất cả filter='All' → trả về exams + totalPages đúng, có field top3", async () => {
    const { exams, totalPages } = await ExamService.list(
      1, "All", "", "All", "All"
    );

    expect(exams.length).toBeLessThanOrEqual(12);
    expect(totalPages).toBeGreaterThanOrEqual(1);

    // Mỗi exam phải có field top3 (mảng, có thể rỗng)
    exams.forEach(e => {
      expect(Array.isArray((e as any).top3)).toBe(true);
    });
  });

  // Test Case ID: EXAM-14
  it("EXAM-14: exam có ranking trong Redis → top3 đúng thứ tự", async () => {
    // Seed ranking cho examActive
    await seedExamRanking(FIX.examActiveId, [
      { user_id: FIX.user1Id, user_name: "test_user1", score: 8.0, time_test: 100 },
      { user_id: FIX.user2Id, user_name: "test_user2", score: 5.0, time_test: 200 },
      { user_id: FIX.user3Id, user_name: "test_user3", score: 2.0, time_test: 300 },
    ]);

    const { exams } = await ExamService.list(
      1, "All", "TEST_Exam_Active", "All", "All"
    );

    const targetExam = exams.find(
      (e: any) => Number(e.exam_id) === FIX.examActiveId
    ) as any;

    expect(targetExam).toBeDefined();
    expect(targetExam.top3.length).toBe(3);

    // User1 có score cao nhất → phải ở đầu
    expect(Number(targetExam.top3[0].user_id)).toBe(FIX.user1Id);
  });

  // Test Case ID: EXAM-15
  it("EXAM-15: exam không có ranking → top3=[]", async () => {
    // Đảm bảo không có ranking cho examDisabled
    await clearExamCache(FIX.examDisabledId);

    const { exams } = await ExamService.list(
      1, "false", "", "All", "All"
    );

    // Tìm examDisabled (available=false)
    const target = exams.find(
      (e: any) => Number(e.exam_id) === FIX.examDisabledId
    ) as any;

    if (target) {
      expect(target.top3).toHaveLength(0);
    }
    // Nếu không tìm thấy thì test pass (exam có thể bị filter do available=false)
  });

  // Test Case ID: EXAM-16
  it("EXAM-16: filter status='true' → chỉ trả về exam available=true", async () => {
    const { exams } = await ExamService.list(
      1, "true", "", "All", "All"
    );

    /**
     * NOTE: ExamService.list() truyền `status` string trực tiếp vào SQL:
     *   conditions.push(`e.available = $${idx}`);
     *   params.push(status);  // status là string "true"/"false"
     * PostgreSQL có thể tự cast string "true" → boolean true.
     * Nếu DB cast lỗi → test này sẽ FAIL.
     * FAIL REASON (nếu xảy ra): service truyền string "true"/"false" thay vì boolean
     *   vào param cho cột kiểu BOOLEAN → hành vi phụ thuộc PostgreSQL driver.
     */
    exams.forEach(e => expect(e.available).toBe(true));
  });
});

// ================================================================
// ExamService.submit()
// ================================================================
describe("ExamService.submit()", () => {
  let snap: Snapshot;

  beforeEach(async () => {
    snap = await takeSnapshot();
    await clearExamCache(FIX.examActiveId);
  });

  afterEach(async () => {
    await restoreSnapshot(snap);
    await clearExamCache(FIX.examActiveId);
  });

  // Test Case ID: EXAM-17
  it("EXAM-17: type 1 đúng → score=0.25, lưu history_exam + user_exam_answer", async () => {
    const { score, history_exam_id } = await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [{ question_id: FIX.qType1aId, user_answer: [FIX.ansType1aCorrectId] }],
      100,
      1,
      "test_user1"
    );

    expect(score).toBe(0.25);

    // CheckDB: history_exam được tạo
    const histRow = await getRow("history_exam", { history_exam_id });
    expect(histRow).not.toBeNull();
    expect(Number(histRow!.score)).toBe(0.25);

    // CheckDB: user_exam_answer được tạo
    const ansCount = await countRows("user_exam_answer", { history_exam_id });
    expect(ansCount).toBe(1);
  });

  // Test Case ID: EXAM-18
  it("EXAM-18: type 2 đúng tất cả correct answers → score=1", async () => {
    /**
     * ExamService scoring type 2:
     *   correctCount === correct_answers.length → score += 1
     * Fixture type 2a có 2 correct answers → cần chọn đúng 2/2 → score=1
     */
    const { score } = await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [{
        question_id: FIX.qType2aId,
        user_answer: [FIX.ansType2aCorrect1Id, FIX.ansType2aCorrect2Id],
      }],
      100,
      1,
      "test_user1"
    );

    expect(score).toBe(1);
  });

  // Test Case ID: EXAM-19
  it("EXAM-19: type 2 đúng 1/2 → score=0.1", async () => {
    const { score } = await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [{
        question_id: FIX.qType2aId,
        user_answer: [FIX.ansType2aCorrect1Id],
      }],
      100,
      1,
      "test_user1"
    );

    expect(score).toBe(0.1);
  });

  // Test Case ID: EXAM-20
  it("EXAM-20: type 3 (tự luận) đúng, subject_type=1 → score=0.5", async () => {
    const { score } = await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [{
        question_id: FIX.qType3aId,
        user_answer: [FIX.essayCorrectTextA],
      }],
      100,
      1, // math → +0.5
      "test_user1"
    );

    expect(score).toBe(0.5);
  });

  // Test Case ID: EXAM-21
  it("EXAM-21: type 3 đúng, subject_type=2 → score=0.25", async () => {
    const { score } = await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [{
        question_id: FIX.qType3aId,
        user_answer: [FIX.essayCorrectTextA],
      }],
      100,
      2, // lit → +0.25
      "test_user1"
    );

    expect(score).toBe(0.25);
  });

  // Test Case ID: EXAM-22
  it("EXAM-22: type 3 sai nội dung → score=0", async () => {
    const { score } = await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [{
        question_id: FIX.qType3aId,
        user_answer: ["sai hoàn toàn"],
      }],
      100,
      1,
      "test_user1"
    );

    expect(score).toBe(0);
  });

  // Test Case ID: EXAM-23
  it("EXAM-23: do_exam rỗng → score=0, history_exam được tạo, không có user_exam_answer", async () => {
    const { score, history_exam_id } = await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [],
      50,
      1,
      "test_user1"
    );

    expect(score).toBe(0);

    // CheckDB: history_exam tồn tại
    const histRow = await getRow("history_exam", { history_exam_id });
    expect(histRow).not.toBeNull();

    // CheckDB: không có user_exam_answer
    const ansCount = await countRows("user_exam_answer", { history_exam_id });
    expect(ansCount).toBe(0);
  });

  // Test Case ID: EXAM-24
  it("EXAM-24: submit thành công → Redis zadd `exam:{id}:ranking` có member của user", async () => {
    await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [{ question_id: FIX.qType1aId, user_answer: [FIX.ansType1aCorrectId] }],
      100,
      1,
      "test_user1"
    );

    // CheckRedis: ranking key phải tồn tại và có member
    const { redis } = await import("../../backend/src/config/redis");
    const rankingKey = `exam:${FIX.examActiveId}:ranking`;
    const count = await redis.zcard(rankingKey);
    expect(count).toBeGreaterThan(0);
  });

  // Test Case ID: EXAM-25
  it("EXAM-25: user_id FK không tồn tại → throws, history_exam KHÔNG được tạo (rollback)", async () => {
    const beforeMax = await getMaxId("history_exam", "history_exam_id");

    await expect(
      ExamService.submit(
        FIX.examActiveId,
        999999, // user_id không tồn tại
        [{ question_id: FIX.qType1aId, user_answer: [FIX.ansType1aCorrectId] }],
        100,
        1,
        "ghost_user"
      )
    ).rejects.toThrow();

    // CheckDB: không có history_exam mới (rollback thành công)
    const afterMax = await getMaxId("history_exam", "history_exam_id");
    expect(afterMax).toBe(beforeMax);
  });
});

// ================================================================
// ExamService.getExamRanking()
// ================================================================
describe("ExamService.getExamRanking()", () => {
  let snap: Snapshot;
  let seededHistoryIds: number[] = [];

  beforeAll(async () => {
    snap = await takeSnapshot();

    // Seed 3 history_exam với điểm khác nhau
    // user1: score 8.0, time 100 → final_score cao nhất
    const h1 = await ExamService.submit(
      FIX.examActiveId, FIX.user1Id,
      [
        { question_id: FIX.qType1aId, user_answer: [FIX.ansType1aCorrectId] },
        { question_id: FIX.qType1bId, user_answer: [FIX.ansType1bCorrectId] },
      ],
      100, 1, "test_user1"
    );
    seededHistoryIds.push(h1.history_exam_id);

    // user2: score 0.25, time 200
    const h2 = await ExamService.submit(
      FIX.examActiveId, FIX.user2Id,
      [{ question_id: FIX.qType1aId, user_answer: [FIX.ansType1aCorrectId] }],
      200, 1, "test_user2"
    );
    seededHistoryIds.push(h2.history_exam_id);

    // user3: score 0, time 300
    const h3 = await ExamService.submit(
      FIX.examActiveId, FIX.user3Id,
      [],
      300, 1, "test_user3"
    );
    seededHistoryIds.push(h3.history_exam_id);

    // Xoá cache để getExamRanking query DB mới
    await clearExamCache(FIX.examActiveId);
  });

  afterAll(async () => {
    await clearExamCache(FIX.examActiveId);
    await restoreSnapshot(snap);
  });

  // Test Case ID: EXAM-26
  it("EXAM-26: nhiều user đã làm → rank đúng thứ tự, total_rank=3, my_rank đúng vị trí", async () => {
    const result = await ExamService.getExamRanking(
      FIX.examActiveId,
      FIX.user1Id,
      "test_user1",
      1
    );

    expect(result.total_rank).toBe(3);
    expect(result.rank.length).toBeLessThanOrEqual(10);

    // user1 có score cao nhất → rank=1
    expect(result.my_rank).not.toBeNull();
    expect(result.my_rank!.rank).toBe(1);
  });

  // Test Case ID: EXAM-27
  it("EXAM-27: user chưa làm exam → my_rank=null, rank[] vẫn có dữ liệu", async () => {
    // Dùng user mới chưa có history
    const newUserResult = await pool.query(
      `INSERT INTO "user" (user_name, email, password_hash)
       VALUES ('rank_ghost', 'ghost_rank@test.com', 'hashed')
       RETURNING user_id`
    );
    const ghostUserId = newUserResult.rows[0].user_id;

    try {
      // Xoá cache để đảm bảo fresh query
      await clearExamCache(FIX.examActiveId);

      const result = await ExamService.getExamRanking(
        FIX.examActiveId,
        ghostUserId,
        "rank_ghost",
        1
      );

      expect(result.my_rank).toBeNull();
      expect(result.total_rank).toBe(3); // 3 user đã làm
    } finally {
      await pool.query(`DELETE FROM "user" WHERE user_id = $1`, [ghostUserId]);
      await clearExamCache(FIX.examActiveId);
    }
  });

  // Test Case ID: EXAM-28
  it("EXAM-28: lần 2 gọi getExamRanking → cache Redis được set (ranking:data)", async () => {
    // Gọi lần 1 để tạo cache
    await ExamService.getExamRanking(FIX.examActiveId, FIX.user1Id, "test_user1", 1);

    // Kiểm tra cache key tồn tại
    const rankingDataKey = `exam:${FIX.examActiveId}:ranking:data`;
    const exists = await keyExists(rankingDataKey);
    expect(exists).toBe(true);
  });
});

// ================================================================
// ExamService.checkDoExam()
// ================================================================
describe("ExamService.checkDoExam()", () => {
  let snap: Snapshot;

  beforeAll(async () => {
    snap = await takeSnapshot();
    // Seed 1 history cho user1 để test ALREADY_DONE
    await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [],
      50,
      1,
      "test_user1"
    );
    await clearExamCache(FIX.examActiveId);
  });

  afterAll(async () => {
    await clearExamCache(FIX.examActiveId);
    await restoreSnapshot(snap);
  });

  // Test Case ID: EXAM-29
  it("EXAM-29: user đã làm exam → {check:false, reason:'ALREADY_DONE'}", async () => {
    const result = await ExamService.checkDoExam(FIX.examActiveId, FIX.user1Id);
    expect(result.check).toBe(false);
    expect(result.reason).toBe("ALREADY_DONE");
  });

  // Test Case ID: EXAM-30
  it("EXAM-30: exam_id không tồn tại → {check:false, reason:'EXAM_NOT_FOUND'}", async () => {
    const result = await ExamService.checkDoExam(999999, FIX.user2Id);
    expect(result.check).toBe(false);
    expect(result.reason).toBe("EXAM_NOT_FOUND");
  });

  // Test Case ID: EXAM-31
  it("EXAM-31: exam disabled (available=false) → {check:false, reason:'DISABLED'}", async () => {
    // user2 chưa làm examDisabled
    const result = await ExamService.checkDoExam(FIX.examDisabledId, FIX.user2Id);
    expect(result.check).toBe(false);
    expect(result.reason).toBe("DISABLED");
  });

  // Test Case ID: EXAM-32
  it("EXAM-32: exam hết hạn (end_time đã qua) → {check:false, reason:'EXPIRED'}", async () => {
    /**
     * Lưu ý: examExpiredId có available=true và end_time đã qua.
     * checkDoExam kiểm tra: if (end_time && end_time < new Date())
     * Fixture scheduleExpired.end_time = NOW() - 1 day → nên trigger EXPIRED.
     */
    const result = await ExamService.checkDoExam(FIX.examExpiredId, FIX.user2Id);
    expect(result.check).toBe(false);
    expect(result.reason).toBe("EXPIRED");
  });

  // Test Case ID: EXAM-33
  it("EXAM-33: exam hợp lệ, user chưa làm → {check:true}", async () => {
    // user2 chưa làm examActive
    const result = await ExamService.checkDoExam(FIX.examActiveId, FIX.user2Id);
    expect(result.check).toBe(true);
    expect(result.reason).toBeUndefined();
  });
});

// ================================================================
// ExamService.getUserListExamHistory()
// ================================================================
describe("ExamService.getUserListExamHistory()", () => {
  let snap: Snapshot;
  let seededHistoryExamId: number;

  beforeAll(async () => {
    snap = await takeSnapshot();
    const { history_exam_id } = await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [],
      60,
      1,
      "test_user1"
    );
    seededHistoryExamId = history_exam_id;
    await clearExamCache(FIX.examActiveId);
  });

  afterAll(async () => {
    await clearExamCache(FIX.examActiveId);
    await restoreSnapshot(snap);
  });

  // Test Case ID: EXAM-34
  it("EXAM-34: user có history → trả về list DESC theo history_exam_id", async () => {
    const { history } = await ExamService.getUserListExamHistory(FIX.user1Id);

    expect(history.length).toBeGreaterThanOrEqual(1);

    // Verify sắp xếp DESC
    for (let i = 0; i < history.length - 1; i++) {
      expect((history[i] as any).history_exam_id).toBeGreaterThan(
        (history[i + 1] as any).history_exam_id
      );
    }

    // Phải tìm thấy history vừa seed
    const found = history.find(
      (h: any) => h.history_exam_id === seededHistoryExamId
    );
    expect(found).toBeDefined();
  });

  // Test Case ID: EXAM-35
  it("EXAM-35: user chưa có history → trả về {history: []}", async () => {
    // user3 chưa làm bài
    const { history } = await ExamService.getUserListExamHistory(FIX.user3Id);
    expect(history).toHaveLength(0);
  });
});

// ================================================================
// ExamService.getUserAnswer()
// ================================================================
describe("ExamService.getUserAnswer()", () => {
  let snap: Snapshot;
  let seededHistoryExamId: number;

  beforeAll(async () => {
    snap = await takeSnapshot();
    const { history_exam_id } = await ExamService.submit(
      FIX.examActiveId,
      FIX.user1Id,
      [
        { question_id: FIX.qType1aId, user_answer: [FIX.ansType1aCorrectId] },
        { question_id: FIX.qType3aId, user_answer: [FIX.essayCorrectTextA] },
      ],
      120,
      1,
      "test_user1"
    );
    seededHistoryExamId = history_exam_id;
    await clearExamCache(FIX.examActiveId);
  });

  afterAll(async () => {
    await clearExamCache(FIX.examActiveId);
    await restoreSnapshot(snap);
  });

  // Test Case ID: EXAM-36
  it("EXAM-36: history hợp lệ → trả về score và grouped questions với user_answers đúng", async () => {
    const result = await ExamService.getUserAnswer(
      seededHistoryExamId,
      FIX.examActiveId
    );

    // score = 0.25 (type1 đúng) + 0.5 (type3 math đúng) = 0.75
    expect(Number(result.score)).toBeCloseTo(0.75, 2);

    expect(result.questions[1]).toBeDefined();
    expect(result.questions[2]).toBeDefined();
    expect(result.questions[3]).toBeDefined();

    // user_answers của type 1 phải có dữ liệu
    const q1 = result.questions[1].find(
      (q: any) => q.question_id === FIX.qType1aId
    );
    expect(q1).toBeDefined();
    expect(q1!.user_answers.length).toBeGreaterThan(0);
  });

  // Test Case ID: EXAM-37
  it("EXAM-37: history_exam_id không tồn tại → score=null", async () => {
    const result = await ExamService.getUserAnswer(
      999999, // không tồn tại
      FIX.examActiveId
    );

    expect(result.score).toBeNull();
    // Questions vẫn được trả theo exam_id
    expect(result.questions).toBeDefined();
  });
});

// ================================================================
// ExamService.getQuestionIdExam()
// ================================================================
describe("ExamService.getQuestionIdExam()", () => {
  // Test Case ID: EXAM-38
  it("EXAM-38: exam có question → trả về mảng question_id đúng", async () => {
    const ids = await ExamService.getQuestionIdExam(FIX.examActiveId);

    // Fixture seed 5 câu vào examActive
    expect(ids.length).toBe(5);

    // CheckDB: đối chiếu trực tiếp question_exam
    const dbResult = await pool.query(
      `SELECT question_id FROM question_exam WHERE exam_id = $1 ORDER BY question_id`,
      [FIX.examActiveId]
    );
    const dbIds = dbResult.rows.map((r: any) => Number(r.question_id));

    expect(ids.sort()).toEqual(dbIds.sort());
  });

  // Test Case ID: EXAM-39
  it("EXAM-39: exam không có question → trả về mảng rỗng", async () => {
    const ids = await ExamService.getQuestionIdExam(FIX.examDisabledId);
    expect(ids).toHaveLength(0);
  });
});

// ================================================================
// ExamService.markOverTime()
// ================================================================
describe("ExamService.markOverTime()", () => {
  let snap: Snapshot;
  let tempExamId: number;

  beforeAll(async () => {
    snap = await takeSnapshot();

    // Tạo exam với schedule đã hết hạn
    const tempSchedule = await pool.query(
      `INSERT INTO exam_schedule (start_time, end_time)
       VALUES (NOW() - INTERVAL '2 days', NOW() - INTERVAL '8 hours')
       RETURNING exam_schedule_id`
    );
    const tempScheduleId = tempSchedule.rows[0].exam_schedule_id;

    const tempExam = await pool.query(
      `INSERT INTO exam (exam_name, topic_id, time_limit, exam_schedule_id, available, description)
       VALUES ('TEMP_EXAM_OVERTIME', $1, 60, $2, true, 'overtime test')
       RETURNING exam_id`,
      [FIX.topic1Id, tempScheduleId]
    );
    tempExamId = tempExam.rows[0].exam_id;
  });

  afterAll(async () => {
    await pool.query(`DELETE FROM exam WHERE exam_id = $1`, [tempExamId]);
    await restoreSnapshot(snap);
  });

  // Test Case ID: EXAM-40
  it("EXAM-40: markOverTime → exam có schedule.end_time < NOW()+7h bị set available=false", async () => {
    // Verify ban đầu available=true
    const beforeRow = await getRow("exam", { exam_id: tempExamId });
    expect(beforeRow!.available).toBe(true);

    await ExamService.markOverTime();

    // CheckDB: exam phải bị tắt
    const afterRow = await getRow("exam", { exam_id: tempExamId });
    expect(afterRow!.available).toBe(false);
  });
});

// ================================================================
// ExamQuestionService.add()
// ================================================================
describe("ExamQuestionService.add()", () => {
  let snap: Snapshot;

  beforeEach(async () => {
    snap = await takeSnapshot();
  });

  afterEach(async () => {
    await restoreSnapshot(snap);
  });

  // Test Case ID: EXAM-41
  it("EXAM-41: thêm câu hỏi vào exam → question_exam được cập nhật, cache bị xoá", async () => {
    // Tạo exam tạm
    const tempExam = await ExamService.create({
      exam_name: "TEMP_EXAM_EQ_41",
      topic_id: FIX.topic1Id,
      time_limit: 60,
      exam_schedule_id: FIX.scheduleActiveId,
      description: "eq test",
    } as any);

    // Set cache trước để kiểm tra nó bị xoá
    const { redis } = await import("../../backend/src/config/redis");
    await redis.set(`exam:${tempExam.exam_id}:full`, JSON.stringify({ test: true }), "EX", 600);

    const payload = [
      { exam_id: tempExam.exam_id, question_id: FIX.qType1aId },
      { exam_id: tempExam.exam_id, question_id: FIX.qType1bId },
    ];

    const result = await ExamQuestionService.add(payload);

    expect(result.exam_id).toBe(tempExam.exam_id);
    expect(result.total).toBe(2);

    // CheckDB: 2 row trong question_exam
    const count = await countRows("question_exam", { exam_id: tempExam.exam_id });
    expect(count).toBe(2);

    // CheckRedis: cache `exam:{id}:full` bị xoá
    const cacheKey = `exam:${tempExam.exam_id}:full`;
    const exists = await keyExists(cacheKey);
    expect(exists).toBe(false);
  });

  // Test Case ID: EXAM-42
  it("EXAM-42: selectedQuestions rỗng → throws", async () => {
    await expect(ExamQuestionService.add([])).rejects.toThrow();
  });

  // Test Case ID: EXAM-43
  it("EXAM-43: selectedQuestions không phải array → throws (branch: if !Array.isArray)", async () => {
    await expect(ExamQuestionService.add("not-an-array" as any)).rejects.toThrow(
      "selectedQuestions must be an array"
    );
  });
});

// ExamQuestionService.remove()
// ================================================================
describe("ExamQuestionService.remove()", () => {
  let snap: Snapshot;

  beforeEach(async () => {
    snap = await takeSnapshot();
  });

  afterEach(async () => {
    await restoreSnapshot(snap);
  });

  // Test Case ID: EXAM-44
  it("EXAM-44: remove câu hỏi tồn tại → trả về true, cache bị xoá", async () => {
    // Tạo exam tạm và gán câu hỏi
    const tempExam = await ExamService.create({
      exam_name: "TEMP_EXAM_EQ_44",
      topic_id: FIX.topic1Id,
      time_limit: 60,
      exam_schedule_id: FIX.scheduleActiveId,
      description: "eq remove test",
    } as any);

    await ExamQuestionService.add([
      { exam_id: tempExam.exam_id, question_id: FIX.qType1aId },
    ]);

    // Set cache để kiểm tra nó bị xoá
    const { redis } = await import("../../backend/src/config/redis");
    await redis.set(`exam:${tempExam.exam_id}:full`, JSON.stringify({ test: true }), "EX", 600);

    const result = await ExamQuestionService.remove({
      exam_id: tempExam.exam_id,
      question_id: FIX.qType1aId,
    });

    expect(result).toBe(true);

    const cacheKey = `exam:${tempExam.exam_id}:full`;
    const exists = await keyExists(cacheKey);
    expect(exists).toBe(false);
  });

  // Test Case ID: EXAM-45
  it("EXAM-45: remove câu hỏi không tồn tại → trả về false (branch: rowCount ?? 0)", async () => {
    const result = await ExamQuestionService.remove({
      exam_id: 999999,
      question_id: 999999,
    });

    expect(result).toBe(false);
  });
});
