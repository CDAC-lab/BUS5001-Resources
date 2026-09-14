# Databricks notebook source
# MAGIC %md
# MAGIC # New York Taxi Trips Dataset Analysis
# MAGIC The NYC Taxi and Limousine Commission (TLC) has publicly released a dataset of taxi trips from January
# MAGIC 2009 to date. Trip data is published monthly (with a couple of months' delay).
# MAGIC
# MAGIC The dataset forms one of the few publicly available big-data datasets: >100GB and more than 2 billion
# MAGIC records across its full history. There are 4 different types of trip data (yellow, green, for-hire and
# MAGIC high volume); this notebook focuses on **yellow taxi** trips.
# MAGIC
# MAGIC The data dictionary can be found [here](https://www1.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf)
# MAGIC
# MAGIC Dataset info page: [link](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
# MAGIC
# MAGIC <br>
# MAGIC
# MAGIC This notebook performs Exploratory Data Analysis (EDA) on the table built by the **Data Ingestion**
# MAGIC notebook, using the zone reference tables built by the **Setup Spatial Analysis** notebook.
# MAGIC
# MAGIC **Run order:** Data Ingestion → Setup Spatial Analysis → this notebook.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What changed for Databricks Free Edition
# MAGIC - The old `taxi_zones.csv` / `taxi_zone_lookup.csv` download from `bus5001.blob.core.windows.net` is
# MAGIC   gone — this notebook now reads the `taxi_zone_geom` / `taxi_zone_lookup` **Delta tables** created by
# MAGIC   the Setup Spatial Analysis notebook. If that notebook's download was blocked, the zone-map sections
# MAGIC   below detect that and skip themselves with a printed message instead of erroring.
# MAGIC - The old `spark.read.load("/bus5001/bigdata/delta/nyc-yellow")` and
# MAGIC   `` delta.`dbfs:/bus5001/bigdata/delta/nyc-yellow` `` references are gone — everything now reads
# MAGIC   from the managed table the Data Ingestion notebook created.
# MAGIC - `shapely.speedups` was removed from the Shapely library years ago (it's a no-op in modern
# MAGIC   Shapely 2.x), so that import/call is removed here — geopandas no longer needs it.
# MAGIC - `pandas_udf` / `PandasUDFType` were imported but never used, and `PandasUDFType` no longer exists in
# MAGIC   current PySpark, so that import is removed.
# MAGIC - `geopandas`, `folium`, `branca` and `mapclassify` (needed for the `scheme='quantiles'` maps) aren't
# MAGIC   preinstalled on Free Edition's serverless compute, so a `%pip install` cell was added.
# MAGIC
# MAGIC Make sure this notebook is attached to **Serverless** compute (the default on Free Edition).

# COMMAND ----------

# MAGIC %md
# MAGIC # Setup Environment

# COMMAND ----------

# MAGIC %md
# MAGIC ## Installing libraries not preinstalled on serverless compute

# COMMAND ----------

# MAGIC %pip install --quiet geopandas folium branca mapclassify

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Importing libraries

# COMMAND ----------

import pandas as pd
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
import folium
import geopandas as gpd

from branca.colormap import linear
from pyspark.sql.functions import *
from pyspark.sql.types import StringType, IntegerType, FloatType, DoubleType, DecimalType

# COMMAND ----------

# MAGIC %md
# MAGIC # Data Loading / Preparation

# COMMAND ----------

# MAGIC %md
# MAGIC Load the trip data and (if available) the taxi zone reference tables built by the other two
# MAGIC notebooks.

# COMMAND ----------

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "nyc_taxi_demo"

TRIPS_TABLE = f"{CATALOG}.{SCHEMA}.nyc_yellow_trips"
ZONE_LOOKUP_TABLE = f"{CATALOG}.{SCHEMA}.taxi_zone_lookup"
ZONE_GEOM_TABLE = f"{CATALOG}.{SCHEMA}.taxi_zone_geom"

