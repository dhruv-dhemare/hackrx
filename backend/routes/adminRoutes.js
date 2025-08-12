const express = require("express");
const router = express.Router();
const admin = require("../models/admin.js");
require("dotenv").config();

const { userAuthMiddleware, generateToken } = require("./../jwt.js");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");

// -------------------- LOGIN --------------------
router.post("/login", async (req, res) => {
  try {
    const { username, password } = req.body;
    const admin_ = await admin.findOne({ username: username });

    if (!admin_) {
      console.log("Invalid username");
      return res.status(401).json({ error: "Invalid username" });
    }

    const pass = admin_.password;
    if (pass !== password) {
      console.log("Invalid password");
      return res.status(401).json({ error: "Incorrect Password" });
    }

    console.log("Admin found");

    const payload = { id: admin_._id };
    const token = generateToken(payload);
    console.log("Token is: ", token);

    res.status(200).json({ response: admin_, token: token });
  } catch (err) {
    console.log(err);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

// -------------------- ENSURE UPLOADS FOLDER --------------------
const uploadsDir = path.join(__dirname, "../uploads");
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

// -------------------- MULTER STORAGE --------------------
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadsDir),
  filename: (req, file, cb) =>
    cb(null, Date.now() + "-" + file.originalname.replace(/\s+/g, "_")),
});
const upload = multer({ storage: storage });

// -------------------- UPLOAD DOCUMENT --------------------
router.post("/upload-doc", upload.single("file"), async (req, res) => {
  try {
    const file = req.file;
    const adminUsername = process.env.ADMIN_USERNAME;

    if (!file) {
      return res.status(400).json({ error: "No file uploaded" });
    }

    const admin_ = await admin.findOne({ username: adminUsername });
    if (!admin_) {
      return res.status(404).json({ error: "Admin not found" });
    }

    // Save metadata in MongoDB
    admin_.documents.push({
      name: file.originalname,
      path: file.path,
      contentType: file.mimetype,
    });

    // --- 🔥 Trigger Python pipeline safely ---
    const pythonScript = "D:/Projects/Chat_Bot_Rag/Final_ChatBot/chatbot_doc_5.py";
 // ✅ safe absolute path

    const pyProcess = spawn("python", [pythonScript, file.path]);

    pyProcess.stdout.on("data", (data) => {
      console.log(`📢 Python: ${data}`);
    });

    pyProcess.stderr.on("data", (data) => {
      console.error(`⚠️ Python error: ${data}`);
    });

    pyProcess.on("close", (code) => {
      if (code === 0) {
        res.status(200).json({
          message: "Document uploaded & indexed successfully",
        });
      } else {
        res.status(500).json({
          error: "Document saved, but indexing failed.",
        });
      }
    });
    
    await admin_.save();
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

// -------------------- DELETE DOCUMENT --------------------
router.delete("/delete-doc/:docName", async (req, res) => {
  try {
    const { docName } = req.params;
    const adminUsername = process.env.ADMIN_USERNAME;

    const admin_ = await admin.findOne({ username: adminUsername });
    if (!admin_) {
      return res.status(404).json({ error: "Admin not found" });
    }

    // Find the document
    const document = admin_.documents.find((doc) => doc.name === docName);
    if (!document) {
      return res.status(404).json({ error: "Document not found" });
    }

    // Remove from DB
    admin_.documents = admin_.documents.filter((doc) => doc.name !== docName);
    await admin_.save();

    // Remove file from disk (if path exists)
    if (document.path && fs.existsSync(document.path)) {
      fs.unlinkSync(document.path);
      console.log(`🗑️ Deleted file from disk: ${document.path}`);
    }

    res.status(200).json({ message: "Document deleted successfully" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

// -------------------- GET DOCUMENT (SERVE) --------------------
router.get("/document/:filename", async (req, res) => {
  try {
    const { filename } = req.params;
    const adminUsername = process.env.ADMIN_USERNAME;

    const admin_ = await admin.findOne({ username: adminUsername });
    if (!admin_) {
      return res.status(404).json({ error: "Admin not found" });
    }

    const document = admin_.documents.find(
      (doc) => doc.name === decodeURIComponent(filename)
    );
    if (!document) {
      return res.status(404).json({ error: "Document not found" });
    }

    res.set({
      "Content-Type": document.contentType,
      "Content-Disposition": `inline; filename="${document.name}"`,
    });

    if (document.path) {
      const filePath = path.isAbsolute(document.path)
        ? document.path
        : path.join(__dirname, "..", document.path);
      return res.sendFile(filePath);
    } else {
      return res.send(document.data); // fallback
    }
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

// -------------------- GET ALL DOCUMENTS --------------------
router.get("/get-docs", async (req, res) => {
  try {
    const adminUsername = process.env.ADMIN_USERNAME;
    const admin_ = await admin.findOne({ username: adminUsername });

    if (!admin_) {
      return res.status(404).json({ error: "Admin not found" });
    }

    const documents = admin_.documents.map((doc) => ({
      name: doc.name,
      url: `${req.protocol}://${req.get("host")}/admin/document/${encodeURIComponent(
        doc.name
      )}`,
    }));

    res.status(200).json({ documents });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

module.exports = router;
