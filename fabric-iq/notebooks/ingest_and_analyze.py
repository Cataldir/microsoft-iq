# %% [markdown]
# # Fabric IQ — E-Commerce Analytics Notebook
#
# This notebook processes Brazilian E-Commerce data (Olist / Kaggle) synced from
# PostgreSQL into the Lakehouse and creates derived analytical tables.
#
# **Source tables** (loaded via `scripts/sync_to_fabric.py`):
# - `orders` — 99K+ order records with status and timestamps
# - `order_items` — Line items with product, seller, price, freight
# - `order_payments` — Payment records with type and installments
# - `agent_insights` — Foundry agent Q&A interactions (transactional → analytical bridge)
#
# **Derived tables created:**
# - `sales_summary` — Daily/monthly revenue aggregation by category and region
# - `delivery_performance` — Delivery time analysis and SLA adherence
# - `payment_analysis` — Payment method distribution and installment patterns
# - `agent_interaction_stats` — Agent usage patterns (closes the analytical loop)

# %% [markdown]
# ## 1. Load Raw Data from Lakehouse

# %%
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, TimestampType

spark = SparkSession.builder.getOrCreate()

orders_df = spark.sql("SELECT * FROM orders")
items_df = spark.sql("SELECT * FROM order_items")
payments_df = spark.sql("SELECT * FROM order_payments")

print(f"Orders: {orders_df.count()}")
print(f"Order items: {items_df.count()}")
print(f"Payments: {payments_df.count()}")

orders_df.printSchema()

# %%
# Check if agent insights table exists
try:
    insights_df = spark.sql("SELECT * FROM agent_insights")
    print(f"Agent insights: {insights_df.count()}")
    has_insights = True
except Exception:
    print("No agent_insights table yet (will be created after Foundry agent interactions)")
    has_insights = False

# %% [markdown]
# ## 2. Revenue Summary by Date and Status

# %%
# Cast price columns to numeric
items_cast = items_df.withColumn("price", F.col("price").cast(DoubleType())) \
                     .withColumn("freight_value", F.col("freight_value").cast(DoubleType()))

orders_cast = orders_df.withColumn(
    "purchase_date", F.to_date(F.col("order_purchase_timestamp"))
).withColumn(
    "purchase_month", F.date_format(F.col("order_purchase_timestamp"), "yyyy-MM")
)

# Join orders with items for revenue analysis
order_revenue = orders_cast.join(items_cast, on="order_id", how="inner")

# Daily revenue summary
daily_summary = (
    order_revenue
    .groupBy("purchase_date", "order_status")
    .agg(
        F.count("*").alias("order_count"),
        F.sum("price").alias("total_revenue"),
        F.sum("freight_value").alias("total_freight"),
        F.avg("price").alias("avg_item_price"),
    )
    .orderBy("purchase_date")
)

daily_summary.write.mode("overwrite").format("delta").saveAsTable("sales_summary")
print(f"Created sales_summary: {daily_summary.count()} rows")

# %% [markdown]
# ## 3. Delivery Performance Analysis

# %%
delivery_df = orders_df.filter(F.col("order_status") == "delivered")

delivery_perf = delivery_df.withColumn(
    "delivery_days", F.datediff(
        F.col("order_delivered_timestamp").cast(TimestampType()),
        F.col("order_purchase_timestamp").cast(TimestampType()),
    )
).withColumn(
    "estimated_days", F.datediff(
        F.col("order_estimated_delivery").cast(TimestampType()),
        F.col("order_purchase_timestamp").cast(TimestampType()),
    )
).withColumn(
    "on_time", F.when(
        F.col("order_delivered_timestamp") <= F.col("order_estimated_delivery"), True
    ).otherwise(False)
)

