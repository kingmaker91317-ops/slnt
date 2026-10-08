const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());
app.use(cors());

const PORT = process.env.PORT || 3000;

// Persistent JSON Storage Path
const KEYS_FILE = path.join(__dirname, 'keys.json');
const WALLET_FILE = path.join(__dirname, 'wallet.json');

// Helper to Load JSON File safely
function loadJSON(filePath, defaultData) {
  try {
    if (fs.existsSync(filePath)) {
      const data = fs.readFileSync(filePath, 'utf8');
      return JSON.parse(data);
    }
  } catch (e) {
    console.error(`Error reading ${filePath}:`, e.message);
  }
  return defaultData;
}

// Helper to Save JSON File safely
function saveJSON(filePath, data) {
  try {
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
  } catch (e) {
    console.error(`Error writing ${filePath}:`, e.message);
  }
}

// Load Initial Data from keys.json & wallet.json
let walletBalance = loadJSON(WALLET_FILE, { balance: 1000 }).balance;
let keys = loadJSON(KEYS_FILE, {});

const PRICING = {
  0.2: 10,   // 5 Hours Trial = ₹10
  1: 20,     // 1 Day = ₹20
  3: 50,     // 3 Days = ₹50
  7: 300,    // 7 Days = ₹300
  15: 550,   // 15 Days = ₹550
  30: 999    // 30 Days Monthly = ₹999
};

function generateKey() {
  const part = () => Math.random().toString(36).substring(2, 6).toUpperCase();
  return `AM-${part()}-${part()}-${part()}`;
}

function isExpired(key) {
  const k = keys[key];
  if (!k) return true;
  if (k.expiresAt === -1) return false;
  return Date.now() > k.expiresAt;
}

// Serve Web UI Panel
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Admin Auth Middleware
const ADMIN_SECRET = process.env.ADMIN_SECRET || 'angry-admin-secret-change-me';
function adminAuth(req, res, next) {
  const secret = req.headers['x-admin-secret'];
  if (secret !== ADMIN_SECRET) {
    return res.status(403).json({ status: 'error', message: 'Unauthorized' });
  }
  next();
}

// GET /admin/wallet — Get Wallet Balance
app.get('/admin/wallet', adminAuth, (req, res) => {
  res.json({ status: 'success', balance: walletBalance });
});

// POST /admin/wallet/add — Add Funds (Admin)
app.post('/admin/wallet/add', adminAuth, (req, res) => {
  const { amount } = req.body;
  if (!amount || amount <= 0) return res.status(400).json({ status: 'error', message: 'Invalid amount' });
  
  walletBalance += parseFloat(amount);
  saveJSON(WALLET_FILE, { balance: walletBalance });
  
  res.json({ status: 'success', balance: walletBalance });
});

// POST /admin/generate — Buy & Generate Key
app.post('/admin/generate', adminAuth, (req, res) => {
  const { user, days } = req.body;
  if (!user || days === undefined) return res.status(400).json({ status: 'error', message: 'User and days required' });

  // Calculate Price
  const price = PRICING[days] || (days * 20);

  // Check Wallet Balance
  if (walletBalance < price) {
    return res.status(400).json({ status: 'error', message: `Insufficient Wallet Balance! Required ₹${price}, Available ₹${walletBalance}` });
  }

  // Deduct Balance & Save Wallet
  walletBalance -= price;
  saveJSON(WALLET_FILE, { balance: walletBalance });

  const key = generateKey();
  const expiresAt = days === -1 ? -1 : Date.now() + (days || 1) * 24 * 60 * 60 * 1000;

  keys[key] = {
    user,
    days,
    price,
    expiresAt,
    active: true,
    hwid: null,
    createdAt: Date.now(),
  };

  saveJSON(KEYS_FILE, keys);

  res.json({
    status: 'success',
    key,
    user,
    days,
    priceDeducted: price,
    remainingBalance: walletBalance,
    expires: expiresAt === -1 ? 'Lifetime' : new Date(expiresAt).toISOString(),
  });
});

// GET /admin/keys — List all generated keys
app.get('/admin/keys', adminAuth, (req, res) => {
  const result = Object.entries(keys).map(([k, v]) => ({
    key: k,
    user: v.user,
    days: v.days,
    price: v.price,
    active: v.active,
    hwid: v.hwid || 'Not bound',
    expires: v.expiresAt === -1 ? 'Lifetime' : new Date(v.expiresAt).toISOString(),
    expired: isExpired(k),
  }));
  res.json({ status: 'success', total: result.length, keys: result });
});

// POST /admin/revoke — Revoke Key
app.post('/admin/revoke', adminAuth, (req, res) => {
  const { key } = req.body;
  if (!keys[key]) return res.status(404).json({ status: 'error', message: 'Key not found' });
  
  keys[key].active = false;
  saveJSON(KEYS_FILE, keys);
  
  res.json({ status: 'success', message: 'Key revoked' });
});

// POST /admin/reset-hwid — Reset Device HWID
app.post('/admin/reset-hwid', adminAuth, (req, res) => {
  const { key } = req.body;
  if (!keys[key]) return res.status(404).json({ status: 'error', message: 'Key not found' });
  
  keys[key].hwid = null;
  saveJSON(KEYS_FILE, keys);
  
  res.json({ status: 'success', message: 'HWID reset done' });
});

// POST /api/login — Public App Verification API (Proxy Mode)
app.post('/api/login', (req, res) => {
  const { key, hwid } = req.body;

  if (!key || !hwid) {
    return res.json({ status: 'error', message: 'Key and HWID required' });
  }

  const keyData = keys[key];
  if (!keyData) return res.json({ status: 'error', message: 'Invalid Key' });
  if (!keyData.active) return res.json({ status: 'error', message: 'Key Has Been Revoked' });
  if (isExpired(key)) return res.json({ status: 'error', message: 'Key Expired' });

  // Bind HWID on first login
  if (!keyData.hwid) {
    keyData.hwid = hwid;
    saveJSON(KEYS_FILE, keys);
  } else if (keyData.hwid !== hwid) {
    return res.json({ status: 'error', message: 'Key locked to another device' });
  }

  res.json({
    status: 'success',
    message: 'Login Successful',
    ogKey: '@SX2TEAM',
    user: keyData.user,
    expires: keyData.expiresAt === -1 ? 'Lifetime' : new Date(keyData.expiresAt).toISOString(),
  });
});

app.listen(PORT, () => {
  console.log(`\n🔑 ANGRY MOD Persistent Key Server running on port ${PORT}`);
});
