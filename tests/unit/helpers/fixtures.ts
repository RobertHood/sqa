/**
 * tests/helpers/fixtures.ts
 *
 * Seed và teardown toàn bộ dữ liệu fixture dùng chung cho tất cả test suite.
 * Thứ tự tạo phải tôn trọng ràng buộc FK:
 *   subject → topic → user → exam_schedule → exam → bank → question → answer
 *   → question_bank → question_exam
 *
 * Thứ tự xoá ngược lại (child trước, parent sau).
 *
 * FIX object: chứa tất cả ID được sinh ra khi seed, truyền vào test để tham chiếu.
 */

import pool from "../../../backend/src/config/database";

// ---------------------------------------------------------------
// Kiểu dữ liệu của FIX object
// ---------------------------------------------------------------
export interface Fixtures {
  // Subjects
  subjectMathId: number;   // subject_type = 1 (Toán)
  subjectLitId: number;    // subject_type = 2 (Văn)

  // Topics
  topic1Id: number;        // thuộc subjectMath
  topic2Id: number;        // thuộc subjectLit

  // Users (đủ để submit history)
  user1Id: number;         // user thông thường
  user2Id: number;         // user thứ 2 (dùng ranking)
  user3Id: number;         // user thứ 3

  // Exam schedules
  scheduleActiveId: number;   // end_time = future
  scheduleExpiredId: number;  // end_time = past

  // Exams
  examActiveId: number;    // available=true, schedule active
  examExpiredId: number;   // available=true, schedule expired  (kiểm EXPIRED)
  examDisabledId: number;  // available=false                   (kiểm DISABLED)

  // Banks
  bankAvailableId: number; // available=true
  bankDisabledId: number;  // available=false

  // Questions (dùng chung cho cả bank và exam)
  qType1aId: number;       // single choice a
  qType1bId: number;       // single choice b
  qType2aId: number;       // multiple choice a
  qType2bId: number;       // multiple choice b
  qType3aId: number;       // essay a (subject_type=1 → +0.5)
  qType3bId: number;       // essay b (subject_type=2 → +0.25)

  // Correct answer IDs for type-1 questions
  ansType1aCorrectId: number;
  ansType1bCorrectId: number;
  // Correct answer IDs for type-2 questions (4 answers each, 2 correct)
  ansType2aCorrect1Id: number;
  ansType2aCorrect2Id: number;
  ansType2aWrong1Id: number;
  ansType2aWrong2Id: number;
  ansType2bCorrect1Id: number;
  ansType2bCorrect2Id: number;
  ansType2bWrong1Id: number;
  ansType2bWrong2Id: number;

  // Correct answer content for essay
  essayCorrectTextA: string;
  essayCorrectTextB: string;
}

// Module-level singleton được điền khi seedFixtures() chạy
export const FIX: Fixtures = {} as Fixtures;

