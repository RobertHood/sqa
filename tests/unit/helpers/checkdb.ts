/**
 * tests/helpers/checkdb.ts
 *
 * Các hàm tiện ích để verify trạng thái database sau khi service thực hiện
 * thay đổi (yêu cầu CheckDB).
 *
 * Không nên dùng trong service code — chỉ dành cho test.
 */

import pool from "../../../backend/src/config/database";

/**
 * Đếm số row trong bảng thoả mãn điều kiện WHERE.
 * Ví dụ: countRows('bank', { bank_id: 5 }) → số row
 *
 * @param table   - Tên bảng (không có dấu ngoặc kép)
 * @param where   - Object { column: value } (tất cả AND)
 */
export async function countRows(
  table: string,
  where: Record<string, any>
): Promise<number> {
  const keys = Object.keys(where);
  const values = Object.values(where);

  const conditions = keys
    .map((k, i) => `"${k}" = $${i + 1}`)
    .join(" AND ");

  const sql = `SELECT COUNT(*) AS cnt FROM "${table}" WHERE ${conditions}`;
  const result = await pool.query(sql, values);
  return Number(result.rows[0].cnt);
}

/**
 * Lấy 1 row đầu tiên từ bảng thoả mãn điều kiện WHERE.
 * Trả về null nếu không có row nào.
 *
 * @param table   - Tên bảng
 * @param where   - Điều kiện lọc
 */
export async function getRow(
  table: string,
  where: Record<string, any>
): Promise<Record<string, any> | null> {
  const keys = Object.keys(where);
  const values = Object.values(where);

  const conditions = keys
    .map((k, i) => `"${k}" = $${i + 1}`)
    .join(" AND ");

  const sql = `SELECT * FROM "${table}" WHERE ${conditions} LIMIT 1`;
  const result = await pool.query(sql, values);
  return result.rows[0] ?? null;
}

/**
 * Lấy giá trị MAX của cột id trong bảng.
 * Dùng trong Strategy B (snapshot) để biết điểm bắt đầu.
 *
 * @param table   - Tên bảng
 * @param idCol   - Tên cột PK (mặc định: '<table>_id')
 */
export async function getMaxId(
  table: string,
  idCol?: string
): Promise<number> {
  const col = idCol ?? `${table}_id`;
  const result = await pool.query(
    `SELECT COALESCE(MAX("${col}"), 0) AS max_id FROM "${table}"`
  );
  return Number(result.rows[0].max_id);
}
