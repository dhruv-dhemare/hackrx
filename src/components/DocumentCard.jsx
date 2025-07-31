import React from "react";
import { Trash2, FileText } from "lucide-react";
import "./DocumentCard.css";

const DocumentCard = ({ doc, onDelete }) => {
  const handleCardClick = () => {
    window.open(doc.url, "_blank");
  };

  const handleDeleteClick = (e) => {
    e.stopPropagation(); // prevent opening PDF on delete
    onDelete(doc.name);
  };

  return (
    <div className="document-card" onClick={handleCardClick}>
      <div className="pdf-icon">
        <FileText size={40} color="#e74c3c" />
      </div>
      <span className="doc-name">{doc.name}</span>
      <button className="document-delete" onClick={handleDeleteClick}>
        <Trash2 size={18} />
      </button>
    </div>
  );
};

export default DocumentCard;
