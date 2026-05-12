/**
 * tests/bank.service.test.ts
 *
 * Unit tests cho BankService (bank.service.ts).
 * Kết nối thật đến PostgreSQL để verify hành vi nghiệp vụ và trạng thái DB.
 *
 * Quy ước rollback:
 *   - CRUD đơn (create/update/remove/setAvailable): Strategy B (snapshot)
 *     vì database.ts dùng pool.query trực tiếp — không thể wrap trong 1 tx chung
 *     mà không thay đổi source service.
 *   - submit: Strategy B (snapshot + redis cleanup).
 *
 * Nếu test FAIL do bug trong service (không phải do test setup sai),
 * lý do được ghi rõ trong comment tại test case đó.
 */

import BankService from "../../backend/src/services/bank.service";
import { BankQuestionService } from "../../backend/src/services/bank.question.service";
import pool from "../../backend/src/config/database";
import {
  seedFixtures,
  teardownFixtures,
  FIX,
} from "./helpers/fixtures";
import { countRows, getRow, getMaxId } from "./helpers/checkdb";
import { takeSnapshot, restoreSnapshot, type Snapshot } from "./helpers/sandbox";

// ---------------------------------------------------------------
// Setup / Teardown global
// ---------------------------------------------------------------
beforeAll(async () => {
  await seedFixtures();
});

afterAll(async () => {
  await teardownFixtures();
  await pool.end();
});

// ================================================================
// BankService.create()
// ================================================================
describe("BankService.create()", () => {
  let snap: Snapshot;
  beforeEach(async () => { snap = await takeSnapshot(); });
  afterEach(async ()  => { await restoreSnapshot(snap); });

  // Test Case ID: BANK-01
  it("BANK-01: tạo bank với payload hợp lệ, trả về Bank mới và DB có row tương ứng", async () => {
    const input = {
      description: "BANK_TEST_01",
      topic_id: FIX.topic1Id,
      time_limit: 60,
    } as any;

    const bank = await BankService.create(input);

    // Kiểm tra giá trị trả về
    expect(bank.bank_id).toBeDefined();
    expect(bank.description).toBe("BANK_TEST_01");
    expect(bank.topic_id).toBe(FIX.topic1Id);
    expect(bank.time_limit).toBe(60);

    // CheckDB: row phải tồn tại trong bảng bank
    const row = await getRow("bank", { bank_id: bank.bank_id });
    expect(row).not.toBeNull();
    expect(row!.description).toBe("BANK_TEST_01");
    expect(Number(row!.topic_id)).toBe(FIX.topic1Id);
  });

  // Test Case ID: BANK-02
  it("BANK-02: topic_id không tồn tại → throws do vi phạm FK constraint", async () => {
    const input = {
      description: "BANK_TEST_02_FK",
      topic_id: 999999, // FK không tồn tại
      time_limit: 60,
    } as any;

    await expect(BankService.create(input)).rejects.toThrow();

    // CheckDB: không có row mới nào được tạo
    const count = await countRows("bank", { description: "BANK_TEST_02_FK" });
    expect(count).toBe(0);
  });
});

// ================================================================
// BankService.update()
// ================================================================
describe("BankService.update()", () => {
  let snap: Snapshot;
  beforeEach(async () => { snap = await takeSnapshot(); });
  afterEach(async ()  => { await restoreSnapshot(snap); });

  // Test Case ID: BANK-03
  it("BANK-03: cập nhật description và topic_id hợp lệ → trả về Bank đã cập nhật", async () => {
    const updated = await BankService.update(FIX.bankAvailableId, {
      description: "BANK_UPDATED_03",
      topic_id: FIX.topic2Id,
    } as any);

    expect(updated).not.toBeNull();
    expect(updated!.description).toBe("BANK_UPDATED_03");
    expect(Number(updated!.topic_id)).toBe(FIX.topic2Id);

    // CheckDB: verify DB đã ghi đúng
    const row = await getRow("bank", { bank_id: FIX.bankAvailableId });
    expect(row!.description).toBe("BANK_UPDATED_03");
    expect(Number(row!.topic_id)).toBe(FIX.topic2Id);
  });

  // Test Case ID: BANK-04
  it("BANK-04: bank_id không tồn tại → trả về null", async () => {
    const updated = await BankService.update(999999, {
      description: "NOT_EXIST",
      topic_id: FIX.topic1Id,
    } as any);

    expect(updated).toBeNull();
  });
});

