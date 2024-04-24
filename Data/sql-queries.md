
# SQL Queries for the Northwind database

## Query 1: Retrieve all data from the "Customers" table
```sql
-- This query selects all columns and all records from the Customers table
SELECT * FROM Customers;
```

## Query 2: Retrieve specific columns from the "Products" table
```sql
-- This query retrieves only the ProductName and UnitPrice columns from the Products table
SELECT ProductName, UnitPrice FROM Products;
```

## Query 3: Sort results by a specific column
```sql
-- This query retrieves all products, sorted by UnitPrice in ascending order
SELECT * FROM Products
ORDER BY UnitPrice ASC;
```

## Query 4: Filter results using a WHERE clause
```sql
-- This query selects all products that have a UnitPrice greater than 20
SELECT * FROM Products
WHERE UnitPrice > 20;
```

## Query 5: Count the number of customers in a specific country
```sql
-- This query counts the number of customers located in Germany
SELECT COUNT(*) AS NumberOfCustomers FROM Customers
WHERE Country = 'Germany';
```

## Query 6: Use JOIN to combine rows from two tables
```sql
-- This query joins Orders and Customers tables to list orders along with customer names
SELECT Orders.OrderID, Customers.ContactName
FROM Orders
JOIN Customers ON Orders.CustomerID = Customers.CustomerID;
```

## Query 7: Group results and use aggregate functions
```sql
-- This query groups products by CategoryID and calculates the average UnitPrice for each category
SELECT CategoryID, AVG(UnitPrice) AS AveragePrice
FROM Products
GROUP BY CategoryID;
```

## Query 8: Filter groups with HAVING
```sql
-- This query finds categories that have an average UnitPrice of more than 30
SELECT CategoryID, AVG(UnitPrice) AS AveragePrice
FROM Products
GROUP BY CategoryID
HAVING AVG(UnitPrice) > 30;
```

## Query 9: Use subqueries in the SELECT clause
```sql
-- This query lists customers and calculates the total number of orders they have placed
SELECT CustomerID, 
       (SELECT COUNT(*) FROM Orders WHERE Orders.CustomerID = Customers.CustomerID) AS NumberOfOrders
FROM Customers;
```

## Query 10: Use multiple JOINs and an aggregate function
```sql
-- This query joins Orders, Order Details, and Products tables to calculate the total order amount for each order
SELECT Orders.OrderID, SUM(Order_Details.UnitPrice * Order_Details.Quantity) AS TotalAmount
FROM Orders
JOIN Order_Details ON Orders.OrderID = Order_Details.OrderID
JOIN Products ON Order_Details.ProductID = Products.ProductID
GROUP BY Orders.OrderID;
```

<!-- Additional queries -->

### Query 1: List Top 5 Best-Selling Products
```sql
-- This query finds the top 5 best-selling products based on total quantity sold
SELECT TOP 5 Products.ProductName, SUM(Order_Details.Quantity) AS TotalQuantitySold
FROM Products
JOIN Order_Details ON Products.ProductID = Order_Details.ProductID
GROUP BY Products.ProductName
ORDER BY TotalQuantitySold DESC;
```

### Query 2: Sales Performance by Year
```sql
-- This query calculates the total sales for each year
SELECT YEAR(Orders.OrderDate) AS OrderYear, SUM(Order_Details.UnitPrice * Order_Details.Quantity) AS TotalSales
FROM Orders
JOIN Order_Details ON Orders.OrderID = Order_Details.OrderID
GROUP BY YEAR(Orders.OrderDate);
```

### Query 3: Customer Retention Analysis
```sql
-- This query lists customers who have placed more than 5 orders to identify repeat customers
SELECT Customers.CustomerID, Customers.CompanyName, COUNT(Orders.OrderID) AS NumberOfOrders
FROM Customers
JOIN Orders ON Customers.CustomerID = Orders.CustomerID
GROUP BY Customers.CustomerID, Customers.CompanyName
HAVING COUNT(Orders.OrderID) > 5;
```

### Query 4: Identify Slow-moving Inventory
```sql
-- This query finds products that have not been ordered in the last 12 months
SELECT ProductName
FROM Products
LEFT JOIN Orders ON Products.ProductID = Orders.ProductID
WHERE Orders.OrderDate < DATEADD(year, -1, GETDATE())
GROUP BY ProductName;
```

### Query 5: Sales by Region
```sql
-- This query summarizes total sales by region
SELECT Region, SUM(Order_Details.UnitPrice * Order_Details.Quantity) AS TotalSales
FROM Orders
JOIN Order_Details ON Orders.OrderID = Order_Details.OrderID
JOIN Employees ON Orders.EmployeeID = Employees.EmployeeID
GROUP BY Region;
```

### Query 6: Profit Margin Per Product
```sql
-- This query calculates the profit margin per product
SELECT ProductName, (UnitPrice - Cost) AS ProfitMargin
FROM Products
WHERE Cost IS NOT NULL;  -- Assuming the Cost field exists and is populated
```

### Query 7: Customer Lifetime Value (CLV)
```sql
-- This query estimates the lifetime value of customers
SELECT Customers.CustomerID, Customers.CompanyName,
       SUM(Order_Details.UnitPrice * Order_Details.Quantity * (1 - Order_Details.Discount)) AS LifetimeValue
FROM Customers
JOIN Orders ON Customers.CustomerID = Orders.CustomerID
JOIN Order_Details ON Orders.OrderID = Order_Details.OrderID
GROUP BY Customers.CustomerID, Customers.CompanyName;
```

### Query 8: Product Reorder Recommendations
```sql
-- This query recommends products to reorder based on stock level and order frequency
SELECT ProductName, UnitsInStock, ReorderLevel
FROM Products
WHERE UnitsInStock <= ReorderLevel AND Discontinued = 0
ORDER BY ProductName;
```

### Query 9: Sales Trends for High-Value Customers
```sql
-- This query analyzes sales trends over time for high-value customers (top 10% by sales)
SELECT Customers.CustomerID, Customers.CompanyName, YEAR(Orders.OrderDate) AS Year, MONTH(Orders.OrderDate) AS Month, 
       SUM(Order_Details.UnitPrice * Order_Details.Quantity * (1 - Order_Details.Discount)) AS MonthlySales
FROM Customers
JOIN Orders ON Customers.CustomerID = Orders.CustomerID
JOIN Order_Details ON Orders.OrderID = Order_Details.OrderID
GROUP BY Customers.CustomerID, Customers.CompanyName, YEAR(Orders.OrderDate), MONTH(Orders.OrderDate)
ORDER BY Customers.CustomerID, Year, Month;
```

### Query 10: Supplier Performance Evaluation
```sql
-- This query evaluates supplier performance based on delivery time and order completeness
SELECT Suppliers.SupplierID, Suppliers.CompanyName, AVG(DATEDIFF(day, Orders.OrderDate, Orders.ShippedDate)) AS AverageDeliveryTime, 
       COUNT(Orders.OrderID) AS TotalOrders
FROM Suppliers
JOIN Products ON Suppliers.SupplierID = Products.SupplierID
JOIN Order_Details ON Products.ProductID = Order_Details.ProductID
JOIN Orders ON Order_Details.OrderID = Orders.OrderID
GROUP BY Suppliers.SupplierID, Suppliers.CompanyName;
```
