# Okapi Wildlife Reserve Power BI project

Open `OWR_Climate.pbip` in Power BI Desktop. The project contains a climate overview and forest change report backed by the repository's daily weather CSV, annual tree-cover-loss CSV, and monthly 2026 forest-alert CSV.

On the first refresh, allow anonymous access to the public raw GitHub CSV sources. The three model tables load `Meteo_owr.csv`, `TreeCoverLoss_owr.csv`, and `ForestAlerts_2026_owr.csv` from this repository's `main` branch.

To create the requested `.pbix`, open the project in Power BI Desktop, refresh the model, then choose **File → Save As → Power BI Desktop (.pbix)**. Power BI Desktop is required for this final conversion; it is not available in the Linux authoring environment.

The weather CSV still has missing source values for some dates in 1991. The annual tree-cover-loss series ends in 2025 and uses the Okapi Wildlife Reserve boundary from OpenStreetMap relation 401017 because the supplied Global Nature Watch AOI geometry was not publicly exposed. Tree-cover loss is not necessarily permanent deforestation. The 2026 alert total is a provisional detection count through October 4, not confirmed forest loss or unique hectares; monthly detections may repeat.