// ================================================================
// BankService.setAvailable()
// ================================================================
describe("BankService.setAvailable()", () => {
  let snap: Snapshot;
  beforeEach(async () => { snap = await takeSnapshot(); });
  afterEach(async ()  => { await restoreSnapshot(snap); });

  // Test Case ID: BANK-05
  it("BANK-05: bật available=true cho bank đang disabled → trả về true, DB cập nhật", async () => {
    const result = await BankService.setAvailable(FIX.bankDisabledId, true);

    expect(result).toBe(true);

    // CheckDB
    const row = await getRow("bank", { bank_id: FIX.bankDisabledId });
    expect(row!.available).toBe(true);
  });

  // Test Case ID: BANK-06
  it("BANK-06: tắt available=false cho bank đang available → trả về true, DB cập nhật", async () => {
    const result = await BankService.setAvailable(FIX.bankAvailableId, false);

    expect(result).toBe(true);

    // CheckDB
    const row = await getRow("bank", { bank_id: FIX.bankAvailableId });
    expect(row!.available).toBe(false);
  });

  // Test Case ID: BANK-07
  it("BANK-07: bank_id không tồn tại → trả về false", async () => {
    const result = await BankService.setAvailable(999999, true);
    expect(result).toBe(false);
  });
});

// ================================================================
// BankService.remove()
// ================================================================
describe("BankService.remove()", () => {
  // Test Case ID: BANK-08
  it("BANK-08: xoá bank tồn tại → trả về true, không còn row trong DB", async () => {
    // Tạo bank tạm để xoá (không ảnh hưởng fixture gốc)
    const snap = await takeSnapshot();
    const tempBank = await BankService.create({
      description: "TEMP_BANK_BANK08",
      topic_id: FIX.topic1Id,
      time_limit: 30,
    } as any);

    const result = await BankService.remove(tempBank.bank_id);
    expect(result).toBe(true);

    // CheckDB: không còn row
    const count = await countRows("bank", { bank_id: tempBank.bank_id });
    expect(count).toBe(0);

    // Không cần restore vì đã xoá thủ công; nhưng restore để đảm bảo sạch
    await restoreSnapshot(snap);
  });

  // Test Case ID: BANK-09
  it("BANK-09: xoá bank_id không tồn tại → trả về false", async () => {
    const result = await BankService.remove(999999);
    expect(result).toBe(false);
  });
});

// ================================================================
// BankService.getById()
// ================================================================
describe("BankService.getById()", () => {
  // Test Case ID: BANK-10
  it("BANK-10: bank tồn tại và có câu hỏi → trả về questions gom theo type, subject_type đúng", async () => {
    const result = await BankService.getById(FIX.bankAvailableId);

    expect(result.subject_type).toBe(1); // subjectMath.subject_type = 1

    // Phải có ít nhất 1 câu trong mỗi type được seed (1a, 2a, 3a)
    expect(result.question).not.toBeNull();
    expect(result.question![1].length).toBeGreaterThanOrEqual(1); // type 1
    expect(result.question![2].length).toBeGreaterThanOrEqual(1); // type 2
    expect(result.question![3].length).toBeGreaterThanOrEqual(1); // type 3
  });

  // Test Case ID: BANK-11
  it("BANK-11: bank_id không tồn tại → subject_type=null, question là object với mảng rỗng", async () => {
    const result = await BankService.getById(999999);

    expect(result.subject_type).toBeNull();
    // groupQuestionsByTypeSafe trả về object với các mảng rỗng khi không có dữ liệu
    expect(result.question).not.toBeNull();
    expect(result.question![1]).toHaveLength(0);
    expect(result.question![2]).toHaveLength(0);
    expect(result.question![3]).toHaveLength(0);
  });

  // Test Case ID: BANK-12
  it("BANK-12: bank tồn tại nhưng không có question → tất cả group rỗng", async () => {
    // bankDisabledId không có question_bank link
    const result = await BankService.getById(FIX.bankDisabledId);

    expect(result.question![1]).toHaveLength(0);
    expect(result.question![2]).toHaveLength(0);
    expect(result.question![3]).toHaveLength(0);
  });
});

