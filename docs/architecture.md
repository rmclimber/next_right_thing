### Overview:
Frontend:
- Next.js

API:
- Lambda + API Gateway

Background jobs:
- ECS/Fargate

DB:
- Aurora PostgreSQL

Storage:
- S3

Auth:
- Cognito

### Principles
- Frontend never accesses DB directly
- Ranking logic lives only in recommendation service
- API contracts are source of truth
- Shared types live in /packages/shared