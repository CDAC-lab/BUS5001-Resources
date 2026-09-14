# Databricks notebook source
# MAGIC %md
# MAGIC # New York Taxi Trips Dataset — Data Ingestion
# MAGIC The NYC Taxi and Limousine Commission (TLC) publishes taxi trip data monthly. This notebook downloads a
# MAGIC small subset of the official **yellow taxi** trip records directly from the TLC's public CloudFront
# MAGIC distribution and saves it as a managed Delta table so the other two notebooks can use it.
# MAGIC
# MAGIC The data dictionary can be found [here](https://www1.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf).
# MAGIC
# MAGIC Dataset info page: [link](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
# MAGIC
# MAGIC **Run this notebook first.** The Setup Spatial Analysis and Data Exploration notebooks both depend on
# MAGIC the table it creates.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What changed for Databricks Free Edition
# MAGIC The original notebook read from a course-specific Azure Blob container
# MAGIC (`bus5001.blob.core.windows.net`) that no longer exists, and wrote Delta tables to raw DBFS paths
# MAGIC (`/bus5001/...`, `/data/...`). Neither works on Free Edition:
# MAGIC - Free Edition only offers **serverless compute**, which restricts direct DBFS root access — Unity
# MAGIC   Catalog **tables** and **volumes** are used instead of `dbfs:/` paths.
# MAGIC - Outbound internet access on Free Edition is limited to a small set of trusted domains, so this
# MAGIC   notebook downloads data directly from the **official TLC CloudFront source**
# MAGIC   (`d37ci6vzurychx.cloudfront.net`) rather than a private mirror.
# MAGIC - As a safety net, if that download is blocked by your workspace's network policy, the notebook
# MAGIC   automatically falls back to the built-in `samples.nyctaxi.trips` demo table so you can still run
# MAGIC   everything end‑to‑end. That sample table only has pickup/dropoff **ZIP codes** (no TLC
# MAGIC   `LocationID`s), so the zone-map sections of the Data Exploration notebook will show a message and
# MAGIC   skip themselves rather than fail.
# MAGIC
# MAGIC Make sure this notebook is attached to **Serverless** compute (the default on Free Edition).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration
# MAGIC Creates (if needed) a schema and a Unity Catalog volume to hold the raw downloaded files, in whatever
# MAGIC catalog is currently the default for your workspace.

# COMMAND ----------

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "nyc_taxi_demo"
VOLUME = "raw_files"

TRIPS_TABLE = f"{CATALOG}.{SCHEMA}.nyc_yellow_trips"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")