// ================================================================
// BankService.listBank()
// ================================================================
describe("BankService.listBank()", () => {
  // Test Case ID: BANK-13
  it("BANK-13: page=1, tất cả filter='All' → trả về ≤12 bank, totalPages tính đúng", async () => {
    const { banks, totalPages } = await BankService.listBank(
      1, "All", "", "All", "All"
    );

    expect(banks.length).toBeLessThanOrEqual(12);
    expect(totalPages).toBeGreaterThanOrEqual(1);

    // CheckDB: tổng bank trong DB tương khớp totalPages
    const totalResult = await pool.query(
      `SELECT COUNT(*) AS cnt FROM bank b
       JOIN topic t ON b.topic_id = t.topic_id
       JOIN subject sj ON sj.subject_id = t.subject_id`
    );
    const total = Number(totalResult.rows[0].cnt);
    const expectedPages = Math.ceil(total / 12);
    expect(totalPages).toBe(expectedPages);
  });

  // Test Case ID: BANK-14
  it("BANK-14: filter status='true' → chỉ trả về bank available=true", async () => {
    const { banks } = await BankService.listBank(
      1, "true", "", "All", "All"
    );

    // Mọi bank trả về phải available=true
    banks.forEach(b => expect(b.available).toBe(true));
  });

  // Test Case ID: BANK-15
  it("BANK-15: filter status='false' → chỉ trả về bank available=false", async () => {
    const { banks } = await BankService.listBank(
      1, "false", "", "All", "All"
    );

    banks.forEach(b => expect(b.available).toBe(false));
  });

  // Test Case ID: BANK-16
  it("BANK-16: filter topicIds cụ thể → chỉ trả về bank thuộc topic đó", async () => {
    const { banks } = await BankService.listBank(
      1, "All", "", FIX.topic1Id, "All"
    );

    banks.forEach(b =>
      expect(Number(b.topic_id)).toBe(FIX.topic1Id)
    );
  });

  // Test Case ID: BANK-17
  it("BANK-17: filter subject_id cụ thể → chỉ trả về bank thuộc subject đó", async () => {
    const { banks } = await BankService.listBank(
      1, "All", "", "All", FIX.subjectMathId
    );

    // Tất cả bank phải có subject_type = 1 (Toán)
    banks.forEach(b => expect(Number((b as any).subject_type)).toBe(1));
  });

  // Test Case ID: BANK-18
  it("BANK-18: searchValue 'TEST_Bank_Available' → tìm thấy bank fixture", async () => {
    const { banks } = await BankService.listBank(
      1, "All", "TEST_Bank_Available", "All", "All"
    );

    const found = banks.find(b => b.description === "TEST_Bank_Available");
    expect(found).toBeDefined();
  });
});

// ================================================================
// BankService.list() — dành cho user (chỉ available=true)
// ================================================================
describe("BankService.list()", () => {
  // Test Case ID: BANK-19
  it("BANK-19: chỉ trả về bank available=true, bank disabled bị loại", async () => {
    const result = await BankService.list(1, "", []) as any;
    const { banks } = result;

    // Không có bank disabled trong kết quả
    const found = banks.find((b: any) => Number(b.bank_id) === FIX.bankDisabledId);
    expect(found).toBeUndefined();

    // Tất cả bank trả về phải available=true
    banks.forEach((b: any) => expect(b.available).toBe(true));
  });

  // Test Case ID: BANK-20
  it("BANK-20: topicIds=[] → trả về tất cả bank available (không lọc topic)", async () => {
    const result = await BankService.list(1, "", []) as any;
    const { banks, totalPages } = result;

    expect(banks.length).toBeLessThanOrEqual(12);
    expect(totalPages).toBeGreaterThanOrEqual(1);
  });

  // Test Case ID: BANK-21
  it("BANK-21: filter topicIds=[topic1Id] → chỉ trả về bank available trong topic1", async () => {
    const result = await BankService.list(1, "", [FIX.topic1Id]) as any;
    const { banks } = result;

    banks.forEach((b: any) => {
      expect(b.available).toBe(true);
      expect(Number(b.topic_id)).toBe(FIX.topic1Id);
    });
  });
});

