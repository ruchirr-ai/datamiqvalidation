# Claude AI Integration Guide

## Overview
The ChatAgent now supports Claude AI integration for intelligent, context-aware responses about database migrations and assessments.

## Features Added

### 1. Migration Risk Analysis (Quick Action)
- ⚠️ **Migration Risk Analysis** button added to quick actions
- Analyzes potential risks before database migration
- Covers data loss, schema compatibility, performance, and application risks
- Provides step-by-step guidance

### 2. Schema Compatibility (Quick Action)
- 🔄 **Schema Compatibility** button added to quick actions
- Checks compatibility between source and target databases
- Identifies data type mismatches and feature incompatibilities
- Offers resolution strategies

### 3. Claude AI Integration
- Powered by Claude 3.5 Sonnet (latest model)
- Context-aware responses based on current page
- Conversation history support (last 5 messages)
- Structured markdown responses
- Fallback to knowledge base if Claude unavailable

## Configuration

### Option 1: Anthropic API (Recommended)

1. **Get API Key**
   - Sign up at https://console.anthropic.com/
   - Create an API key
   - Copy the key

2. **Update .env file**
   ```env
   ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
   CLAUDE_MODEL=claude-3-5-sonnet-20241022
   CLAUDE_MAX_TOKENS=4096
   CLAUDE_TEMPERATURE=0.7
   ```

3. **Restart Backend**
   ```bash
   # The backend will auto-reload if using --reload flag
   # Otherwise restart manually
   ```

### Option 2: AWS Bedrock (Alternative)

1. **Configure AWS Credentials**
   ```env
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   ```

2. **Enable Bedrock**
   ```env
   CLAUDE_USE_BEDROCK=true
   CLAUDE_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
   ```

3. **Ensure Bedrock Access**
   - Enable Claude model in AWS Bedrock console
   - Grant IAM permissions for bedrock-runtime

### Fallback Mode (No Configuration)

If neither Anthropic API nor Bedrock is configured:
- ChatAgent uses local knowledge base
- 10 pre-built topics with detailed responses
- No external API calls
- Fully functional offline mode

## Quick Actions Updated

The quick action bar now shows:

1. ⚠️ **Migration Risk Analysis** - Analyze migration risks
2. 🔄 **Schema Compatibility** - Check schema compatibility
3. 📊 **Create Assessment** - How to create assessments
4. 📄 **View Reports** - How to view reports

## Claude AI Capabilities

### What Claude Can Help With

**Migration Planning**
- Risk assessment and mitigation strategies
- Best practices for database migrations
- Step-by-step migration guides
- Troubleshooting common issues

**Schema Analysis**
- Compatibility checking between databases
- Data type mapping recommendations
- Feature parity analysis
- Constraint and index strategies

**Assessment Guidance**
- Creating and configuring assessments
- Interpreting assessment reports
- Data profiling insights
- Performance optimization tips

**Database Connections**
- Connection setup for various databases
- Troubleshooting connection issues
- Security best practices
- Permission requirements

### Response Format

Claude provides:
- Structured markdown with headings
- Bullet points and numbered lists
- Code examples when relevant
- Step-by-step instructions
- Risk highlights and warnings
- Best practices and recommendations

## Testing Claude Integration

### 1. Check Configuration
```bash
# Backend logs will show:
# "Claude AI client (Anthropic API) initialized successfully"
# OR
# "AWS Bedrock client initialized successfully"
# OR
# "Claude AI not configured, using fallback knowledge base"
```

### 2. Test Quick Actions
1. Open ChatAgent
2. Click "Migration Risk Analysis"
3. Verify response is detailed and contextual
4. Click "Schema Compatibility"
5. Verify response covers compatibility topics

### 3. Test Conversation
1. Ask: "What are the risks of migrating from MySQL to PostgreSQL?"
2. Follow up: "How do I handle ENUM types?"
3. Verify Claude maintains context across messages

### 4. Test Fallback
1. Temporarily remove ANTHROPIC_API_KEY from .env
2. Restart backend
3. Verify ChatAgent still works with knowledge base
4. Responses should be from pre-built topics

## API Usage and Costs

### Anthropic API Pricing (as of 2024)
- Claude 3.5 Sonnet: $3 per million input tokens, $15 per million output tokens
- Average chat message: ~500-1000 tokens
- Estimated cost: $0.01-0.02 per conversation

### AWS Bedrock Pricing
- Similar to Anthropic API
- Billed through AWS account
- May have volume discounts

### Cost Optimization
- Responses cached in conversation history
- Max 5 messages sent for context
- Fallback to knowledge base on errors
- No API calls for suggested queries (uses knowledge base)

## Monitoring

### Backend Logs
```python
# Success
logger.info("Claude AI client initialized successfully")
logger.info(f"ChatAgent request: {message} (context: {context})")
logger.info("ChatAgent response generated successfully")

# Errors
logger.error(f"Claude AI error: {e}, falling back to knowledge base")
logger.warning(f"Failed to initialize Claude AI client: {e}")
```

### Frontend Feedback
- Users can provide thumbs up/down on responses
- Feedback logged to console (ready for analytics)
- Track which responses are helpful

## Troubleshooting

### Issue: "Claude AI not configured"
**Solution**: Add ANTHROPIC_API_KEY to .env file

### Issue: "Failed to initialize Claude AI client"
**Solution**: 
- Check API key is valid
- Verify internet connection
- Check anthropic package is installed: `pip install anthropic`

### Issue: Responses are generic
**Solution**:
- Verify Claude is initialized (check logs)
- If using fallback, responses will be from knowledge base
- Add API key for intelligent responses

### Issue: Slow responses
**Solution**:
- Claude API typically responds in 2-5 seconds
- Check network latency
- Consider reducing CLAUDE_MAX_TOKENS

### Issue: API rate limits
**Solution**:
- Anthropic has generous rate limits
- Implement request queuing if needed
- Consider caching common responses

## Security Best Practices

### API Key Security
- Never commit .env file to version control
- Use .env.example for documentation
- Rotate API keys regularly
- Use AWS Secrets Manager in production

### Data Privacy
- No sensitive data sent to Claude
- User messages are not stored by Anthropic (per their policy)
- Conversation history limited to 5 messages
- Workspace context included but no PII

### Production Deployment
- Use environment variables, not .env files
- Store API keys in AWS Secrets Manager
- Enable CloudWatch logging
- Monitor API usage and costs
- Implement rate limiting

## Future Enhancements

### Potential Additions
- Function calling for database queries
- Image analysis for schema diagrams
- Multi-turn planning conversations
- Custom knowledge base integration
- Fine-tuned models for specific databases
- Streaming responses for real-time feedback

## Support

### Documentation
- Anthropic API Docs: https://docs.anthropic.com/
- AWS Bedrock Docs: https://docs.aws.amazon.com/bedrock/

### Getting Help
- Check backend logs for errors
- Verify .env configuration
- Test with fallback mode first
- Review CHATAGENT_FEATURES.md for UI features

---

**Status**: ✅ Production Ready with Claude AI
**Version**: 2.1.0
**Last Updated**: March 1, 2026