print(f"Catalog:     {CATALOG}")
print(f"Schema:      {SCHEMA}")
print(f"Trips table: {TRIPS_TABLE}")
print(f"Volume path: {VOLUME_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Download raw trip data from the official TLC source
# MAGIC Files are stored as monthly Parquet files at
# MAGIC `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{YYYY}-{MM}.parquet`.
# MAGIC
# MAGIC Free Edition has limited storage/compute quota, so this defaults to just **two months** (~1 GB
# MAGIC combined). Add more entries to `MONTHS` below if your quota allows — remove some if you hit limits.

# COMMAND ----------

import os
import requests

MONTHS = ["2019-01", "2019-02"]  # e.g. add "2019-03" for a 3rd month
BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"


def download_month(month: str) -> str:
    dest_path = f"{VOLUME_PATH}/yellow_tripdata_{month}.parquet"
    if os.path.exists(dest_path):
        print(f"{month}: already downloaded, skipping")
        return dest_path
    url = BASE_URL.format(month=month)
    print(f"{month}: downloading {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(chunk)
    return dest_path


downloaded_paths = []
download_failed = False
for m in MONTHS:
    try:
        downloaded_paths.append(download_month(m))
    except Exception as e:
        print(f"Could not download {m}: {e}")
        download_failed = True
        break

USE_SAMPLE_FALLBACK = download_failed or len(downloaded_paths) == 0

if USE_SAMPLE_FALLBACK:
    print(
        "\nFalling back to the built-in samples.nyctaxi.trips table — either the download failed or "
        "your workspace's network policy blocked d37ci6vzurychx.cloudfront.net."
    )
else:
    print(f"\nDownloaded {len(downloaded_paths)} file(s) into {VOLUME_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load and standardise the schema
# MAGIC Renames the official TLC column names to the friendlier names the rest of these notebooks use, and
# MAGIC builds the same fallback path against `samples.nyctaxi.trips` if the download above didn't succeed.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Data dictionary (official TLC yellow taxi Parquet schema)
# MAGIC ```
# MAGIC VendorID:int                 --> vendor_id string
# MAGIC tpep_pickup_datetime:ts      --> pickup_datetime datetime
# MAGIC tpep_dropoff_datetime:ts     --> dropoff_datetime datetime
# MAGIC passenger_count:double       --> passenger_count integer
# MAGIC trip_distance:double         --> trip_distance double
# MAGIC PULocationID:int             --> pickup_location_id double
# MAGIC DOLocationID:int             --> dropoff_location_id double
# MAGIC RatecodeID:double            --> rate_code_id string
# MAGIC store_and_fwd_flag:string    --> store_and_forward string
# MAGIC payment_type:int             --> payment_type integer
# MAGIC fare_amount:double           --> fare_amount double
# MAGIC extra:double                 --> extra double
# MAGIC mta_tax:double                --> mta_tax double
# MAGIC tip_amount:double            --> tip_amount double
# MAGIC tolls_amount:double          --> tolls_amount double
# MAGIC total_amount:double          --> total_amount double
# MAGIC ```

# COMMAND ----------

from pyspark.sql.functions import col, lit, spark_partition_id, asc
from pyspark.sql.types import DoubleType, IntegerType

if not USE_SAMPLE_FALLBACK:
    raw_df = spark.read.parquet(*downloaded_paths)

    df_yellow = (
        raw_df.withColumnRenamed("VendorID", "vendor_id")
        .withColumnRenamed("tpep_pickup_datetime", "pickup_datetime")
        .withColumnRenamed("tpep_dropoff_datetime", "dropoff_datetime")
        .withColumnRenamed("RatecodeID", "rate_code_id")
        .withColumnRenamed("store_and_fwd_flag", "store_and_forward")
        .withColumn("pickup_location_id", col("PULocationID").cast(DoubleType()))
        .withColumn("dropoff_location_id", col("DOLocationID").cast(DoubleType()))
        .withColumn("passenger_count", col("passenger_count").cast(IntegerType()))
        .withColumn("trip_distance", col("trip_distance").cast(DoubleType()))
        .withColumn("fare_amount", col("fare_amount").cast(DoubleType()))
        .withColumn("extra", col("extra").cast(DoubleType()))
        .withColumn("mta_tax", col("mta_tax").cast(DoubleType()))
        .withColumn("tip_amount", col("tip_amount").cast(DoubleType()))
        .withColumn("tolls_amount", col("tolls_amount").cast(DoubleType()))
        .withColumn("total_amount", col("total_amount").cast(DoubleType()))
        .withColumn("payment_type", col("payment_type").cast(IntegerType()))
        .select(
            "vendor_id", "pickup_datetime", "dropoff_datetime", "store_and_forward",
            "rate_code_id", "pickup_location_id", "dropoff_location_id", "passenger_count",
            "trip_distance", "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
            "total_amount", "payment_type",
        )
    )
    df_yellow_18_19 = df_yellow.filter(
        (col("pickup_datetime") >= "2019-01-01") & (col("pickup_datetime") < "2019-03-01")
    )
else:
    sample_df = spark.table("samples.nyctaxi.trips")
    # samples.nyctaxi.trips only has: tpep_pickup_datetime, tpep_dropoff_datetime, trip_distance,
    # fare_amount, pickup_zip, dropoff_zip — everything else is filled in as null so the schema still
    # matches, and total_amount is approximated from fare_amount since there's no tip/tax breakdown.
    df_yellow_18_19 = (
        sample_df.withColumnRenamed("tpep_pickup_datetime", "pickup_datetime")
        .withColumnRenamed("tpep_dropoff_datetime", "dropoff_datetime")
        .withColumn("vendor_id", lit(None).cast("string"))
        .withColumn("store_and_forward", lit(None).cast("string"))
        .withColumn("rate_code_id", lit(None).cast("string"))
        .withColumn("pickup_location_id", lit(None).cast(DoubleType()))
        .withColumn("dropoff_location_id", lit(None).cast(DoubleType()))
        .withColumn("passenger_count", lit(None).cast(IntegerType()))
        .withColumn("trip_distance", col("trip_distance").cast(DoubleType()))
        .withColumn("fare_amount", col("fare_amount").cast(DoubleType()))
        .withColumn("extra", lit(None).cast(DoubleType()))
        .withColumn("mta_tax", lit(None).cast(DoubleType()))
        .withColumn("tip_amount", lit(None).cast(DoubleType()))
        .withColumn("tolls_amount", lit(None).cast(DoubleType()))
        .withColumn("total_amount", col("fare_amount").cast(DoubleType()))
        .withColumn("payment_type", lit(None).cast(IntegerType()))
        .select(
            "vendor_id", "pickup_datetime", "dropoff_datetime", "store_and_forward",
            "rate_code_id", "pickup_location_id", "dropoff_location_id", "passenger_count",
            "trip_distance", "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
            "total_amount", "payment_type",
        )
    )

display(df_yellow_18_19.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sanity check: partition sizes

# COMMAND ----------

display(
    df_yellow_18_19.withColumn("partitionId", spark_partition_id())
    .groupBy("partitionId")
    .count()
    .orderBy(asc("count"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save as a managed Delta table

# COMMAND ----------

(
    df_yellow_18_19.write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(TRIPS_TABLE)
)

row_count = spark.table(TRIPS_TABLE).count()
print(f"Saved {row_count:,} rows to {TRIPS_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Optimize the table

# COMMAND ----------

spark.sql(f"OPTIMIZE {TRIPS_TABLE} ZORDER BY (pickup_datetime)")

# COMMAND ----------

display(spark.sql(f"DESCRIBE DETAIL {TRIPS_TABLE}"))

# COMMAND ----------

display(spark.sql(f"SELECT count(*) AS row_count FROM {TRIPS_TABLE}"))
