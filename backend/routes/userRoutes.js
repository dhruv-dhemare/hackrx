const express = require ('express');
const router = express.Router();
const user = require('../models/user.js');
const {userAuthMiddleware, generateToken} = require('./../jwt.js');

// Signup Route
router.post('/signup', async (req, res) => {
  try {
    const newUser = new user(req.body); // Assuming req.body contains { username, password, name, age }
    
    const exists = await user.findOne({ username: newUser.username });
    if (exists) {
      return res.status(409).json({ message: "Username already exists" });
    }

    const response = await newUser.save();

    // Generate token
    const payload = { id: response._id };
    const token = generateToken(payload);

    console.log('User data saved');
    console.log("Token is:", token);

    res.status(200).json({ response, token });

  } catch (err) {

    console.log(err);
    res.status(500).json({ error: 'Internal Server Error' });
  }
});


//login
router.post('/login', async (req,res) => {
    try{
        const {username,password} = req.body;
        const user_ = await user.findOne({ username : username});

        if(!user_){
            console.log("Invalid username");
            res.status(401).json({ error: 'Invalid username' });
        }
        const pass = user_.password;
        if(pass!=password){
            console.log("Invalid password");
            res.status(401).json({ error: 'Incorrect Password' });
        }
        console.log("User found");

        const payload = {id: user_._id};
        const token = generateToken(payload);
        console.log("Token is: ",token);

        res.status(200).json({response: user_, token: token});

    }catch(err){
        console.log(err);
        res.status(500).json({ error: 'Internal Server Error' });
    }
})

module.exports = router;