**Delivery Performance & Returns Analysis**


**Project Overview**

Business Question: How well are we delivering, and what causes returns?

This project uses Python to analyze delivery performance and customer returns using seven synthetic retail/e-commerce datasets. The analysis evaluates shipment statuses, delivery lead times, courier performance, return reasons, and category-level return rates.

Technologies Used: Python, Jupyter Notebook, Pandas, NumPy, Matplotlib, Seaborn, Streamlit, and Plotly.


**Submission Files**

The project includes the following required deliverables:

README.md – Project documentation and execution instructions.

Executive Summary.txt – Summary of findings and recommendations.

delivery_returns_analysis.ipynb – Python analysis notebook.

outputs/customers_clean.csv – Cleaned customer dataset.

outputs/products_clean.csv – Cleaned product dataset.

charts/ – Six exported PNG visualizations.

Additional files include the Python analysis script, cleaned transaction datasets, interactive dashboard, and analyst report.


**Data Analysis & Methodology**

The analysis uses seven CSV files: Customers, Products, Orders, Order Items, Payments, Shipments, and Returns.

Data cleaning includes standardizing product categories, removing exact duplicates and repeated primary keys, handling missing values, parsing mixed date formats, converting currency strings to numeric values, and validating relationships between datasets.


**Key Metrics**

Delivery Lead Time: Delivered Date minus Ship Date, measured in days.

Delivery Status Rate: Shipments in each status divided by total shipments, multiplied by 100.

Return Rate: Unique orders with recorded returns divided by total unique orders, multiplied by 100.

Courier Performance: Average delivery lead time, delivery percentage, and return rate by courier.

Category Return Rate: Unique returned orders containing a category divided by total unique orders containing that category, multiplied by 100.

Only delivered shipments with valid dates are included in lead-time calculations. Invalid quantities and unmatched product records are excluded from relevant category calculations.


**Six Data Visualizations**

Delivery Lead Time Distribution – Distribution of completed delivery durations.

Courier Performance Comparison – Average delivery lead time by courier.

Top Reported Return Reasons – Frequency of recorded return reasons.

Return Rate by Product Category – Comparison of order return rates across product categories.

Shipment Status Breakdown – Delivered, In Transit, Lost, and Returned to Sender shipments.

Return Rate by Courier – Percentage of orders with returns by courier.

All six charts are exported as PNG images.


**Executive Summary**

The analysis covers **15,000** unique orders and 15,000 shipments.

**77.87%** of shipments are marked Delivered.

**17.96%** are marked In Transit.

**1.07%** are marked Lost.

**3.10%** are marked Returned to Sender.

Average completed delivery lead time is **4.00** days.

Overall order return rate is **8.00%**.

Changed mind is the leading recorded return reason, with **182 cases**.

**Home & Kitchen** has the highest category-associated return rate at **8.65%**.

**J&T** has the lowest observed delivery completion percentage at **76.59%**.

**Recommendation 1**: Investigate courier delivery exceptions and operational bottlenecks.

**Recommendation 2**: Improve product information and investigate the underlying reasons for returns.


**Running the Project**

Project directory: C:\Users\Ronn\DataGripProjects

CSV source directory: C:\Users\Ronn\Downloads

Save the Python scripts and Jupyter Notebook in the project directory.

Ensure all seven CSV datasets are available in Downloads or the project's data folder.

Open delivery_returns_analysis.ipynb using Jupyter Notebook.

Install required libraries if they are missing.

Select Kernel → Restart & Run All.

Review the generated results in the outputs and charts folders.

Save the notebook with its executed outputs.


**Interactive Dashboard**

To run the Streamlit dashboard, open PowerShell and execute:

cd "C:\Users\Ronn\DataGripProjects"
python -m pip install -r requirements_dashboard.txt
python -m streamlit run dashboard.py

The dashboard provides interactive filters for couriers, product categories, and shipment statuses, together with PDF export functionality when pdf_export.py is installed.

Limitations

This project uses synthetic training data. The findings identify recorded return reasons and statistical patterns, not proven causal relationships. An on-time delivery percentage cannot be calculated reliably without promised delivery dates."# python_data_analysis" 