df_yellow_18_19 = spark.table(TRIPS_TABLE)
df_yellow_18_19.createOrReplaceTempView("nyc_yellow_trips")

zones_available = spark.catalog.tableExists(ZONE_LOOKUP_TABLE) and spark.catalog.tableExists(ZONE_GEOM_TABLE)
if zones_available:
    spark.table(ZONE_GEOM_TABLE).createOrReplaceTempView("taxiGeom")
    spark.table(ZONE_LOOKUP_TABLE).createOrReplaceTempView("taxiZones")
    print("Zone reference tables loaded — zone-map sections below will run.")
else:
    print(
        "Zone reference tables not found. Run the 'Setup Spatial Analysis' notebook first — if you "
        "already have, its shapefile download was likely blocked by your workspace's network policy. "
        "The zone-map sections below will be skipped."
    )

# COMMAND ----------

if zones_available:
    display(spark.sql("SELECT * FROM taxiGeom LIMIT 20"))

# COMMAND ----------

if zones_available:
    display(spark.table(ZONE_LOOKUP_TABLE))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Transform Data

# COMMAND ----------

# MAGIC %md
# MAGIC The Data Ingestion notebook already:
# MAGIC - renamed columns to a consistent, meaningful format
# MAGIC - cast datetime strings to proper timestamp columns
# MAGIC - cast decimal values to Double type
# MAGIC
# MAGIC so `nyc_yellow_trips` (a view over the managed Delta table) is ready to query directly.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data dictionary
# MAGIC ```
# MAGIC vendor_id: string
# MAGIC pickup_datetime: timestamp
# MAGIC dropoff_datetime: timestamp
# MAGIC passenger_count: integer
# MAGIC trip_distance: double
# MAGIC pickup_location_id: double
# MAGIC dropoff_location_id: double
# MAGIC rate_code_id: string
# MAGIC store_and_forward: string
# MAGIC payment_type: integer
# MAGIC fare_amount: double
# MAGIC extra: double
# MAGIC mta_tax: double
# MAGIC tip_amount: double
# MAGIC tolls_amount: double
# MAGIC total_amount: double
# MAGIC ```
# MAGIC If the Data Ingestion notebook fell back to the built-in `samples.nyctaxi.trips` table (no internet
# MAGIC access), `pickup_location_id`/`dropoff_location_id` and several other columns will be `NULL` — the
# MAGIC zone-based sections below handle that gracefully.

# COMMAND ----------

from pyspark.sql.functions import spark_partition_id, asc, desc

display(
    df_yellow_18_19.withColumn("partitionId", spark_partition_id())
    .groupBy("partitionId")
    .count()
    .orderBy(asc("count"))
)

# COMMAND ----------

display(spark.sql(f"DESCRIBE DETAIL {TRIPS_TABLE}"))

# COMMAND ----------

display(df_yellow_18_19.describe())

# COMMAND ----------

# MAGIC %md
# MAGIC # Exploratory Data Analysis (EDA)

# COMMAND ----------

# MAGIC %md
# MAGIC Now you can run SQL queries on top of the temporary views and the Delta table created earlier. You
# MAGIC can also use the Spark DataFrame API to query as well.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Total trip count

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) FROM nyc_yellow_trips;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trip count by date using Spark API

# COMMAND ----------

df_yellow_18_19.count()

# COMMAND ----------

# MAGIC %sql
# MAGIC
# MAGIC SELECT
# MAGIC    COUNT(pickup_datetime) trip_count
# MAGIC   ,to_date(pickup_datetime) date
# MAGIC FROM nyc_yellow_trips
# MAGIC GROUP BY
# MAGIC    to_date(pickup_datetime)
# MAGIC ORDER BY
# MAGIC   to_date(date)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Payment type as a percentage over time

# COMMAND ----------