delivery_stats = (
    delivery_perf
    .groupBy(F.date_format(F.col("order_purchase_timestamp"), "yyyy-MM").alias("month"))
    .agg(
        F.count("*").alias("deliveries"),
        F.avg("delivery_days").alias("avg_delivery_days"),
        F.avg("estimated_days").alias("avg_estimated_days"),
        F.sum(F.when(F.col("on_time"), 1).otherwise(0)).alias("on_time_count"),
    )
    .withColumn("on_time_pct", F.round(F.col("on_time_count") / F.col("deliveries") * 100, 1))
    .orderBy("month")
)

delivery_stats.write.mode("overwrite").format("delta").saveAsTable("delivery_performance")
print(f"Created delivery_performance: {delivery_stats.count()} rows")

# %% [markdown]
# ## 4. Payment Method Analysis

# %%
payments_cast = payments_df \
    .withColumn("payment_value", F.col("payment_value").cast(DoubleType())) \
    .withColumn("payment_installments", F.col("payment_installments").cast(IntegerType()))

payment_analysis = (
    payments_cast
    .groupBy("payment_type")
    .agg(
        F.count("*").alias("transaction_count"),
        F.sum("payment_value").alias("total_value"),
        F.avg("payment_value").alias("avg_value"),
        F.avg("payment_installments").alias("avg_installments"),
        F.max("payment_installments").alias("max_installments"),
    )
    .orderBy(F.desc("total_value"))
)

payment_analysis.write.mode("overwrite").format("delta").saveAsTable("payment_analysis")
print(f"Created payment_analysis: {payment_analysis.count()} rows")
payment_analysis.show()

# %% [markdown]
# ## 5. Top Sellers and Products

# %%
top_sellers = (
    items_cast
    .groupBy("seller_id")
    .agg(
        F.count("*").alias("items_sold"),
        F.sum("price").alias("total_revenue"),
        F.countDistinct("product_id").alias("unique_products"),
        F.countDistinct("order_id").alias("unique_orders"),
    )
    .orderBy(F.desc("total_revenue"))
)

top_products = (
    items_cast
    .groupBy("product_id")
    .agg(
        F.count("*").alias("times_sold"),
        F.sum("price").alias("total_revenue"),
        F.avg("price").alias("avg_price"),
    )
    .orderBy(F.desc("total_revenue"))
)

from pyspark.sql.window import Window
rank_window = Window.orderBy(F.desc("total_revenue"))
top_products = top_products.withColumn("revenue_rank", F.row_number().over(rank_window))

top_products.write.mode("overwrite").format("delta").saveAsTable("top_products")
top_sellers.write.mode("overwrite").format("delta").saveAsTable("top_sellers")
print(f"Created top_products: {top_products.count()} rows")
print(f"Created top_sellers: {top_sellers.count()} rows")

# %% [markdown]
# ## 6. Agent Interaction Stats (Closing the Loop)

# %%
if has_insights:
    agent_stats = (
        insights_df
        .groupBy("agent_name")
        .agg(
            F.count("*").alias("total_queries"),
            F.min("created_at").alias("first_query"),
            F.max("created_at").alias("last_query"),
        )
    )
    agent_stats.write.mode("overwrite").format("delta").saveAsTable("agent_interaction_stats")
    print(f"Created agent_interaction_stats: {agent_stats.count()} rows")
else:
    print("Skipped agent_interaction_stats — no insights data yet")

# %% [markdown]
# ## 7. Verify All Tables

# %%
print("=== Sales Summary (sample) ===")
spark.sql("SELECT * FROM sales_summary ORDER BY purchase_date DESC LIMIT 5").show()

print("=== Delivery Performance ===")
spark.sql("SELECT * FROM delivery_performance ORDER BY month DESC LIMIT 5").show()

print("=== Payment Analysis ===")
spark.sql("SELECT * FROM payment_analysis").show()

print("=== Top Products (top 10) ===")
spark.sql("SELECT revenue_rank, product_id, total_revenue, times_sold FROM top_products LIMIT 10").show()

print("Done — Lakehouse tables ready for the Fabric Agent.")
