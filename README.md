# ANGRY MOD Key Server

Node.js + Express based key validation server — Render pe deploy karne ke liye ready.

## Features
- ✅ Key generation with expiry (daily / lifetime)
- ✅ HWID (device) locking — ek key ek hi device pe chalegi
- ✅ Admin routes (generate, revoke, reset HWID)
- ✅ CORS enabled (Android app se connect hoga)

## Render Pe Deploy Kaise Karo

1. Is folder ko GitHub pe push karo
2. Render.com → New Web Service → GitHub repo connect karo
3. Build command: `npm install`
4. Start command: `npm start`
5. Environment Variables add karo:
   - `ADMIN_SECRET` = `koi_bhi_secret_password`
6. Deploy!

## Admin API Usage (After Deploy)

### Naya Key Banao
```bash
curl -X POST https://your-app.onrender.com/admin/generate \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: YOUR_ADMIN_SECRET" \
  -d '{"user": "player1", "days": 30}'
```

### Saari Keys Dekho
```bash
curl https://your-app.onrender.com/admin/keys \
  -H "x-admin-secret: YOUR_ADMIN_SECRET"
```

### Key Revoke Karo
```bash
curl -X POST https://your-app.onrender.com/admin/revoke \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: YOUR_ADMIN_SECRET" \
  -d '{"key": "AM-XXXX-XXXX-XXXX"}'
```

### HWID Reset Karo
```bash
curl -X POST https://your-app.onrender.com/admin/reset-hwid \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: YOUR_ADMIN_SECRET" \
  -d '{"key": "AM-XXXX-XXXX-XXXX"}'
```