display(spark.sql(
    '''
    SELECT
       COUNT(*) trips
      ,to_date(pickup_datetime) date
      ,CASE
        WHEN payment_type = 1 THEN 'Credit card'
        WHEN payment_type = 2 THEN 'Cash'
        WHEN payment_type = 3 THEN 'No charge'
        WHEN payment_type = 4 THEN 'Dispute'
        WHEN payment_type = 5 THEN 'Unknown'
        ELSE 'Voided trip'
      END AS Payment_type
    FROM nyc_yellow_trips
    GROUP BY
       to_date(pickup_datetime)
      ,payment_type
    ORDER BY
      to_date(date)
    '''
), False)

# COMMAND ----------

# MAGIC %md
# MAGIC US Holidays in 2019 (the default ingestion window is Jan-Feb 2019 — extend `MONTHS` in the Data
# MAGIC Ingestion notebook to cover more of the calendar)
# MAGIC
# MAGIC ```
# MAGIC New Year's Day                      Tue, 1 Jan 2019
# MAGIC Martin Luther King Jr. Day          Mon, 21 Jan 2019
# MAGIC Presidents' Day                     Mon, 18 Feb 2019
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Taxi trip pickups by taxi zone

# COMMAND ----------

if zones_available:
    pickup_by_zone = spark.sql(
        '''
        SELECT
           tg.zone as Zone
          ,t.pickup_location_id as pickup_location_id
          ,tg.the_geom as geometry
          ,t.trip_count
        FROM
        taxiGeom tg INNER JOIN (
            SELECT
                pickup_location_id,
                COUNT(pickup_location_id) as trip_count
            FROM nyc_yellow_trips
            GROUP BY pickup_location_id
        ) t
        ON t.pickup_location_id = tg.LocationID
        ORDER BY t.pickup_location_id
        '''
    ).toPandas()

    if pickup_by_zone.empty:
        print("No zone-level pickup data available (the trips table has no location IDs) — skipping map.")
    else:
        pickup_by_zone_gs = gpd.GeoSeries.from_wkt(pickup_by_zone['geometry'])
        pickup_by_zone_gdf = gpd.GeoDataFrame(pickup_by_zone, geometry=pickup_by_zone_gs, crs="EPSG:4326")

        m = pickup_by_zone_gdf.explore(
            column="trip_count",
            tooltip=["Zone", "trip_count"],
            legend=True,
            legend_kwds=dict(colorbar=False),
            popup=True,
            tiles="CartoDB positron",
            cmap='YlOrBr',
            scheme='quantiles',
        )
        display(m)
