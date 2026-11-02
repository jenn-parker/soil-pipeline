# Soil Pipeline Demo Script

This walkthrough is designed for a five-to-ten-minute interview or portfolio demonstration. It highlights the product workflow first, then briefly connects the experience to the implementation.

## Before the demo

From the repository root:

```bash
docker compose up -d --build
cd frontend
npm run dev -- --host 127.0.0.1 > /tmp/soil-pipeline-vite.log 2>&1 &
```

Open <http://localhost:5173>. Use the Cognito sign-in flow when demonstrating OAuth. The local API-key mode is available as a fallback for a quick offline demo.

## 1. Introduce the product

Say:

> Soil Pipeline is a secure workspace for locating soil samples, reviewing field context, and managing traceable soil data. I built it to demonstrate a complete path from data ingestion through spatial reporting and sample-level authorization.

Point out the dashboard, connection status, map, measurement summary, and upload workflow.

## 2. Explore the map

1. Explain that the initial markers are representative Iowa records derived from USDA NRCS SSURGO data.
2. Click a marker such as Ames, Mason City, or Sioux City.
3. Show the popup measurements and the coordinates copied into the report form.
4. Change the **Color by** selector from pH to organic matter or texture.
5. Run a nearby report and point out the sample count, date window, and measurement ranges.
6. Expand **Add recommendation context**, enter `Corn`, `Iowa`, `200`, `bu/acre`, `Example Lab`, and `Mehlich-3`, then enable **Generate AI explanation** and run the soil brief. Show the returned explanation and its safety note.

Say:

> The map and report use the same spatial data, but the report deliberately summarizes ranges rather than pretending multiple nearby samples are one composite result.

Say:

> The AI feature is deliberately opt-in. It receives aggregate measurements and the context I provide, not exact coordinates or sample IDs. It explains the summary in plain language; it does not prescribe rates or replace a lab, agronomist, or extension recommendation.

## 3. Add one sample manually

1. Select **Enter one sample manually**.
2. Use fictional values, for example:

   - Sample ID: `DEMO-WAVERLY-01`
   - Field name: `North Field`
   - Latitude: `42.7272`
   - Longitude: `-92.4669`
   - pH: `6.5`
   - Organic matter: `3.8`

3. Save the sample.
4. Return to the dashboard and refresh the map.
5. Open the new marker.

Point out that the newly created record shows owner actions while the reference records remain read-only.

## 4. Demonstrate ownership and sharing

1. Open **My samples** from the navigation.
2. Select **Edit** for the new sample and change a value, such as the field name.
3. Return to **My samples**.
4. Select **Manage access**.
5. Grant a fictional signed-in user viewer or editor access.

Say:

> Authentication establishes who the user is, but authorization happens at the sample level. The owner can share a record, and an editor can modify it without becoming the owner.

## 5. Demonstrate archive and restore

1. Return to **My samples**.
2. Archive the demo sample.
3. Show that it disappears from the active list and map.
4. Enable **Include archived samples**.
5. Restore the sample.
6. Refresh the dashboard map and show that it is visible again.

Say:

> Archive is a reversible workflow that removes a sample from normal operational views while preserving its history and access records. Hard deletion remains a separate owner-only operation.

## 6. Upload a CSV batch

1. Return to the dashboard.
2. Open **View CSV format and example**.
3. Choose `data/seed/ssurgo-iowa-demo.csv`, or use a small fictional CSV.
4. Upload the batch.
5. Point out accepted and rejected row counts.
6. Refresh the map and show the imported locations.

Say:

> The API validates the complete file before inserting samples. Invalid batches return row-level errors and do not partially save the file.

## 7. Close with the engineering story

Use this summary:

> The frontend is React and TypeScript, the API is FastAPI, and PostgreSQL/PostGIS handles relational and spatial queries. Cognito provides OAuth authentication, while ownership and sharing enforce sample-level authorization. Terraform manages the AWS authentication, storage, and IAM foundation. Docker Compose keeps the full demo reproducible locally, and GitHub Actions validates backend tests, frontend builds, Terraform, and the API image without requiring a live deployment.

If asked about production deployment, explain that the repository intentionally does not provision EKS, compute, RDS, networking, or a public endpoint. Those are documented as a future deployment phase so the portfolio demo does not incur unnecessary ongoing cloud costs.

## Backup talking points

- Why PostGIS: spatial filtering and radius reports belong in the database.
- Why Cognito: managed OAuth and token validation without storing passwords.
- Why PKCE: protects the browser authorization-code flow without a client secret.
- Why archive: safer operational recovery than immediate deletion.
- Why no live deployment: the local environment demonstrates the application without creating always-on cloud spend.
- Why CI without deployment: the repository proves repeatable validation while keeping cloud credentials out of pull requests.

