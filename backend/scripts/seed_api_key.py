from app.db import SessionLocal
from app.models.api_key import ApiKey, ApiKeyStatus

KEY = "dev-key-123"   # change if you want
ORG_ID = 1            # whatever makes sense for your MVP

def main():
    db = SessionLocal()
    try:
        existing = db.query(ApiKey).filter(ApiKey.key == KEY).first()
        if existing:
            existing.status = ApiKeyStatus.ACTIVE
            existing.org_id = ORG_ID
            db.commit()
            print("Updated existing key:", KEY)
            return

        db.add(ApiKey(key=KEY, org_id=ORG_ID, status=ApiKeyStatus.ACTIVE))
        db.commit()
        print("Created API key:", KEY)
    finally:
        db.close()

if __name__ == "__main__":
    main()