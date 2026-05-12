/**
 * tests/helpers/sandbox.ts
 *
 * Strategy B — Snapshot & Restore
 *
 * Dùng cho các service method dùng pool.connect() riêng (submit, BankQuestionService.add…)
 * → KHÔNG thể bọc trong transaction chung của test.
 *
 * Cách dùng:
 *   let snap: Snapshot;
 *   beforeEach(async () => { snap = await takeSnapshot(); });
 *   afterEach(async () => { await restoreSnapshot(snap); });
 *
 * Snapshot lưu MAX id của các bảng ghi.
 * Restore xoá mọi row được INSERT sau thời điểm snapshot (DELETE WHERE id > maxId).
 * Thứ tự xoá: child trước parent (tôn trọng FK).
 */

import pool from "../../../backend/src/config/database";
import { getMaxId } from "./checkdb";

// Danh sách bảng cần snapshot theo thứ tự xoá (child → parent)
const SNAPSHOT_TABLES: Array<{ table: string; idCol: string }> = [
  { table: "user_bank_answer",  idCol: "user_bank_answer_id" },
  { table: "user_exam_answer",  idCol: "user_exam_answer_id" },
  { table: "history_bank",      idCol: "history_bank_id" },
  { table: "history_exam",      idCol: "history_exam_id" },
  { table: "question_bank",     idCol: "question_id" },   // composite PK — dùng ctid thay thế bên dưới
  { table: "question_exam",     idCol: "question_id" },
  { table: "bank",              idCol: "bank_id" },
  { table: "exam",              idCol: "exam_id" },
  { table: "question",          idCol: "question_id" },
];

export type Snapshot = Record<string, number>;

/**
 * Lưu max id của mỗi bảng vào thời điểm hiện tại.
 */
export async function takeSnapshot(): Promise<Snapshot> {
  const snap: Snapshot = {};

  for (const { table, idCol } of SNAPSHOT_TABLES) {
    // question_bank và question_exam là composite PK, không có id riêng
    // → dùng MAX(question_id) làm mốc (đủ dùng vì question_id monotone)
    snap[table] = await getMaxId(table, idCol);
  }

  return snap;
}

/**
 * Xoá tất cả row có id > giá trị tại thời điểm snapshot.
 * Thứ tự đảm bảo không vi phạm FK constraint.
 */
export async function restoreSnapshot(snap: Snapshot): Promise<void> {
  const client = await pool.connect();
  try {
    // user_bank_answer
    await client.query(
      `DELETE FROM user_bank_answer WHERE user_bank_answer_id > $1`,
      [snap["user_bank_answer"]]
    );
    // user_exam_answer
    await client.query(
      `DELETE FROM user_exam_answer WHERE user_exam_answer_id > $1`,
      [snap["user_exam_answer"]]
    );
    // history_bank
    await client.query(
      `DELETE FROM history_bank WHERE history_bank_id > $1`,
      [snap["history_bank"]]
    );
    // history_exam
    await client.query(
      `DELETE FROM history_exam WHERE history_exam_id > $1`,
      [snap["history_exam"]]
    );
    // question_bank: không có id tự tăng → xoá theo question_id > snapshot
    await client.query(
      `DELETE FROM question_bank WHERE question_id > $1`,
      [snap["question_bank"]]
    );
    // question_exam
    await client.query(
      `DELETE FROM question_exam WHERE question_id > $1`,
      [snap["question_exam"]]
    );
    // bank
    await client.query(
      `DELETE FROM bank WHERE bank_id > $1`,
      [snap["bank"]]
    );
    // exam
    await client.query(
      `DELETE FROM exam WHERE exam_id > $1`,
      [snap["exam"]]
    );
    // question
    await client.query(
      `DELETE FROM question WHERE question_id > $1`,
      [snap["question"]]
    );
  } finally {
    client.release();
  }
}
