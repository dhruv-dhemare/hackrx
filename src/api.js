import axios from 'axios';

const BASE_URL = 'http://localhost:3000/admin'; // Change port/domain if needed

// Upload a document
export const uploadDocument = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  return axios.post(`${BASE_URL}/upload-doc`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    }
  });
};

// Delete a document
export const deleteDocument = async (username, docName, token) => {
  return axios.delete(`${BASE_URL}/delete-doc`, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    data: { username, docName },
  });
};

// Get all documents
export const getAllDocuments = async () => {
  return axios.get(`${BASE_URL}/get-docs`);
};