// ---------------------------------------------------------------
// seedFixtures() — gọi trong beforeAll của từng test suite
// ---------------------------------------------------------------
export async function seedFixtures(): Promise<void> {
  const client = await pool.connect();

  try {
    // ----- SUBJECTS -----
    const subMath = await client.query(
      `INSERT INTO subject (subject_name, subject_type, available)
       VALUES ('TEST_Subject_Math', 1, true) RETURNING subject_id`
    );
    FIX.subjectMathId = subMath.rows[0].subject_id;

    const subLit = await client.query(
      `INSERT INTO subject (subject_name, subject_type, available)
       VALUES ('TEST_Subject_Lit', 2, true) RETURNING subject_id`
    );
    FIX.subjectLitId = subLit.rows[0].subject_id;

    // ----- TOPICS -----
    const t1 = await client.query(
      `INSERT INTO topic (title, subject_id, description)
       VALUES ('TEST_Topic_Toan', $1, 'topic test math') RETURNING topic_id`,
      [FIX.subjectMathId]
    );
    FIX.topic1Id = t1.rows[0].topic_id;

    const t2 = await client.query(
      `INSERT INTO topic (title, subject_id, description)
       VALUES ('TEST_Topic_Van', $1, 'topic test lit') RETURNING topic_id`,
      [FIX.subjectLitId]
    );
    FIX.topic2Id = t2.rows[0].topic_id;

    // ----- USERS -----
    const u1 = await client.query(
      `INSERT INTO "user" (user_name, email, password_hash)
       VALUES ('test_user1', 'test_u1@test.com', 'hashed') RETURNING user_id`
    );
    FIX.user1Id = u1.rows[0].user_id;

    const u2 = await client.query(
      `INSERT INTO "user" (user_name, email, password_hash)
       VALUES ('test_user2', 'test_u2@test.com', 'hashed') RETURNING user_id`
    );
    FIX.user2Id = u2.rows[0].user_id;

    const u3 = await client.query(
      `INSERT INTO "user" (user_name, email, password_hash)
       VALUES ('test_user3', 'test_u3@test.com', 'hashed') RETURNING user_id`
    );
    FIX.user3Id = u3.rows[0].user_id;

    // ----- EXAM SCHEDULES -----
    const schedActive = await client.query(
      `INSERT INTO exam_schedule (start_time, end_time)
       VALUES (NOW() - INTERVAL '1 hour', NOW() + INTERVAL '7 days') RETURNING exam_schedule_id`
    );
    FIX.scheduleActiveId = schedActive.rows[0].exam_schedule_id;

    const schedExpired = await client.query(
      `INSERT INTO exam_schedule (start_time, end_time)
       VALUES (NOW() - INTERVAL '10 days', NOW() - INTERVAL '1 day') RETURNING exam_schedule_id`
    );
    FIX.scheduleExpiredId = schedExpired.rows[0].exam_schedule_id;

    // ----- EXAMS -----
    const examA = await client.query(
      `INSERT INTO exam (exam_name, topic_id, time_limit, exam_schedule_id, available, description)
       VALUES ('TEST_Exam_Active', $1, 90, $2, true, 'active exam') RETURNING exam_id`,
      [FIX.topic1Id, FIX.scheduleActiveId]
    );
    FIX.examActiveId = examA.rows[0].exam_id;

    const examE = await client.query(
      `INSERT INTO exam (exam_name, topic_id, time_limit, exam_schedule_id, available, description)
       VALUES ('TEST_Exam_Expired', $1, 90, $2, true, 'expired exam') RETURNING exam_id`,
      [FIX.topic1Id, FIX.scheduleExpiredId]
    );
    FIX.examExpiredId = examE.rows[0].exam_id;

    const examD = await client.query(
      `INSERT INTO exam (exam_name, topic_id, time_limit, exam_schedule_id, available, description)
       VALUES ('TEST_Exam_Disabled', $1, 90, $2, false, 'disabled exam') RETURNING exam_id`,
      [FIX.topic1Id, FIX.scheduleActiveId]
    );
    FIX.examDisabledId = examD.rows[0].exam_id;

    // ----- BANKS -----
    const bankA = await client.query(
      `INSERT INTO bank (description, topic_id, time_limit, available)
       VALUES ('TEST_Bank_Available', $1, 60, true) RETURNING bank_id`,
      [FIX.topic1Id]
    );
    FIX.bankAvailableId = bankA.rows[0].bank_id;

    const bankD = await client.query(
      `INSERT INTO bank (description, topic_id, time_limit, available)
       VALUES ('TEST_Bank_Disabled', $1, 60, false) RETURNING bank_id`,
      [FIX.topic2Id]
    );
    FIX.bankDisabledId = bankD.rows[0].bank_id;

    // ----- QUESTIONS -----
    const q1a = await client.query(
      `INSERT INTO question (question_content, type_question, available)
       VALUES ('TEST_Q1A single choice', 1, true) RETURNING question_id`
    );
    FIX.qType1aId = q1a.rows[0].question_id;

    const q1b = await client.query(
      `INSERT INTO question (question_content, type_question, available)
       VALUES ('TEST_Q1B single choice', 1, true) RETURNING question_id`
    );
    FIX.qType1bId = q1b.rows[0].question_id;

    const q2a = await client.query(
      `INSERT INTO question (question_content, type_question, available)
       VALUES ('TEST_Q2A multiple choice', 2, true) RETURNING question_id`
    );
    FIX.qType2aId = q2a.rows[0].question_id;

    const q2b = await client.query(
      `INSERT INTO question (question_content, type_question, available)
       VALUES ('TEST_Q2B multiple choice', 2, true) RETURNING question_id`
    );
    FIX.qType2bId = q2b.rows[0].question_id;

    const q3a = await client.query(
      `INSERT INTO question (question_content, type_question, available)
       VALUES ('TEST_Q3A essay', 3, true) RETURNING question_id`
    );
    FIX.qType3aId = q3a.rows[0].question_id;

    const q3b = await client.query(
      `INSERT INTO question (question_content, type_question, available)
       VALUES ('TEST_Q3B essay', 3, true) RETURNING question_id`
    );
    FIX.qType3bId = q3b.rows[0].question_id;

    // ----- ANSWERS -----
    // Type 1a: 2 answers, 1 correct
    const a1aC = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Đáp án đúng Q1A', true) RETURNING answer_id`,
      [FIX.qType1aId]
    );
    FIX.ansType1aCorrectId = a1aC.rows[0].answer_id;
    await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Đáp án sai Q1A', false)`,
      [FIX.qType1aId]
    );

    // Type 1b: 2 answers, 1 correct
    const a1bC = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Đáp án đúng Q1B', true) RETURNING answer_id`,
      [FIX.qType1bId]
    );
    FIX.ansType1bCorrectId = a1bC.rows[0].answer_id;
    await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Đáp án sai Q1B', false)`,
      [FIX.qType1bId]
    );

    // Type 2a: 4 answers, 2 correct
    const a2aC1 = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Đúng 2A-1', true) RETURNING answer_id`,
      [FIX.qType2aId]
    );
    FIX.ansType2aCorrect1Id = a2aC1.rows[0].answer_id;

    const a2aC2 = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Đúng 2A-2', true) RETURNING answer_id`,
      [FIX.qType2aId]
    );
    FIX.ansType2aCorrect2Id = a2aC2.rows[0].answer_id;

    const a2aW1 = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Sai 2A-1', false) RETURNING answer_id`,
      [FIX.qType2aId]
    );
    FIX.ansType2aWrong1Id = a2aW1.rows[0].answer_id;

    const a2aW2 = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Sai 2A-2', false) RETURNING answer_id`,
      [FIX.qType2aId]
    );
    FIX.ansType2aWrong2Id = a2aW2.rows[0].answer_id;

    // Type 2b: 4 answers, 2 correct
    const a2bC1 = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Đúng 2B-1', true) RETURNING answer_id`,
      [FIX.qType2bId]
    );
    FIX.ansType2bCorrect1Id = a2bC1.rows[0].answer_id;

    const a2bC2 = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Đúng 2B-2', true) RETURNING answer_id`,
      [FIX.qType2bId]
    );
    FIX.ansType2bCorrect2Id = a2bC2.rows[0].answer_id;

    const a2bW1 = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Sai 2B-1', false) RETURNING answer_id`,
      [FIX.qType2bId]
    );
    FIX.ansType2bWrong1Id = a2bW1.rows[0].answer_id;

    const a2bW2 = await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, 'Sai 2B-2', false) RETURNING answer_id`,
      [FIX.qType2bId]
    );
    FIX.ansType2bWrong2Id = a2bW2.rows[0].answer_id;

    // Type 3 (essay): answer content = text đúng
    FIX.essayCorrectTextA = "Đáp án tự luận A";
    await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, $2, true)`,
      [FIX.qType3aId, FIX.essayCorrectTextA]
    );

    FIX.essayCorrectTextB = "Đáp án tự luận B";
    await client.query(
      `INSERT INTO answer (question_id, answer_content, is_correct)
       VALUES ($1, $2, true)`,
      [FIX.qType3bId, FIX.essayCorrectTextB]
    );

    // ----- QUESTION_BANK (link questions → bankAvailable) -----
    await client.query(
      `INSERT INTO question_bank (bank_id, question_id) VALUES
       ($1, $2), ($1, $3), ($1, $4), ($1, $5), ($1, $6)`,
      [
        FIX.bankAvailableId,
        FIX.qType1aId,
        FIX.qType2aId,
        FIX.qType3aId,
        FIX.qType1bId,
        FIX.qType2bId,
      ]
    );

    // ----- QUESTION_EXAM (link questions → examActive) -----
    await client.query(
      `INSERT INTO question_exam (exam_id, question_id) VALUES
       ($1, $2), ($1, $3), ($1, $4), ($1, $5), ($1, $6)`,
      [
        FIX.examActiveId,
        FIX.qType1aId,
        FIX.qType2aId,
        FIX.qType3aId,
        FIX.qType1bId,
        FIX.qType2bId,
      ]
    );

  } finally {
    client.release();
  }
}

