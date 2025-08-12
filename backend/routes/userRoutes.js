const express = require("express");
const router = express.Router();
const Query = require("../models/query.js");
const { spawn } = require("child_process");
const path = require("path");

// ⚡ Hardcode one user ID (create this user in MongoDB and copy its _id here)
const DEFAULT_USER_ID = "688b6945f2f69d99447d758d";

// Get absolute path of Python script
const scriptPath = path.join(__dirname, "..", "..", "chatbot_doc_6.py");

// ---------------- QUERY ----------------
router.post("/query", async (req, res) => {
  try {
    const { query } = req.body;
    if (!query) {
      return res.status(400).json({ error: "Query is required" });
    }

    console.log("📥 Query received:", query);

    // Run Python script with query
    const python = spawn("python", [scriptPath, query]);

    let dataBuffer = "";
    python.stdout.on("data", (data) => {
      dataBuffer += data.toString();
    });

    python.stderr.on("data", (data) => {
      console.error(`🐍 Python Error: ${data}`);
    });

    python.on("close", async () => {
      console.log("🐍 Raw Python Output:", dataBuffer); // ✅ Debugging

      try {
        const answer = JSON.parse(dataBuffer);

        // Save to DB under default user
        const q = new Query({
          userId: DEFAULT_USER_ID,
          query,
          answer,
        });
        await q.save();

        res.json({ query, answer });
      } catch (err) {
        console.error("❌ Parse Error:", err);
        res.status(500).json({ error: "Failed to process chatbot response" });
      }
    });
  } catch (err) {
    console.error("❌ Query Route Error:", err);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

// ---------------- HISTORY ----------------
router.get("/history", async (req, res) => {
  try {
    const history = await Query.find({ userId: DEFAULT_USER_ID }).sort({ timestamp: -1 });
    res.json(history);
  } catch (err) {
    console.error("❌ History Error:", err);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

module.exports = router;
