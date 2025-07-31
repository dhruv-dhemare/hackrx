const express = require('express');
const cors = require("cors");
const bodyParser = require('body-parser');

// 👉 Load environment variables BEFORE requiring db.js
require("dotenv").config();

const app = express();
const db = require('./db'); // now MONGO_URL will be available

app.use(cors({
    origin: 'http://localhost:5173', // Replace with your React port (default for Vite)
    credentials: true
}));

const PORT = process.env.PORT || 3000;

app.use(bodyParser.json());

// Root route
app.get('/', (req, res) => {
  try {
    console.log('🌟 REAL BACKEND REACHED');
    return res.send('WELCOME TO BAJAJ FINANCE ✅');
  } catch (error) {
    console.log('Invalid server', error);
    return res.status(500).send({ error: 'Server error occurred' });
  }
});

// Routes
const userRoutes = require('./routes/userRoutes');
app.use('/user', userRoutes);

const adminRoutes = require('./routes/adminRoutes');
app.use('/admin', adminRoutes);

app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
});