// ---------------------------------------------------------------
// teardownFixtures() — gọi trong afterAll, xoá theo thứ tự FK ngược
// ---------------------------------------------------------------
export async function teardownFixtures(): Promise<void> {
  const client = await pool.connect();

  try {
    // Xoá theo thứ tự: child tables trước
    await client.query(
      `DELETE FROM user_bank_answer
       WHERE bank_id IN ($1, $2)`,
      [FIX.bankAvailableId, FIX.bankDisabledId]
    );

    await client.query(
      `DELETE FROM user_exam_answer
       WHERE exam_id IN ($1, $2, $3)`,
      [FIX.examActiveId, FIX.examExpiredId, FIX.examDisabledId]
    );

    await client.query(
      `DELETE FROM history_bank
       WHERE bank_id IN ($1, $2)`,
      [FIX.bankAvailableId, FIX.bankDisabledId]
    );

    await client.query(
      `DELETE FROM history_exam
       WHERE exam_id IN ($1, $2, $3)`,
      [FIX.examActiveId, FIX.examExpiredId, FIX.examDisabledId]
    );

    await client.query(
      `DELETE FROM question_bank
       WHERE bank_id IN ($1, $2)`,
      [FIX.bankAvailableId, FIX.bankDisabledId]
    );

    await client.query(
      `DELETE FROM question_exam
       WHERE exam_id IN ($1, $2, $3)`,
      [FIX.examActiveId, FIX.examExpiredId, FIX.examDisabledId]
    );

    // Xoá bank và exam
    await client.query(
      `DELETE FROM bank WHERE bank_id IN ($1, $2)`,
      [FIX.bankAvailableId, FIX.bankDisabledId]
    );

    await client.query(
      `DELETE FROM exam WHERE exam_id IN ($1, $2, $3)`,
      [FIX.examActiveId, FIX.examExpiredId, FIX.examDisabledId]
    );

    // Xoá answers → questions
    const questionIds = [
      FIX.qType1aId, FIX.qType1bId,
      FIX.qType2aId, FIX.qType2bId,
      FIX.qType3aId, FIX.qType3bId,
    ];
    await client.query(
      `DELETE FROM answer WHERE question_id = ANY($1::int[])`,
      [questionIds]
    );
    await client.query(
      `DELETE FROM question WHERE question_id = ANY($1::int[])`,
      [questionIds]
    );

    // Xoá exam_schedule
    await client.query(
      `DELETE FROM exam_schedule WHERE exam_schedule_id IN ($1, $2)`,
      [FIX.scheduleActiveId, FIX.scheduleExpiredId]
    );

    // Xoá users
    await client.query(
      `DELETE FROM "user" WHERE user_id IN ($1, $2, $3)`,
      [FIX.user1Id, FIX.user2Id, FIX.user3Id]
    );

    // Xoá topics → subjects
    await client.query(
      `DELETE FROM topic WHERE topic_id IN ($1, $2)`,
      [FIX.topic1Id, FIX.topic2Id]
    );

    await client.query(
      `DELETE FROM subject WHERE subject_id IN ($1, $2)`,
      [FIX.subjectMathId, FIX.subjectLitId]
    );

  } finally {
    client.release();
  }
}
