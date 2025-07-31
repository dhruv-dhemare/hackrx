const express = require('express');
const app = express();
const db = require('./db');

const cors = require("cors");

app.use(cors({
    origin: 'http://localhost:5173', // Replace with your React port (default for Vite)
    credentials: true
}));

const PORT = 3000;
const bodyParser = require('body-parser');
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

const userRoutes = require('./routes/userRoutes')
app.use('/user', userRoutes);

const adminRoutes = require('./routes/adminRoutes')
app.use('/admin', adminRoutes);

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});