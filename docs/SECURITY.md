# INSIGHT - Security & Credentials Management

**Last Updated:** 2025-10-10
**Status:** 🔒 Confidential

---

## ⚠️ **CRITICAL SECURITY NOTICE**

You have exposed AWS credentials in this conversation. **You must rotate them immediately.**

### **Exposed Credentials (DEACTIVATE THESE NOW):**

```
Access Key ID: AKIA****************        ← ROTATE IMMEDIATELY
Secret Key: ************************************   ← ROTATE IMMEDIATELY
```

---

## 🚨 **IMMEDIATE ACTION REQUIRED**

### **Step 1: Deactivate Exposed Credentials**

1. Go to: https://console.aws.amazon.com/iam/home#/users/insight-s3-reader?section=security_credentials
2. Find your exposed access key
3. Click **Actions** → **Deactivate** → Confirm
4. Then click **Actions** → **Delete** → Confirm

### **Step 2: Create New Access Key**

1. Click **Create access key**
2. Select: **Application running outside AWS**
3. Download CSV immediately
4. Update `.env` with NEW credentials
5. Test connection

### **Step 3: Verify Rotation**

```bash
# Check if old key is deactivated
aws iam list-access-keys --user-name insight-s3-reader

# Should show only your new key ID
```

---

## 🔐 **Security Best Practices**

### **1. Never Commit Credentials to Git**

✅ **Protected (Already configured):**
- `.env` is in `.gitignore`
- All `*.env*` files ignored
- Git will not track credentials

❌ **Never do this:**
```bash
# Bad - exposes credentials
git add .env
git commit -m "add config"
```

✅ **Always check before committing:**
```bash
# Verify .env is ignored
git status

# .env should NOT appear in the output
```

---

### **2. Use Environment Variables Only**

✅ **Correct:**
```python
import os
from dotenv import load_dotenv
load_dotenv()

access_key = os.getenv('AWS_ACCESS_KEY_ID')
```

❌ **Never hardcode:**
```python
# NEVER DO THIS
access_key = "AKIA****************"
```

---

### **3. Limit IAM Permissions**

Your IAM user should have **minimum required permissions**:

**Current Policy:** `AmazonS3ReadOnlyAccess`
- ✅ Can read S3 objects
- ❌ Cannot delete
- ❌ Cannot modify
- ❌ Cannot access other AWS services

**Recommended Custom Policy:**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:ap-southeast-2:228067885723:accesspoint/usa-linkedin-data",
                "arn:aws:s3:ap-southeast-2:228067885723:accesspoint/usa-linkedin-data/object/*"
            ]
        }
    ]
}
```

This limits access to **only your specific Access Point**.

---

### **4. Rotate Credentials Regularly**

**Schedule:**
- Rotate every **90 days** minimum
- Rotate immediately if:
  - Credentials exposed publicly
  - Employee leaves project
  - Suspicious activity detected

**How to Rotate:**
1. Create new access key
2. Update `.env` with new key
3. Test application works
4. Delete old access key
5. Document rotation in changelog

---

### **5. Monitor Access Logs**

Enable S3 access logging:

1. S3 Console → Your bucket → **Properties**
2. **Server access logging** → Enable
3. Target bucket: Create a separate logging bucket
4. Review logs regularly for unauthorized access

---

### **6. Use AWS Secrets Manager (Production)**

For production deployments, use AWS Secrets Manager instead of `.env`:

```python
import boto3
import json

def get_secret():
    client = boto3.client('secretsmanager', region_name='ap-southeast-2')
    secret = client.get_secret_value(SecretId='insight/s3-credentials')
    return json.loads(secret['SecretString'])

credentials = get_secret()
access_key = credentials['AWS_ACCESS_KEY_ID']
```

**Benefits:**
- Automatic rotation
- Audit logging
- Encryption at rest
- No credentials in code

---

## 📋 **Security Checklist**

### **Initial Setup:**
- [x] `.env` file created
- [x] `.env` in `.gitignore`
- [x] IAM user created with limited permissions
- [ ] **Old credentials deactivated** ⚠️ DO THIS NOW
- [ ] New credentials generated
- [ ] New credentials in `.env`
- [ ] Connection tested with new credentials

### **Ongoing:**
- [ ] Credentials rotated every 90 days
- [ ] S3 access logs reviewed monthly
- [ ] No credentials in code/commits
- [ ] `.env` never shared publicly

---

## 🔍 **How to Check for Exposed Credentials**

### **Check Git History:**
```bash
# Search for potential credential leaks
git log --all --full-history --source -- .env
git log --all -S "AWS_ACCESS_KEY_ID"
git log --all -S "AKIA"

# Should return nothing if .env was never committed
```

### **Check Current Staging:**
```bash
# Verify .env is not staged
git status

# Should show:
# On branch main
# nothing to commit, working tree clean
```

### **Check Remote:**
```bash
# Verify .env was never pushed
git log --all --remotes --source -- .env

# Should return nothing
```

---

## 🚨 **If Credentials Are Compromised**

### **Immediate Actions (Within 5 minutes):**

1. **Deactivate compromised credentials:**
   ```
   IAM Console → Users → Security credentials → Deactivate key
   ```

2. **Check CloudTrail for unauthorized activity:**
   ```
   CloudTrail Console → Event history → Filter by compromised key
   ```

3. **Create new credentials:**
   ```
   Generate new access key → Update .env → Test
   ```

4. **Delete compromised credentials:**
   ```
   IAM Console → Delete deactivated key
   ```

### **Within 1 Hour:**

5. **Review S3 access logs:**
   - Check for unusual download patterns
   - Look for unknown IP addresses
   - Verify only expected data was accessed

6. **Notify team:**
   - Document incident
   - Update security procedures
   - Review access controls

### **Within 24 Hours:**

7. **Security audit:**
   - Review all IAM policies
   - Check for unauthorized resources
   - Verify bucket permissions
   - Update security documentation

---

## 📖 **Additional Resources**

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [AWS Security Best Practices](https://aws.amazon.com/architecture/security-identity-compliance/)
- [Git-secrets (prevent credential commits)](https://github.com/awslabs/git-secrets)

---

## 🆘 **Contact for Security Issues**

If you discover a security vulnerability:

1. **DO NOT** post publicly
2. **DO NOT** commit to git
3. Rotate credentials immediately
4. Document incident privately
5. Update security procedures

---

**Remember:** Security is not a one-time task. It's an ongoing process.

**Next security review:** 2026-01-10 (90 days from now)