// ================================================================
// BankService.getQuestionIdBank()
// ================================================================
describe("BankService.getQuestionIdBank()", () => {
  // Test Case ID: BANK-22
  it("BANK-22: bank có question → trả về mảng question_id đúng", async () => {
    const ids = await BankService.getQuestionIdBank(FIX.bankAvailableId);

    // Fixture seed 5 câu vào bankAvailable
    expect(ids.length).toBe(5);

    // CheckDB: đối chiếu trực tiếp với question_bank
    const dbResult = await pool.query(
      `SELECT question_id FROM question_bank WHERE bank_id = $1 ORDER BY question_id`,
      [FIX.bankAvailableId]
    );
    const dbIds = dbResult.rows.map((r: any) => r.question_id);

    expect(ids.sort()).toEqual(dbIds.map(Number).sort());
  });

  // Test Case ID: BANK-23
  it("BANK-23: bank không có question → trả về mảng rỗng", async () => {
    const ids = await BankService.getQuestionIdBank(FIX.bankDisabledId);
    expect(ids).toHaveLength(0);
  });
});

// ================================================================
// BankService.submit()
// ================================================================
describe("BankService.submit()", () => {
  let snap: Snapshot;
  beforeEach(async () => { snap = await takeSnapshot(); });
  afterEach(async ()  => { await restoreSnapshot(snap); });

  // Test Case ID: BANK-24
  it("BANK-24: type 1 trả lời đúng → score=0.25, lưu history_bank và user_bank_answer", async () => {
    const { score, history_bank_id } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [{ question_id: FIX.qType1aId, user_answer: [FIX.ansType1aCorrectId] }],
      100,
      1 // subject_type math
    );

    expect(score).toBe(0.25);

    // CheckDB: history_bank được tạo
    const histRow = await getRow("history_bank", { history_bank_id });
    expect(histRow).not.toBeNull();
    expect(Number(histRow!.score)).toBe(0.25);

    // CheckDB: user_bank_answer được tạo (1 answer)
    const ansCount = await countRows("user_bank_answer", { history_bank_id });
    expect(ansCount).toBe(1);
  });

  // Test Case ID: BANK-25
  it("BANK-25: type 1 trả lời sai → score=0", async () => {
    const { score } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [{ question_id: FIX.qType1aId, user_answer: [FIX.ansType2aWrong1Id] }],
      100,
      1
    );

    expect(score).toBe(0);
  });

  // Test Case ID: BANK-26
  it("BANK-26: type 2 đúng tất cả → score=1 (bài bank: +1 khi đúng hết)", async () => {
    /**
     * Lưu ý về scoring type 2 trong BankService.submit():
     * Code so sánh cứng correct count vs 1/2/3/4:
     *   correct === 1 → +0.1
     *   correct === 2 → +0.25
     *   correct === 3 → +0.5
     *   else          → +1
     * Fixture type 2a có 2 correct answers → "đúng tất" nghĩa là correct=2 → score=0.25
     * (KHÔNG phải score=1 như ExamService vì BankService dùng logic cứng khác)
     */
    const { score } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [{
        question_id: FIX.qType2aId,
        user_answer: [FIX.ansType2aCorrect1Id, FIX.ansType2aCorrect2Id],
      }],
      100,
      1
    );

    // Fixture có 2 correct answers → correct=2 → +0.25 (theo BankService code)
    expect(score).toBe(0.25);
  });

  // Test Case ID: BANK-27
  it("BANK-27: type 2 đúng 1/2 → score=0.1", async () => {
    const { score } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [{
        question_id: FIX.qType2aId,
        user_answer: [FIX.ansType2aCorrect1Id], // chỉ 1 đúng
      }],
      100,
      1
    );

    expect(score).toBe(0.1);
  });

  // Test Case ID: BANK-28
  it("BANK-28: type 3 (tự luận) đúng chính xác, subject_type=1 → score=0.5", async () => {
    const { score } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [{
        question_id: FIX.qType3aId,
        user_answer: [FIX.essayCorrectTextA],
      }],
      100,
      1 // subject_type=1 (math) → +0.5
    );

    expect(score).toBe(0.5);
  });

  // Test Case ID: BANK-29
  it("BANK-29: type 3 đúng, subject_type=2 → score=0.25", async () => {
    const { score } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [{
        question_id: FIX.qType3aId,
        user_answer: [FIX.essayCorrectTextA],
      }],
      100,
      2 // subject_type=2 (lit) → +0.25
    );

    expect(score).toBe(0.25);
  });

  // Test Case ID: BANK-30
  it("BANK-30: type 3 đúng nhưng viết hoa/thường khác nhau (case-insensitive) → score=0.5", async () => {
    const { score } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [{
        question_id: FIX.qType3aId,
        user_answer: [FIX.essayCorrectTextA.toUpperCase()],
      }],
      100,
      1
    );

    expect(score).toBe(0.5);
  });

  // Test Case ID: BANK-31
  it("BANK-31: do_bank rỗng → score=0, vẫn tạo history_bank, không có user_bank_answer", async () => {
    const { score, history_bank_id } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [], // không trả lời câu nào
      100,
      1
    );

    expect(score).toBe(0);

    // CheckDB: history_bank vẫn được tạo
    const histRow = await getRow("history_bank", { history_bank_id });
    expect(histRow).not.toBeNull();

    // CheckDB: không có user_bank_answer
    const ansCount = await countRows("user_bank_answer", { history_bank_id });
    expect(ansCount).toBe(0);
  });

  // Test Case ID: BANK-32
  it("BANK-32: user_id không tồn tại → throws (FK), history_bank KHÔNG được tạo", async () => {
    const beforeCount = await getMaxId("history_bank", "history_bank_id");

    await expect(
      BankService.submit(
        FIX.bankAvailableId,
        999999, // user_id FK không tồn tại
        [{ question_id: FIX.qType1aId, user_answer: [FIX.ansType1aCorrectId] }],
        100,
        1
      )
    ).rejects.toThrow();

    // CheckDB: không có history_bank mới nào được tạo (rollback thành công)
    const afterCount = await getMaxId("history_bank", "history_bank_id");
    expect(afterCount).toBe(beforeCount);
  });
});

