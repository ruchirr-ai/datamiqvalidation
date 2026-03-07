# Quick Claude AI Setup Guide

## Problem
AWS Bedrock is showing this error:
```
Invocation of model ID with on-demand throughput isn't supported
```

This means the Claude model needs to be enabled in your AWS Bedrock console first.

## ✅ Solution: Use Direct Anthropic API (Recommended)

### Step 1: Get Your API Key (5 minutes)

1. **Go to Anthropic Console**
   - Visit: https://console.anthropic.com/
   
2. **Sign Up / Log In**
   - Use your email to create an account
   - Or log in if you already have one

3. **Get API Key**
   - Click "API Keys" in the left sidebar
   - Click "Create Key" button
   - Name it: "DataMIQ ChatAgent"
   - **Copy the key** (starts with `sk-ant-api03-...`)
   - ⚠️ Save it immediately - you won't see it again!

### Step 2: Add Key to .env File

1. **Open your `.env` file** (in the root of your project)

2. **Find this line**:
   ```env
   ANTHROPIC_API_KEY=sk-ant-api03-your-key-here-replace-this
   ```

3. **Replace with your actual key**:
   ```env
   ANTHROPIC_API_KEY=sk-ant-api03-AbCdEf1234567890...
   ```

4. **Save the file**

### Step 3: Restart Backend

The backend should auto-reload, but if not:

**Windows (PowerShell)**:
```powershell
# Stop the backend (Ctrl+C in the terminal)
# Then restart:
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 4: Test It!

1. **Refresh your browser** (http://localhost:3000)
2. **Open ChatAgent** (blue button, bottom-right)
3. **Ask**: "What are the risks of migrating from BigQuery to Redshift?"
4. **You should get a detailed, intelligent response from Claude!**

### Step 5: Verify It's Working

Check the backend terminal for:
```
✅ "Claude AI client (Anthropic API) initialized successfully"
```

If you see this, Claude is active!

---

## 🔄 Alternative: Fix AWS Bedrock (Advanced)

If you prefer to use AWS Bedrock:

### Enable Claude Model in AWS Console

1. **Go to AWS Bedrock Console**
   - https://console.aws.amazon.com/bedrock/

2. **Navigate to Model Access**
   - Click "Model access" in the left sidebar

3. **Request Access to Claude**
   - Find "Anthropic Claude 3.5 Sonnet"
   - Click "Request model access"
   - Fill out the form
   - Wait for approval (usually instant)

4. **Update .env**:
   ```env
   CLAUDE_USE_BEDROCK=true
   ANTHROPIC_API_KEY=  # Leave empty or comment out
   ```

5. **Restart backend**

---

## 🧪 Test Queries

Once Claude is working, try these:

1. **Migration Risk Analysis**:
   - "What are the risks of migrating from MySQL to PostgreSQL?"
   - "Analyze the risks of BigQuery to Redshift migration"

2. **Schema Compatibility**:
   - "Check compatibility between Oracle and PostgreSQL"
   - "What data types are incompatible between MySQL and BigQuery?"

3. **Specific Issues**:
   - "How do I handle ENUM types when migrating to PostgreSQL?"
   - "What happens to stored procedures in a BigQuery migration?"

---

## 💰 Pricing (Anthropic API)

- **Claude 3.5 Sonnet**: $3 per million input tokens, $15 per million output tokens
- **Average chat**: ~500-1000 tokens
- **Estimated cost**: $0.01-0.02 per conversation
- **Very affordable for development and testing!**

---

## ❓ Troubleshooting

### Issue: Still getting welcome message
**Check**: 
1. Did you add the API key to `.env`?
2. Did you save the file?
3. Did the backend reload? (check terminal)

### Issue: "Failed to initialize Claude AI client"
**Check**:
1. API key is correct (starts with `sk-ant-api03-`)
2. No extra spaces in the `.env` file
3. Internet connection is working

### Issue: Backend not reloading
**Solution**: Manually restart the backend:
```bash
# Stop with Ctrl+C
# Then restart:
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ✅ Success Indicators

You'll know Claude is working when:

1. **Backend logs show**:
   ```
   Claude AI client (Anthropic API) initialized successfully
   ```

2. **ChatAgent responses are**:
   - Detailed and contextual
   - Different each time you ask
   - Formatted with headings and bullet points
   - Specific to your question

3. **NOT the welcome message**:
   - If you keep getting "Hello! I'm your Assessment AI Assistant..."
   - Claude is NOT active yet

---

**Need Help?** Check the backend terminal for error messages!
