# Written Submission Note: Architecture, RBAC Scaling, and Production Readiness

## 1. Schema Design and Normalization Tradeoffs

The database schema is structured around four primary entities: `users`, `students`, `sessions`, and `evaluations`. 
- A one-to-many relationship exists between `users` (specifically parents) and `students` via the `students.parent_id` foreign key.
- A `sessions` record bridges a teacher (FK to `users.id`) and a student (FK to `students.id`).
- An `evaluations` record is associated 1-to-1 with a `sessions` record (enforced via a `unique` constraint on `evaluations.session_id`).

### Normalization Tradeoffs
The relational database is normalized to Third Normal Form (3NF) to guarantee transactional integrity and prevent anomalies (such as duplicate child-parent mappings). However, to support high-throughput read operations on the `/sessions/{id}` endpoint, we implement a **de-normalization tradeoff** in the caching layer. The JSON payload cached in Redis stores the student's `parent_id` directly inside the session object. This allows our RBAC authorization logic to inspect permissions instantly without performing database joins or extra queries, significantly reducing database load on hot read paths.

---

## 2. Scaling RBAC to Nested Organizations or a Fourth Role

### Supporting a Fourth Role (e.g., Student)
To support a `student` role logging in directly, we would transition the `students` table to link back to the `users` table via a `user_id` foreign key (or unify them). The RBAC middleware would simply add an authorization path: if the user's role is `student`, they can read the session if `session.student.user_id == current_user.id`.

### Supporting Nested Organizations
For nested organizations (e.g., *District > School > Department > Class*), a flat role-based system fails. We would transition to a hierarchical, attribute-based access control (ABAC) or relationship-based access control (ReBAC) system:
1.  **Organization Hierarchy**: Model organizations as a tree structure using a **Closure Table** or adjacency list to represent ancestor-descendant relationships.
2.  **User Memberships**: Create an `organization_memberships` table linking `user_id`, `org_id`, and a context-specific `role` (e.g., `school_admin`, `department_head`).
3.  **Scope Verification**: The authorization middleware would trace the resource's organization ID and verify if it falls within the subtree of any organization where the logged-in user holds sufficient administrative privileges.

---

## 3. Gaps Preventing Production Readiness

For this service to be deployed in a secure, scalable production environment, several components must be added:
-   **Database Migrations**: Currently, tables are auto-created on startup. We must implement **Alembic** to manage database schema updates incrementally and safely.
-   **Connection Pooling**: In a serverless or highly concurrent environment (like Supabase), direct database connections can exhaust DB limits. We should configure connection pooling using **PgBouncer** (in transaction mode) and tune SQLAlchemy's pool settings.
-   **Secrets Handling**: Environment variables are currently read from a local `.env` file. In production, sensitive variables (DB credentials, JWT secret keys, Redis URL) must be managed using a secure manager such as **Supabase Vault**, **AWS Secrets Manager**, or Docker Secrets.
-   **Secure Communication (TLS/SSL)**: All database connections (including Supabase Postgres and Redis) must enforce SSL/TLS (`sslmode=require`) to protect data in transit.
-   **Celery Failover**: The Celery queue requires persistent storage setups and dead-letter queues (DLQ) to handle failed evaluation runs and retry mechanics for transient failures (e.g., LLM rate limits).
