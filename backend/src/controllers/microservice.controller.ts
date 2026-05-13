import { Request, Response } from "express";
import safeExecute, { DefaultResponse } from "../utils/safe.execute";
import axios from "axios";
import path from "path";
import fs from "fs";
import FormData from "form-data";
import AdmZip from "adm-zip";


const PYTHON_LLM_URL = process.env.PYTHON_LLM_URL || "http://localhost:8000/llm/ask";
const VECTORIZE_URL = process.env.VECTORIZE_URL || "http://localhost:8000/llm/vectorize";
const DOCX_PROCESS_URL = process.env.DOCX_PROCESS_URL || "http://localhost:8000/bert/process-docx";

const MicroserviceController = {
  async askLLM(req: Request, res: Response) {
    const response: DefaultResponse<any> = await safeExecute(async () => {
      const { question } = req.body;

      if (!question || typeof question !== "string") {
        return {
          status: 400,
          message: "question is required",
          data: null,
        };
      }

      try {
        const llmRes = await axios.post(PYTHON_LLM_URL, { question }, { timeout: 15000 });
        return {
          status: 200,
          message: "LLM answer",
          data: llmRes.data, // { question, answer, sources }
        };
      } catch (err: any) {
        const statusCode = err?.response?.status ?? 503;
        const errorMessage =
          err?.response?.data?.detail ??
          err?.response?.data?.message ??
          err?.message ??
          "AI microservice is unavailable";

        return {
          status: statusCode,
          message: "AI microservice error",
          data: {
            error: errorMessage,
          },
        };
      }
    });

    res.status(response.status).json(response);
  },

  async vectorize(req: Request, res: Response) {
    const response = await safeExecute(async () => {
      const files = req.body.files;

      /**
       * files = [
       *   { document_id: number, link: string }
       * ]
       */

      if (!Array.isArray(files) || files.length === 0) {
        return {
          status: 400,
          message: "files must be a non-empty array",
          data: null,
        };
      }

      const BASE_DIR = path.resolve(__dirname, "../../");

      // ✅ chuẩn hoá + validate
      const payload = files.map((f: any) => {
        if (!f.document_id || !f.link) {
          throw new Error("Each file must have document_id and link");
        }

        const absPath = path.join(BASE_DIR, f.link);

        if (!fs.existsSync(absPath)) {
          throw new Error(`File not found: ${f.link}`);
        }

        return {
          document_id: f.document_id,
          // Chỉ trả về đường dẫn **tương đối** hoặc gốc
          link: f.link.replace(/\\/g, "/"),
        };
      });

      console.log("Vectorizing files:", payload);

      // 👉 gửi sang Python microservice
      await axios.post(
        VECTORIZE_URL,
        { files: payload },
        {
          headers: { "Content-Type": "application/json" },
        }
      );

      return {
        status: 200,
        message: "Vectorize started",
        data: {
          total_files: payload.length,
          files: payload,
        },
      };
    });

    res.status(response.status).json(response);
  },










  // ===== DOCX =====
  async process_docx(req: Request, res: Response) {
    let tmpZipPath: string | null = null;

    const cleanupFiles = () => {
      try {
        if (tmpZipPath && fs.existsSync(tmpZipPath)) fs.unlinkSync(tmpZipPath);
        if (req.file && fs.existsSync(req.file.path)) fs.unlinkSync(req.file.path);
      } catch (e) {
        console.warn("[CLEANUP] Failed to remove temp files:", e);
      }
    };

    try {
      if (!req.file) {
        return res.status(400).json({ status: 400, error: "NO_DOCX_FILE" });
      }

      // =====================
      // 1. Gửi file sang Python
      // =====================
      const form = new FormData();
      form.append("file", fs.createReadStream(req.file.path), {
        filename: req.file.originalname,
        contentType: req.file.mimetype,
      });

      let pyRes;
      try {
        pyRes = await axios.post(DOCX_PROCESS_URL, form, {
          headers: form.getHeaders(),
          responseType: "arraybuffer", // ZIP
          maxBodyLength: Infinity,
          timeout: 6000000, // tăng timeout nếu file lớn
        });
      } catch (err: any) {
        console.error("[PYTHON] DOCX processing failed:", err?.message || err);
        cleanupFiles();
        return res.status(500).json({ status: 500, error: "PYTHON_PROCESS_FAILED" });
      }

      // =====================
      // 2. Lưu zip tạm
      // =====================
      tmpZipPath = req.file.path.replace(/\.docx$/i, "_result.zip");
      fs.writeFileSync(tmpZipPath, pyRes.data);

      // =====================
      // 3. Chuẩn bị output dirs
      // =====================
      const BASE_OUTPUT = path.resolve(__dirname, "../../data/outputs");
      const MEDIA_DIR = path.join(BASE_OUTPUT, "media");

      fs.mkdirSync(BASE_OUTPUT, { recursive: true });
      fs.mkdirSync(MEDIA_DIR, { recursive: true });

      // =====================
      // 4. Unzip + phân loại
      // =====================
      try {
        const zip = new AdmZip(tmpZipPath);
        const entries = zip.getEntries();

        for (const entry of entries) {
          if (entry.isDirectory) continue;

          // 📄 JSON
          if (entry.entryName.endsWith(".json")) {
            const jsonPath = path.join(BASE_OUTPUT, entry.entryName);
            fs.writeFileSync(jsonPath, entry.getData());
          }

          // 🖼️ IMAGE
          if (entry.entryName.startsWith("media/")) {
            const imageName = path.basename(entry.entryName);
            const imagePath = path.join(MEDIA_DIR, imageName);
            fs.writeFileSync(imagePath, entry.getData());
          }
        }
      } catch (zipErr) {
        console.error("[ZIP] Failed to extract zip:", zipErr);
        cleanupFiles();
        return res.status(500).json({ status: 500, error: "ZIP_EXTRACTION_FAILED" });
      }

      // =====================
      // 5. Cleanup file tạm
      // =====================
      cleanupFiles();

      return res.status(200).json({
        status: 200,
        message: "Xử lý DOCX thành công",
        data: {
          json_output: BASE_OUTPUT,
          media_output: MEDIA_DIR,
        },
      });

    } catch (err) {
      console.error("[PROCESS_DOCX] Unexpected error:", err);
      cleanupFiles();
      return res.status(500).json({ status: 500, error: "UNEXPECTED_ERROR", details: err });
    }
  },

};

export default MicroserviceController;
