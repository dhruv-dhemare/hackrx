const express = require('express');
const router = express.Router();
const admin = require('../models/admin.js');
require('dotenv').config();

const { userAuthMiddleware, generateToken } = require('./../jwt.js');

// login
router.post('/login', async (req, res) => {
    try {
        const { username, password } = req.body;
        const admin_ = await admin.findOne({ username: username });

        if (!admin_) {
            console.log("Invalid username");
            return res.status(401).json({ error: 'Invalid username' });
        }

        const pass = admin_.password;
        if (pass !== password) {
            console.log("Invalid password");
            return res.status(401).json({ error: 'Incorrect Password' });
        }

        console.log("Admin found");

        const payload = { id: admin_._id };
        const token = generateToken(payload);
        console.log("Token is: ", token);

        res.status(200).json({ response: admin_, token: token });

    } catch (err) {
        console.log(err);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

// router.get('/list', async (req, res) => {
//     const admins = await admin.find({});
//     res.json(admins);
// });

const multer = require('multer');
const storage = multer.memoryStorage(); // store files in memory
const upload = multer({ storage: storage });

// Upload a single document for an admin
router.post('/upload-doc', upload.single('file'), async (req, res) => {
  try {
    const file = req.file;
    const adminUsername = process.env.ADMIN_USERNAME;

    if (!file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const admin_ = await admin.findOne({ username: adminUsername });

    if (!admin_) {
      return res.status(404).json({ error: 'Admin not found' });
    }

    // Add the uploaded file to the admin's documents array
    admin_.documents.push({
      name: file.originalname,
      data: file.buffer,
      contentType: file.mimetype,
    });

    await admin_.save();

    res.status(200).json({ message: 'Document uploaded successfully' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Internal Server Error' });
  }
});
// DELETE a document by name for a specific admin
router.delete('/delete-doc', async (req, res) => {
  try {
    const { username, docName } = req.body;

    const admin_ = await admin.findOne({ username });

    if (!admin_) {
      return res.status(404).json({ error: 'Admin not found' });
    }

    const initialLength = admin_.documents.length;

    // Filter out the document with the given name
    admin_.documents = admin_.documents.filter(doc => doc.name !== docName);

    if (admin_.documents.length === initialLength) {
      return res.status(404).json({ error: 'Document not found' });
    }

    await admin_.save();

    res.status(200).json({ message: 'Document deleted successfully' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Internal Server Error' });
  }
});

const path = require('path');
const fs = require('fs');

// Serve a document from MongoDB by filename
router.get('/document/:filename', async (req, res) => {
  try {
    const { filename } = req.params;
    const adminUsername = process.env.ADMIN_USERNAME;

    const admin_ = await admin.findOne({ username: adminUsername });

    if (!admin_) {
      return res.status(404).json({ error: 'Admin not found' });
    }

    const document = admin_.documents.find(doc => doc.name === filename);

    if (!document) {
      return res.status(404).json({ error: 'Document not found' });
    }

    res.set({
      'Content-Type': document.contentType,
      'Content-Disposition': `inline; filename="${document.name}"`,
    });

    res.send(document.data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Internal Server Error' });
  }
});



// Get all documents for the admin from env username
router.get('/get-docs', async (req, res) => {
  try {
    const adminUsername = process.env.ADMIN_USERNAME;

    const admin_ = await admin.findOne({ username: adminUsername });

    if (!admin_) {
      return res.status(404).json({ error: 'Admin not found' });
    }

    // Construct document URLs
    const documents = admin_.documents.map(doc => ({
      name: doc.name,
      url: `${req.protocol}://${req.get('host')}/admin/document/${encodeURIComponent(doc.name)}`
    }));

    res.status(200).json({ documents });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Internal Server Error' });
  }
});




module.exports = router;
