# %% [markdown]
# # Fabric IQ — Data Ingestion & Analysis Notebook
#
# This notebook processes the sample retail data loaded into the Lakehouse
# and creates derived tables for the Fabric Agent to query.
#
# **Tables used:**
# - `sales_transactions` — 1,000 synthetic sales records
# - `products` — 50 product dimension records
#
# **Tables created:**
# - `sales_summary` — Daily aggregated sales by category and region
# - `top_products` — Top products ranked by revenue

# %% [markdown]
# ## 1. Load Raw Data from Lakehouse

# %%
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.getOrCreate()

# Load tables from the default Lakehouse
sales_df = spark.sql("SELECT * FROM sales_transactions")
products_df = spark.sql("SELECT * FROM products")

print(f"Sales records: {sales_df.count()}")
print(f"Products: {products_df.count()}")

sales_df.printSchema()

# %% [markdown]
# ## 2. Explore Sales Data

# %%
# Basic statistics
sales_df.describe("quantity", "unit_price", "total").show()

# Sales by category
sales_by_category = (
    sales_df
    .groupBy("category")
    .agg(
        F.count("*").alias("transaction_count"),
        F.sum("total").alias("total_revenue"),
        F.avg("total").alias("avg_order_value"),
        F.sum("quantity").alias("total_units"),
    )
    .orderBy(F.desc("total_revenue"))
)

sales_by_category.show()

# %% [markdown]
# ## 3. Create Daily Sales Summary

# %%
# Aggregate sales by date, category, and region
daily_summary = (
    sales_df
    .groupBy("date", "category", "region")
    .agg(
        F.count("*").alias("transactions"),
        F.sum("quantity").alias("units_sold"),
        F.sum("total").alias("revenue"),
        F.avg("unit_price").alias("avg_price"),
    )
    .orderBy("date", "category")
)

# Write as a managed Delta table
daily_summary.write.mode("overwrite").format("delta").saveAsTable("sales_summary")
print(f"Created sales_summary table: {daily_summary.count()} rows")

# %% [markdown]
# ## 4. Create Top Products Table

# %%
# Rank products by total revenue
top_products = (
    sales_df
    .groupBy("product", "category")
    .agg(
        F.sum("total").alias("total_revenue"),
        F.sum("quantity").alias("total_units"),
        F.count("*").alias("order_count"),
        F.avg("unit_price").alias("avg_selling_price"),
    )
    .orderBy(F.desc("total_revenue"))
)

# Add rank column
from pyspark.sql.window import Window

rank_window = Window.orderBy(F.desc("total_revenue"))
top_products = top_products.withColumn("revenue_rank", F.row_number().over(rank_window))

# Write as a managed Delta table
top_products.write.mode("overwrite").format("delta").saveAsTable("top_products")
print(f"Created top_products table: {top_products.count()} rows")

# %% [markdown]
# ## 5. Customer Segment Analysis

# %%
# Revenue by customer segment
segment_analysis = (
    sales_df
    .groupBy("customer_segment")
    .agg(
        F.count("*").alias("transactions"),
        F.sum("total").alias("revenue"),
        F.avg("total").alias("avg_order_value"),
        F.countDistinct("product").alias("unique_products"),
    )
    .orderBy(
        F.when(F.col("customer_segment") == "platinum", 1)
        .when(F.col("customer_segment") == "gold", 2)
        .when(F.col("customer_segment") == "silver", 3)
        .otherwise(4)
    )
)

segment_analysis.show()

# %% [markdown]
# ## 6. Regional Performance

# %%
# Revenue by region with category breakdown
regional = (
    sales_df
    .groupBy("region", "category")
    .agg(
        F.sum("total").alias("revenue"),
        F.count("*").alias("orders"),
    )
    .orderBy("region", F.desc("revenue"))
)

regional.show(20)

# %% [markdown]
# ## 7. Verify Created Tables

# %%
print("=== Sales Summary (sample) ===")
spark.sql("SELECT * FROM sales_summary LIMIT 5").show()

print("=== Top Products (top 10) ===")
spark.sql("SELECT revenue_rank, product, category, total_revenue, total_units FROM top_products LIMIT 10").show()

print("Done — Lakehouse tables are ready for the Fabric Agent.")