else:
    print("Zone reference tables not available — skipping pickup-by-zone map.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Taxi trip dropoffs by taxi zone

# COMMAND ----------

if zones_available:
    dropoff_by_zone = spark.sql(
        '''
        SELECT
         tg.zone as Zone
         ,t.dropoff_location_id as dropoff_location_id
        ,tg.the_geom as geometry
        ,t.trip_count
        FROM
        taxiGeom tg INNER JOIN (
            SELECT
                dropoff_location_id,
                COUNT(dropoff_location_id) as trip_count
            FROM nyc_yellow_trips
            GROUP BY dropoff_location_id
        ) t
        ON t.dropoff_location_id = tg.LocationID
        ORDER BY t.dropoff_location_id
        '''
    ).toPandas()

    if dropoff_by_zone.empty:
        print("No zone-level dropoff data available (the trips table has no location IDs) — skipping map.")
    else:
        dropoff_by_zone_gs = gpd.GeoSeries.from_wkt(dropoff_by_zone['geometry'])
        dropoff_by_zone_gdf = gpd.GeoDataFrame(dropoff_by_zone, geometry=dropoff_by_zone_gs, crs="EPSG:4326")

        m = dropoff_by_zone_gdf.explore(
            column="trip_count",
            tooltip=["Zone", "trip_count"],
            legend=True,
            legend_kwds=dict(colorbar=False),
            popup=True,
            tiles="CartoDB positron",
            cmap='YlOrBr',
            scheme='quantiles',
        )
        display(m)
else:
    print("Zone reference tables not available — skipping dropoff-by-zone map.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Taxi trip pickups by taxi zone over time

# COMMAND ----------

if zones_available:
    display(spark.sql(
        '''
        SELECT
           tg.zone as Zone
          ,t.pickup_location_id as pickup_location_id
          ,tg.the_geom as geometry
          ,t.trip_count
          ,t.trip_date
        FROM
        taxiGeom tg INNER JOIN (
            SELECT
                pickup_location_id
                ,to_date(pickup_datetime) trip_date
                ,COUNT(pickup_location_id) as trip_count
            FROM nyc_yellow_trips
            WHERE pickup_datetime BETWEEN "2019-01-01" AND "2019-03-01"
            GROUP BY
                to_date(pickup_datetime)
                ,pickup_location_id
        ) t
        ON t.pickup_location_id = tg.LocationID
        ORDER BY t.pickup_location_id
        '''
    ))
else:
    print("Zone reference tables not available — skipping pickup-by-zone-over-time query.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trip count by passenger count

# COMMAND ----------

display(
    df_yellow_18_19
    .groupBy(col("passenger_count").alias("passenger_count"))
    .agg(count("passenger_count").alias("trip count"))
    .orderBy(col('passenger_count'))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trip count by weekday

# COMMAND ----------

display(
    df_yellow_18_19
    .groupBy(date_format(to_date("pickup_datetime"), "EEEE").alias("day"), dayofweek(to_date("pickup_datetime")).alias("day_number"))
    .agg(count("pickup_datetime").alias("trip count"))
    .orderBy(col("day_number"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Taxi trip pickups by hour

# COMMAND ----------

display(
    df_yellow_18_19
    .groupBy(hour("pickup_datetime").alias("hour"))
    .agg(count("pickup_datetime").alias("pickups"))
    .orderBy(col("hour"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Taxi trip dropoffs by hour

# COMMAND ----------

display(
    df_yellow_18_19
    .groupBy(hour("dropoff_datetime").alias("hour"))
    .agg(count("dropoff_datetime").alias("dropoffs"))
    .orderBy(col("hour"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Taxi trip origin destination heatmap

# COMMAND ----------

if zones_available:
    pickup_dropoff_heatmap = spark.sql('''
    SELECT
       pu.Zone AS pickup_location
      ,do.Zone AS dropoff_location
      ,t.trip_count
    FROM
    (
        (
        SELECT
           pickup_location_id AS pickup_location
          ,dropoff_location_id AS dropoff_location
          ,count(pickup_location_id) AS trip_count
        FROM nyc_yellow_trips
            WHERE
            pickup_location_id < 264
            AND
            dropoff_location_id < 264
        GROUP BY
            pickup_location_id
            ,dropoff_location_id
        ) t
        LEFT JOIN taxiZones pu ON t.pickup_location=pu.LocationID
        LEFT JOIN taxiZones do ON t.dropoff_location=do.LocationID
    )
    ORDER BY
        t.trip_count DESC
        ,pu.Borough DESC
        ,do.Borough DESC
    LIMIT 100
        '''
    ).toPandas()

    if pickup_dropoff_heatmap.empty:
        print("No zone-level origin/destination data available — skipping heatmap.")
    else:
        pickup_dropoff_heatmap_pivot = pd.pivot_table(pickup_dropoff_heatmap, columns='dropoff_location', index='pickup_location')
        pickup_dropoff_heatmap_pivot[pickup_dropoff_heatmap_pivot < 1000] = np.nan

        sns.set(rc={'figure.figsize': (15, 15)})
        sns.heatmap(pickup_dropoff_heatmap_pivot, cmap='rocket_r')
        plt.show()
else:
    print("Zone reference tables not available — skipping origin/destination heatmap.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trip duration by pickup hour

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   hour(pickup_datetime) AS pickup_hour,
# MAGIC   AVG(
# MAGIC     (bigint(to_timestamp(dropoff_datetime))) - (bigint(to_timestamp(pickup_datetime)))
# MAGIC   ) AS trip_duration
# MAGIC FROM
# MAGIC   nyc_yellow_trips
# MAGIC GROUP BY
# MAGIC   hour(pickup_datetime)
# MAGIC ORDER BY
# MAGIC   pickup_hour

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trip duration by dropoff hour

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   hour(dropoff_datetime) AS dropoff_hour,
# MAGIC   AVG(
# MAGIC     (bigint(to_timestamp(dropoff_datetime))) - (bigint(to_timestamp(pickup_datetime)))
# MAGIC   ) AS trip_duration
# MAGIC FROM
# MAGIC   nyc_yellow_trips
# MAGIC GROUP BY
# MAGIC   hour(dropoff_datetime)
# MAGIC ORDER BY
# MAGIC   dropoff_hour

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trip duration by week day

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   date_format(pickup_datetime, "EEEE") AS weekday,
# MAGIC   dayofweek(pickup_datetime) as day_number,
# MAGIC   AVG(
# MAGIC     (bigint(to_timestamp(dropoff_datetime))) - (bigint(to_timestamp(pickup_datetime)))
# MAGIC   ) AS trip_duration
# MAGIC FROM
# MAGIC   nyc_yellow_trips
# MAGIC GROUP BY
# MAGIC   date_format(pickup_datetime, "EEEE"),
# MAGIC   dayofweek(pickup_datetime)
# MAGIC ORDER BY
# MAGIC   day_number

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trip duration by passenger count

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   passenger_count,
# MAGIC   AVG(
# MAGIC     (bigint(to_timestamp(dropoff_datetime))) - (bigint(to_timestamp(pickup_datetime)))
# MAGIC   ) AS trip_duration
# MAGIC FROM
# MAGIC   nyc_yellow_trips
# MAGIC GROUP BY
# MAGIC   passenger_count
# MAGIC HAVING
# MAGIC   passenger_count < 15
# MAGIC ORDER BY
# MAGIC   passenger_count

# COMMAND ----------

# MAGIC %md
# MAGIC ## Average trip fare over time

# COMMAND ----------

display(spark.sql(
    '''
    SELECT
       AVG(total_amount) avg_total_amount
      ,to_date(pickup_datetime) date
    FROM nyc_yellow_trips WHERE total_amount >= 0
    GROUP BY
       to_date(pickup_datetime)
    ORDER BY
      to_date(date)
    '''
), False)

# COMMAND ----------

# MAGIC %md
# MAGIC [Price Hike](https://www.ny1.com/nyc/all-boroughs/news/2019/02/03/congestion-pricing-surcharge-in-nyc-goes-into-effect)
# MAGIC (only visible if your ingestion window includes early Feb 2019 and your Data Ingestion run used the
# MAGIC real TLC source rather than the `samples.nyctaxi.trips` fallback, since the fallback approximates
# MAGIC `total_amount` from `fare_amount` alone).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Average tip amount over time

# COMMAND ----------

display(spark.sql(
    '''
    SELECT
       AVG(tip_amount) avg_tip_amount
      ,to_date(pickup_datetime) date
    FROM nyc_yellow_trips WHERE tip_amount >= 0
    GROUP BY
       to_date(pickup_datetime)
    ORDER BY
      to_date(date)
    '''
), False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tip to Total Amount percentage

# COMMAND ----------

display(spark.sql(
    '''
    SELECT
       (AVG(tip_amount) / AVG(total_amount-tip_amount))* 100 tip_percentage_of_total_amount
      ,to_date(pickup_datetime) date
    FROM nyc_yellow_trips WHERE tip_amount >= 0 AND total_amount >= 0
    GROUP BY
       to_date(pickup_datetime)
    ORDER BY
      to_date(date)
    '''
), False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Average trip distance over time

# COMMAND ----------

display(spark.sql(
    '''
    SELECT
       AVG(trip_distance) avg_trip_distance
      ,to_date(pickup_datetime) date
    FROM nyc_yellow_trips
    GROUP BY
       to_date(pickup_datetime)
    ORDER BY
      to_date(date)
    '''
), False)
