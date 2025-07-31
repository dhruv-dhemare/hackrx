const jwt = require('jsonwebtoken');
const SECRET_KEY = process.env.JWT_SECRET || 'your-secret-key';

const userAuthMiddleware = (req, res, next) => {
    const token = extractToken(req);
    if (!token) return res.status(401).json({ error: 'User token missing' });

    try {
        const decoded = jwt.verify(token, SECRET_KEY);
        req.user = decoded; 
        next();
    } catch (err) {
        return res.status(403).json({ error: 'Invalid user token' });
    }
};

// const adminAuthMiddleware = (req, res, next) => {
//     const token = extractToken(req);
//     if (!token) return res.status(401).json({ error: 'Admin token missing' });

//     try {
//         const decoded = jwt.verify(token, SECRET_KEY);
//         req.admin = decoded; 
//         next();
//     } catch (err) {
//         return res.status(403).json({ error: 'Invalid seller token' });
//     }
// };

const generateToken = (payload) => {
    return jwt.sign(payload, SECRET_KEY, { expiresIn: '2d' });
};

const extractToken = (req) => {
    const header = req.headers.authorization;
    return header && header.startsWith('Bearer ') ? header.split(' ')[1] : null;
};

module.exports = {
    userAuthMiddleware,
    generateToken
};