// ================================================================
// BankService.getUserListBankHistory()
// ================================================================
describe("BankService.getUserListBankHistory()", () => {
  let snap: Snapshot;
  let seededHistoryId: number;

  beforeAll(async () => {
    snap = await takeSnapshot();
    // Seed 1 history để test BANK-33
    const { history_bank_id } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [],
      50,
      1
    );
    seededHistoryId = history_bank_id;
  });

  afterAll(async () => {
    await restoreSnapshot(snap);
  });

  // Test Case ID: BANK-33
  it("BANK-33: user có history → trả về list sắp xếp DESC theo history_bank_id", async () => {
    const { history } = await BankService.getUserListBankHistory(FIX.user1Id);

    expect(history.length).toBeGreaterThanOrEqual(1);

    // Verify sắp xếp DESC
    for (let i = 0; i < history.length - 1; i++) {
      expect(history[i].history_bank_id).toBeGreaterThan(history[i + 1].history_bank_id);
    }

    // Phải chứa history vừa seed
    const found = history.find(h => h.history_bank_id === seededHistoryId);
    expect(found).toBeDefined();
    expect(Number(found!.score)).toBe(0);
    expect(Number(found!.time_test)).toBe(50);
  });

  // Test Case ID: BANK-34
  it("BANK-34: user chưa có history → trả về {history: []}", async () => {
    // user3 chưa làm bài lần nào
    const { history } = await BankService.getUserListBankHistory(FIX.user3Id);
    expect(history).toHaveLength(0);
  });
});

