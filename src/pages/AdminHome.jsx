import React, { useEffect, useState } from "react";
import Header from "../components/AdminHeader";
import UploadNew from "../components/UploadNew";
import DocumentCard from "../components/DocumentCard";
import { getAllDocuments, deleteDocument } from "../api";

const AdminHome = () => {
  const [documents, setDocuments] = useState([]);

  // Fetch all docs
  const fetchDocuments = async () => {
    try {
      const res = await getAllDocuments();
      setDocuments(res.data.documents);
    } catch (err) {
      console.error("Error fetching documents:", err);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  // When upload succeeds, refresh list
  const handleUploadSuccess = () => {
    fetchDocuments();
  };

  // Delete handler
  const handleDelete = async (docName) => {
    try {
      await deleteDocument(docName);
      fetchDocuments(); // refresh after delete
    } catch (err) {
      console.error("Error deleting document:", err);
    }
  };

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Header />
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "2rem",
          backgroundColor: "#f8f9fb",
        }}
      >
        <h2 style={{ color: "#007edb" }}>Uploaded Documents</h2>

        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "flex-start",
            gap: "20px",
            marginTop: "1rem",
            flexWrap: "wrap",
          }}
        >
          {/* Upload Button */}
          <UploadNew onUpload={handleUploadSuccess} />

          {/* Document Cards */}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            {documents.length > 0 ? (
              documents.map((doc, index) => (
                <DocumentCard key={index} doc={doc} onDelete={handleDelete} />
              ))
            ) : (
              <p>No documents uploaded yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminHome;
