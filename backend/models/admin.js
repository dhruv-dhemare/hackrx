const mongoose = require('mongoose');

// Define a subdocument schema for files
const documentSchema = new mongoose.Schema({
  name: String,
  data: Buffer,
  contentType: String,
  uploadedAt: {
    type: Date,
    default: Date.now
  }
});

// Extend your existing admin schema
const adminSchema = new mongoose.Schema({
  username: {
    type: String,
    required: true
  },
  password: {
    type: String,
    required: true
  },
  documents: [documentSchema]  // New field to store multiple documents
});

// userSchema.pre('save',async function(next){
//     const user = this;

//     //Hash the password only if it has been modified(or is new)
//     if (!user.isModified('password')) return next();

//     try{
//         //hash password generation
//         const salt = await bcrypt.genSalt(10);

//         //hash password
//         const hashedPassword = await bcrypt.hash(user.password,salt);

//         //override the plain password with the hashed one
//         user.password = hashedPassword;

//         next();
//     }catch(err){
//         next(err);
//     }
// })
// userSchema.methods.comparePassword = async function(candidatePassword){
//     try{
//         // use bcrypt to compare the provided password with the hashed password
//         const isMatch = await bcrypt.compare(candidatePassword, this.password);
//         return isMatch;
//     }catch(err){
//         throw err;
//     }
// }

//create person model
const admin = mongoose.model('admin',adminSchema);
module.exports = admin;