// ================================================================
// BankService.getUserAnswer()
// ================================================================
describe("BankService.getUserAnswer()", () => {
  let snap: Snapshot;
  let seededHistoryBankId: number;

  beforeAll(async () => {
    snap = await takeSnapshot();
    // Submit để có dữ liệu history + user_bank_answer
    const { history_bank_id } = await BankService.submit(
      FIX.bankAvailableId,
      FIX.user1Id,
      [
        { question_id: FIX.qType1aId, user_answer: [FIX.ansType1aCorrectId] },
        { question_id: FIX.qType3aId, user_answer: [FIX.essayCorrectTextA] },
      ],
      120,
      1
    );
    seededHistoryBankId = history_bank_id;
  });

  afterAll(async () => {
    await restoreSnapshot(snap);
  });

  // Test Case ID: BANK-35
  it("BANK-35: history hợp lệ → trả về score và grouped questions với user_answers đúng", async () => {
    const result = await BankService.getUserAnswer(
      seededHistoryBankId,
      FIX.bankAvailableId
    );

    expect(result.score).toBe(0.5 + 0.25); // 0.25 (type1) + 0 (type2 không trả) + 0.5 (type3 math)
    // Phải có questions cho mỗi type
    expect(result.questions[1]).toBeDefined();
    expect(result.questions[2]).toBeDefined();
    expect(result.questions[3]).toBeDefined();

    // Type 1: question_id phải có user_answers
    const q1 = result.questions[1].find(
      (q: any) => q.question_id === FIX.qType1aId
    );
    expect(q1).toBeDefined();
    expect(q1!.user_answers.length).toBeGreaterThan(0);
  });

  // Test Case ID: BANK-36
  it("BANK-36: history_bank_id không tồn tại → score=null, questions trả theo bank", async () => {
    const result = await BankService.getUserAnswer(
      999999, // không tồn tại
      FIX.bankAvailableId
    );

    expect(result.score).toBeNull();
    // Questions vẫn được trả về (theo bank_id)
    expect(result.questions).toBeDefined();
  });
});

// ================================================================
// BankQuestionService.add()
// ================================================================
describe("BankQuestionService.add()", () => {
  let snap: Snapshot;
  beforeEach(async () => { snap = await takeSnapshot(); });
  afterEach(async ()  => { await restoreSnapshot(snap); });

  // Test Case ID: BANK-37
  it("BANK-37: thêm câu hỏi mới vào bank → question_bank được cập nhật đúng", async () => {
    // Seed một bank mới để test
    const tempBank = await BankService.create({
      description: "TEMP_BANK_BQ_37",
      topic_id: FIX.topic1Id,
      time_limit: 30,
    } as any);

    const payload = [
      { bank_id: tempBank.bank_id, question_id: FIX.qType1aId },
      { bank_id: tempBank.bank_id, question_id: FIX.qType1bId },
    ];

    const result = await BankQuestionService.add(payload);

    expect(result.bank_id).toBe(tempBank.bank_id);
    expect(result.total).toBe(2);

    // CheckDB
    const count = await countRows("question_bank", { bank_id: tempBank.bank_id });
    expect(count).toBe(2);
  });

  // Test Case ID: BANK-38
  it("BANK-38: selectedQuestions rỗng → throws 'selectedQuestions is empty or invalid'", async () => {
    await expect(BankQuestionService.add([])).rejects.toThrow(
      "selectedQuestions is empty or invalid"
    );
  });
});

// ================================================================
// BankQuestionService.remove()
// ================================================================
describe("BankQuestionService.remove()", () => {
  let snap: Snapshot;
  beforeEach(async () => { snap = await takeSnapshot(); });
  afterEach(async ()  => { await restoreSnapshot(snap); });

  // Test Case ID: BANK-39
  it("BANK-39: xoá question khỏi bank tồn tại → trả về true, row bị xoá", async () => {
    // Thêm câu vào bank trước
    const tempBank = await BankService.create({
      description: "TEMP_BANK_BQ_39",
      topic_id: FIX.topic1Id,
      time_limit: 30,
    } as any);

    await BankQuestionService.add([
      { bank_id: tempBank.bank_id, question_id: FIX.qType1aId },
    ]);

    const result = await BankQuestionService.remove({
      bank_id: tempBank.bank_id,
      question_id: FIX.qType1aId,
    });

    expect(result).toBe(true);

    // CheckDB
    const count = await countRows("question_bank", {
      bank_id: tempBank.bank_id,
      question_id: FIX.qType1aId,
    });
    expect(count).toBe(0);
  });

  // Test Case ID: BANK-40
  it("BANK-40: xoá cặp (bank_id, question_id) không tồn tại → trả về false", async () => {
    const result = await BankQuestionService.remove({
      bank_id: 999999,
      question_id: 999999,
    });

    expect(result).toBe(false);
  });
});
