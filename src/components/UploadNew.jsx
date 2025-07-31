import React, { useState } from 'react';
import './UploadNew.css';
import { uploadDocument } from '../api'; // adjust the path as needed

const UploadNew = ({ onUpload }) => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const selected = e.target.files[0];
    if (selected && selected.type === 'application/pdf') {
      setFile(selected);
    } else {
      alert('Only PDF files are allowed');
      e.target.value = null;
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    try {
      setLoading(true);
      const response = await uploadDocument(file);

      alert('Upload successful');
      if (onUpload) onUpload(response.data);
      setFile(null);
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.error || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-container">
      <label htmlFor="file-upload" className="upload-box">
        {file ? (
          <span className="file-name">{file.name}</span>
        ) : (
          <span className="plus-icon">+</span>
        )}
        <input
          id="file-upload"
          type="file"
          accept="application/pdf"
          onChange={handleChange}
          className="hidden-input"
        />
      </label>

      {file && (
        <button onClick={handleUpload} className="upload-btn" disabled={loading}>
          {loading ? 'Uploading...' : 'Upload'}
        </button>
      )}
    </div>
  );
};

export default UploadNew;
