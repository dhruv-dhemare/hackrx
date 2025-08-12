import axios from 'axios';

const BASE_URL = 'http://localhost:3000/admin'; // adjust if needed

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

// Delete a document (by name only, backend uses env ADMIN_USERNAME)
export const deleteDocument = async (docName) => {
  return axios.delete(`${BASE_URL}/delete-doc/${encodeURIComponent(docName)}`);
};

// Get all documents
export const getAllDocuments = async () => {
  return axios.get(`${BASE_URL}/get-docs`);
};
