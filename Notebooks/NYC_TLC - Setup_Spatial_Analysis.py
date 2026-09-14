# Databricks notebook source
# MAGIC %md
# MAGIC ## Setup Spatial Analysis — Taxi Zone Reference Data
# MAGIC Downloads the official NYC TLC taxi zone shapefile and builds two small reference tables used by the
# MAGIC Data Exploration notebook:
# MAGIC - `taxi_zone_lookup` — LocationID → Borough / Zone / service_zone
# MAGIC - `taxi_zone_geom` — LocationID → zone name + polygon geometry (as WKT, reprojected to WGS84)
# MAGIC
# MAGIC Run the **Data Ingestion** notebook first. This notebook can then run before or after it doesn't
# MAGIC matter relative to Data Exploration, but Data Exploration needs the tables created here.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What changed for Databricks Free Edition
# MAGIC The original notebook downloaded a GeoJSON file to a scratch path under `dbfs:/tmp/mosaic/...` using
# MAGIC the DBFS FUSE mount, which serverless compute doesn't support. This version:
# MAGIC - Downloads the **official TLC taxi zone shapefile** (`taxi_zones.zip`) from the same
# MAGIC   `d37ci6vzurychx.cloudfront.net` domain used by the ingestion notebook, into a **Unity Catalog
# MAGIC   volume** instead of a DBFS path.
# MAGIC - Saves the result as two Delta **tables** rather than leaving it as a loose file, so it survives
# MAGIC   independently of any one cluster/session.
# MAGIC - If the download is blocked by your workspace's network policy, this notebook prints a clear
# MAGIC   message and skips table creation — the Data Exploration notebook detects that and skips its
# MAGIC   zone-map sections instead of erroring.

# COMMAND ----------

# MAGIC %pip install --quiet geopandas

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "nyc_taxi_demo"
VOLUME = "raw_files"

ZONE_LOOKUP_TABLE = f"{CATALOG}.{SCHEMA}.taxi_zone_lookup"
ZONE_GEOM_TABLE = f"{CATALOG}.{SCHEMA}.taxi_zone_geom"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")

print(f"Zone lookup table: {ZONE_LOOKUP_TABLE}")
print(f"Zone geom table:   {ZONE_GEOM_TABLE}")
print(f"Volume path:       {VOLUME_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Download the official TLC taxi zone shapefile

# COMMAND ----------

import pathlib
import zipfile

import requests

zones_zip_path = f"{VOLUME_PATH}/taxi_zones.zip"
zones_extract_dir = f"{VOLUME_PATH}/taxi_zones"

try:
    r = requests.get("https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip", timeout=120)
    r.raise_for_status()
    with open(zones_zip_path, "wb") as f:
        f.write(r.content)

    pathlib.Path(zones_extract_dir).mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zones_zip_path) as z:
        z.extractall(zones_extract_dir)

    zones_extract_dir = zones_extract_dir + '/taxi_zones' # The shapefile is nested in a folder
    zones_download_ok = True
    print("Downloaded and extracted the taxi zone shapefile.")
except Exception as e:
    zones_download_ok = False
    print(f"Could not download the taxi zone shapefile: {e}")
    print(
        "Your workspace's network policy may be blocking d37ci6vzurychx.cloudfront.net. "
        "The zone-map sections in the Data Exploration notebook will be skipped."
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build the zone lookup + zone geometry tables

# COMMAND ----------

if zones_download_ok:
    import geopandas as gpd

    shp_files = list(pathlib.Path(zones_extract_dir).glob("*.shp"))
    gdf = gpd.read_file(shp_files[0]).to_crs(4326)

    # Match columns case-insensitively — the shapefile's attribute names can vary slightly by source.
    col_by_lower = {c.lower(): c for c in gdf.columns}
    locid_col = col_by_lower["locationid"]
    zone_col = col_by_lower["zone"]
    borough_col = col_by_lower["borough"]

    zone_lookup_pdf = gdf[[locid_col, borough_col, zone_col]].rename(
        columns={locid_col: "LocationID", borough_col: "Borough", zone_col: "Zone"}
    )
    zone_lookup_pdf["service_zone"] = None
    zone_lookup_df = spark.createDataFrame(zone_lookup_pdf)
    (
        zone_lookup_df.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(ZONE_LOOKUP_TABLE)
    )

    zone_geom_pdf = gdf[[locid_col, zone_col]].rename(columns={locid_col: "LocationID", zone_col: "zone"})
    zone_geom_pdf["the_geom"] = gdf.geometry.to_wkt()
    zone_geom_df = spark.createDataFrame(zone_geom_pdf)
    (
        zone_geom_df.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(ZONE_GEOM_TABLE)
    )

    print(f"Saved {zone_lookup_df.count()} zones to {ZONE_LOOKUP_TABLE} and {ZONE_GEOM_TABLE}")
else:
    print("Skipping table creation since the shapefile could not be downloaded.")

# COMMAND ----------

if zones_download_ok:
    display(spark.table(ZONE_LOOKUP_TABLE).limit(10))

# COMMAND ----------

if zones_download_ok:
    display(spark.table(ZONE_GEOM_TABLE).limit(10))
