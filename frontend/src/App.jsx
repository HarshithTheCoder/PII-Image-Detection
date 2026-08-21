import { useState } from "react";
import "./App.css";
const API_URL = "http://127.0.0.1:8000";
function App() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [detections, setDetections] = useState([]);
  const [faces, setFaces] = useState([]);
  const [selectedFields, setSelectedFields] = useState([]);
  const [redactedImage, setRedactedImage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("Upload a document to begin.");
  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (!selected) return;
    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setRedactedImage(null);
    setDetections([]);
    setFaces([]);
    setSelectedFields([]);
    setStatus("Document ready for detection.");
  };
  const detectPII = async () => {
    if (!file) {
      setStatus("Please upload a document first.");
      return;
    }
    setLoading(true);
    setStatus("Detecting PII...");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch(`${API_URL}/detect`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Detection failed");
      }
      setDetections(data.detections || []);
      setFaces(data.faces || []);
      const detectedFields = [
        ...(data.detections || []).map((d) => d.class_name),
        ...(data.faces?.length ? ["Face (photo)"] : []),
      ];
      setSelectedFields(detectedFields);
      setStatus(
        `Detection complete. ${detectedFields.length} sensitive region(s) found.`,
      );
    } catch (error) {
      setStatus(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };
  const toggleField = (field) => {
    setSelectedFields((current) =>
      current.includes(field)
        ? current.filter((item) => item !== field)
        : [...current, field],
    );
  };
  const applyRedaction = async () => {
    if (!file || selectedFields.length === 0) {
      setStatus("Select at least one field to redact.");
      return;
    }
    setLoading(true);
    setStatus("Applying redaction...");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("detections", JSON.stringify(detections));
    formData.append("faces", JSON.stringify(faces));
    formData.append("selected_fields", JSON.stringify(selectedFields));
    try {
      const response = await fetch(`${API_URL}/redact`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error("Redaction failed");
      }
      const blob = await response.blob();
      const imageURL = URL.createObjectURL(blob);
      setRedactedImage(imageURL);
      setStatus("Redaction completed successfully.");
    } catch (error) {
      setStatus(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };
  const downloadImage = () => {
    if (!redactedImage) return;
    const link = document.createElement("a");
    link.href = redactedImage;
    link.download = "redacted-document.jpg";
    link.click();
  };
  return (
    <div className="app">
      {" "}
      {/* Header */}{" "}
      <header className="header">
        {" "}
        <div className="brand">
          {" "}
          <div className="logo">🛡️</div>{" "}
          <div>
            {" "}
            <h1>PII Shield</h1> <p>Automated PII Detection & Redaction</p>{" "}
          </div>{" "}
        </div>{" "}
        <div className="status">
          {" "}
          <span></span> Local Processing{" "}
        </div>{" "}
      </header>{" "}
      {/* Main */}{" "}
      <main className="container">
        {" "}
        <section className="hero">
          {" "}
          <h2>Protect Sensitive Information</h2>{" "}
          <p>
            {" "}
            Upload an identification document and automatically detect sensitive
            personal information before securely redacting it.{" "}
          </p>{" "}
        </section>{" "}
        <div className="workspace">
          {" "}
          {/* Left Panel */}{" "}
          <div className="card">
            {" "}
            <div className="card-header">
              {" "}
              <h3>Document</h3> <span className="step"> STEP 1 </span>{" "}
            </div>{" "}
            <label className="upload-box">
              {" "}
              {preview ? (
                <img src={preview} className="preview" alt="Document preview" />
              ) : (
                <>
                  {" "}
                  <div className="upload-icon">↑</div>{" "}
                  <strong> Upload document </strong>{" "}
                  <small> PNG, JPG or JPEG </small>{" "}
                </>
              )}{" "}
              <input
                type="file"
                accept="image/png,image/jpeg"
                onChange={handleFileChange}
              />{" "}
            </label>{" "}
            <button
              className="primary-btn"
              onClick={detectPII}
              disabled={!file || loading}
            >
              {" "}
              {loading ? "Processing..." : "🔍 Detect PII"}{" "}
            </button>{" "}
          </div>{" "}
          {/* Detection Panel */}{" "}
          <div className="card">
            {" "}
            <div className="card-header">
              {" "}
              <h3>Detected Information</h3>{" "}
              <span className="step"> STEP 2 </span>{" "}
            </div>{" "}
            {detections.length === 0 && faces.length === 0 ? (
              <div className="empty">
                {" "}
                <div>🔎</div> <p> No detections yet </p>{" "}
                <small> Upload a document and click Detect PII </small>{" "}
              </div>
            ) : (
              <div className="detections">
                {" "}
                {detections.map((item, index) => (
                  <div
                    className="detection"
                    key={`${item.class_name}-${index}`}
                  >
                    {" "}
                    <label>
                      {" "}
                      <input
                        type="checkbox"
                        checked={selectedFields.includes(item.class_name)}
                        onChange={() => toggleField(item.class_name)}
                      />{" "}
                      <span> {item.class_name} </span>{" "}
                    </label>{" "}
                    {item.confidence !== undefined && (
                      <span className="confidence">
                        {" "}
                        {(item.confidence * 100).toFixed(1)}%{" "}
                      </span>
                    )}{" "}
                  </div>
                ))}{" "}
                {faces.length > 0 && (
                  <div className="detection">
                    {" "}
                    <label>
                      {" "}
                      <input
                        type="checkbox"
                        checked={selectedFields.includes("Face (photo)")}
                        onChange={() => toggleField("Face (photo)")}
                      />{" "}
                      <span> Face (photo) </span>{" "}
                    </label>{" "}
                    <span className="confidence">
                      {" "}
                      {faces.length} detected{" "}
                    </span>{" "}
                  </div>
                )}{" "}
              </div>
            )}{" "}
          </div>{" "}
          {/* Result */}{" "}
          <div className="card result-card">
            {" "}
            <div className="card-header">
              {" "}
              <h3>Redacted Output</h3>{" "}
              <span className="step"> STEP 3 </span>{" "}
            </div>{" "}
            <div className="result">
              {" "}
              {redactedImage ? (
                <img
                  src={redactedImage}
                  alt="Redacted document"
                  className="result-image"
                />
              ) : (
                <div className="empty">
                  {" "}
                  <div>🔐</div> <p> Redacted document will appear here </p>{" "}
                </div>
              )}{" "}
            </div>{" "}
            <button
              className="secondary-btn"
              onClick={applyRedaction}
              disabled={!file || selectedFields.length === 0 || loading}
            >
              {" "}
              🔒 Apply Redaction{" "}
            </button>{" "}
            {redactedImage && (
              <button className="download-btn" onClick={downloadImage}>
                {" "}
                ↓ Download Redacted Document{" "}
              </button>
            )}{" "}
          </div>{" "}
        </div>{" "}
        {/* Status */}{" "}
        <div className="status-card">
          {" "}
          <strong>Status</strong> <span> {status} </span>{" "}
        </div>{" "}
      </main>{" "}
      <footer> PII Shield • Privacy-first document protection </footer>{" "}
    </div>
  );
}
export default App;
