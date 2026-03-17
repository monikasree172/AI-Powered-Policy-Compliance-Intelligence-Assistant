const express = require("express");
const cors = require("cors");
const axios = require("axios");
require("dotenv").config();

const app = express();
const PORT = process.env.PORT || 3001;
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

app.use(cors());
app.use(express.json());

// Health check
app.get("/api/health", async (req, res) => {
  try {
    const { data } = await axios.get(`${BACKEND_URL}/api/v1/health`, { timeout: 4000 });
    res.json(data);
  } catch {
    res.status(503).json({ status: "offline", documents_indexed: 0 });
  }
});

// Compliance query
app.post("/api/query", async (req, res) => {
  try {
    const { data } = await axios.post(`${BACKEND_URL}/api/v1/query`, req.body, { timeout: 120000 });
    res.json(data);
  } catch (err) {
    const status = err.response?.status || 500;
    const detail = err.response?.data?.detail || err.message || "Query failed";
    res.status(status).json({ error: detail });
  }
});

// Analytics
app.get("/api/analytics", async (req, res) => {
  try {
    const { data } = await axios.get(`${BACKEND_URL}/api/v1/analytics`);
    res.json(data);
  } catch {
    res.status(503).json({ error: "Analytics unavailable" });
  }
});

// Document stats
app.get("/api/documents/stats", async (req, res) => {
  try {
    const { data } = await axios.get(`${BACKEND_URL}/api/v1/documents/stats`);
    res.json(data);
  } catch {
    res.status(503).json({ error: "Stats unavailable" });
  }
});

app.listen(PORT, () => {
  console.log(`Express server running at http://localhost:${PORT}`);
  console.log(`Proxying requests to FastAPI at ${BACKEND_URL}`);
});
