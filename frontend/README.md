# CodeBouncer Frontend

Next.js frontend with a "Dev Tool" aesthetic for the CodeBouncer security scanner.

## Features
- **Circular Floating Nav**: Smooth, animated navigation dock.
- **Terminal Output**: Real-time scan logs.
- **Dark Mode**: High-contrast, glowing accents.
- **Dashboard**: High-level security metrics.

## Setup

1.  **Install dependencies**:
    ```bash
    npm install
    ```

2.  **Run Development Server**:
    ```bash
    npm run dev
    ```

3.  **Run Backend** (Required for data):
    From the root of the repo:
    ```bash
    python -m uvicorn src.api:app --reload
    ```

## Stack
- Next.js 14+ (App Router)
- Tailwind CSS
- Framer Motion
- Lucide React
