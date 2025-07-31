const mongoose = require("mongoose");

const mongoURL = process.env.MONGO_URL;

if (!mongoURL) {
  console.error("❌ MongoDB URL is missing! Check your .env file.");
  process.exit(1);
}

mongoose
  .connect(mongoURL, {
    useNewUrlParser: true,
    useUnifiedTopology: true,
  })
  .then(() => {
    console.log("✅ Connected to MongoDB server");
  })
  .catch((err) => {
    console.error("❌ Initial MongoDB connection error:", err);
  });

const db = mongoose.connection;

db.on("error", (err) => {
  console.error("MongoDB runtime error:", err);
});

db.on("disconnected", () => {
  console.log("⚠️ MongoDB disconnected");
});

process.on("SIGINT", async () => {
  await mongoose.connection.close();
  console.log("MongoDB disconnected on app termination");
  process.exit(0);
});

module.exports = db;
