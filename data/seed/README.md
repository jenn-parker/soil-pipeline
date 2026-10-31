# SSURGO demo seed data

`ssurgo-iowa-demo.csv` contains ten representative Iowa soil-survey locations.
The coordinates are selected reference points near Iowa communities. Each record
uses the dominant component's surface-horizon properties returned by the USDA
NRCS Soil Data Access service, including pH, organic matter, and texture.

These records are intentionally labeled as representative SSURGO data. They are
not claims that a physical sample was collected at the displayed coordinate.

Sources:

- USDA NRCS [Soil Survey Geographic Database (SSURGO)](https://www.nrcs.usda.gov/resources/data-and-reports/soil-survey-geographic-database-ssurgo)
- USDA NRCS [Soil Data Access web service](https://sdmdataaccess.sc.egov.usda.gov/WebServiceHelp.aspx)

To load the records into the local PostGIS database from the repository root:

```bash
docker compose exec -T db psql -U earth_user -d soil_db < scripts/seed_ssurgo_demo.sql
```
