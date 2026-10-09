# Implementation instructions
Build the working FoodWise AI application from this pack; do not stop at scaffolding or documentation.
Inspect the current repository first. Preserve unrelated work. Resolve routine implementation choices yourself.
Use React/Vite/TypeScript, Tailwind, Recharts; FastAPI/Pydantic, Pandas/NumPy and SQLite. Local execution is the deliverable; no deployment required.
Do not add authentication, autonomous agents, vector databases, IoT, image-based safety certification, or NGO integrations.
All calculations and safety transitions are server-owned. The LLM explains validated evidence only. The complete demo must work without an API key or internet after dependencies are installed.
Implement P0 first. P1 only after P0 acceptance passes. Do not create extra agents unless explicitly authorized by the user.
No embedded secrets. Add .env.example and ignore .env. Verify installed SDK/API interfaces against current official documentation when implementing the optional provider adapter; do not guess model IDs.
Run meaningful domain tests, frontend type/build checks, and an end-to-end local demo. Report actual check results and unresolved issues honestly.
No redistribution approval based on origin alone. Demo eligibility is policy review, not food-safety certification.
Use kg for cooked-food mass. Convert count-based dishes via explicit measured piece weight; never silently treat raw ingredient kg as cooked-food kg.
