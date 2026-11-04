import pymysql

connection = pymysql.connect(
    host="mysql-2f07378e-hoorab-finance.l.aivencloud.com",
    port=16301,
    user="avnadmin",
    password="APNA_ASLI_PASSWORD_YAHAN_LIKHO",
    database="defaultdb"
)

cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS Users (
  UserID INT AUTO_INCREMENT PRIMARY KEY,
  FullName VARCHAR(100) NOT NULL,
  Email VARCHAR(255) NOT NULL UNIQUE,
  PasswordHash VARCHAR(255) NOT NULL,
  CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Budgets (
  BudgetID INT AUTO_INCREMENT PRIMARY KEY,
  UserID INT NOT NULL,
  MonthlyBudget DECIMAL(12,2) NOT NULL,
  `Month` INT NOT NULL,
  `Year` INT NOT NULL,
  CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (UserID) REFERENCES Users(UserID)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Transactions (
  TransactionID INT AUTO_INCREMENT PRIMARY KEY,
  UserID INT NOT NULL,
  TransactionType VARCHAR(20) NOT NULL,
  Amount DECIMAL(12,2) NOT NULL,
  Category VARCHAR(100) NOT NULL,
  Description TEXT,
  TransactionDate DATE NOT NULL,
  FOREIGN KEY (UserID) REFERENCES Users(UserID)
)
""")

connection.commit()
print("TABLES BAN GAYE!")
cursor.close()
connection.close()