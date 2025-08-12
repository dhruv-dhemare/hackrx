const jwt = require('jsonwebtoken');
const SECRET_KEY = process.env.JWT_SECRET || 'your-secret-key';

// ---------------- USER AUTH ----------------
const userAuthMiddleware = (req, res, next) => {
    const token = extractToken(req);
    if (!token) {
        return res.status(401).json({ error: 'User token missing' });
    }

    try {
        const decoded = jwt.verify(token, SECRET_KEY);
        req.user = decoded;  // Attach decoded payload (e.g. { id: userId })
        next();
    } catch (err) {
        console.error("JWT Verify Error:", err.message);
        return res.status(403).json({ error: 'Invalid or expired user token' });
    }
};

// ---------------- GENERATE TOKEN ----------------
const generateToken = (payload) => {
    return jwt.sign(payload, SECRET_KEY, { expiresIn: '2d' });
};

// ---------------- TOKEN EXTRACTOR ----------------
const extractToken = (req) => {
    const header = req.headers['authorization']; // lowercase to be safe
    if (!header) return null;

    if (header.startsWith('Bearer ')) {
        return header.split(' ')[1]; // return only the token
    }
    return null;
};

module.exports = {
    userAuthMiddleware,
    generateToken
};
