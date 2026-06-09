-- ============================================================
-- Reset stock schema data and create 3-stock group objects.
--
-- Step 1 : clears all rows from existing tables (FK-safe order)
--          and reseeds identity columns back to 1.
-- Step 2 : creates the StockGroup table (skipped if it already
--          exists from a previous run).
-- Step 3 : drops and recreates Group_Insert / Group_List /
--          Group_Delete stored procedures.
--
-- Run against the target SQL Server database (stocks schema).
-- ============================================================


-- ============================================================
-- 1. Clear existing data
-- ============================================================

PRINT 'Clearing existing data...';

-- Most-derived children first so FK constraints are never violated.

IF OBJECT_ID('stocks.StockGroup', 'U') IS NOT NULL
BEGIN
    DELETE FROM stocks.StockGroup;
    PRINT '  stocks.StockGroup cleared';
END

IF OBJECT_ID('stocks.Pair', 'U') IS NOT NULL
BEGIN
    DELETE FROM stocks.Pair;
    PRINT '  stocks.Pair cleared';
END

IF OBJECT_ID('stocks.StockPrice', 'U') IS NOT NULL
BEGIN
    DELETE FROM stocks.StockPrice;
    PRINT '  stocks.StockPrice cleared';
END

DELETE FROM stocks.Stock;
PRINT '  stocks.Stock cleared';

DELETE FROM stocks.Exchange;
PRINT '  stocks.Exchange cleared';

DELETE FROM stocks.Country;
PRINT '  stocks.Country cleared';

-- Reseed identities so the first new row gets ID = 1.
DBCC CHECKIDENT ('stocks.Country',  RESEED, 0) WITH NO_INFOMSGS;
DBCC CHECKIDENT ('stocks.Exchange', RESEED, 0) WITH NO_INFOMSGS;
DBCC CHECKIDENT ('stocks.Stock',    RESEED, 0) WITH NO_INFOMSGS;

IF OBJECT_ID('stocks.StockPrice', 'U') IS NOT NULL
    DBCC CHECKIDENT ('stocks.StockPrice', RESEED, 0) WITH NO_INFOMSGS;

IF OBJECT_ID('stocks.StockGroup', 'U') IS NOT NULL
    DBCC CHECKIDENT ('stocks.StockGroup', RESEED, 0) WITH NO_INFOMSGS;

PRINT 'Data cleared and identity seeds reset.';
GO


-- ============================================================
-- 2. StockGroup table
-- ============================================================

IF OBJECT_ID('stocks.StockGroup', 'U') IS NULL
BEGIN
    CREATE TABLE stocks.StockGroup
    (
        GroupID   INT            NOT NULL IDENTITY(1,1)
                                 CONSTRAINT PK_StockGroup PRIMARY KEY,
        GroupName NVARCHAR(200)  NOT NULL,
        Stock1ID  INT            NOT NULL
                                 CONSTRAINT FK_StockGroup_S1
                                 REFERENCES stocks.Stock(StockID),
        Stock2ID  INT            NOT NULL
                                 CONSTRAINT FK_StockGroup_S2
                                 REFERENCES stocks.Stock(StockID),
        Stock3ID  INT            NOT NULL
                                 CONSTRAINT FK_StockGroup_S3
                                 REFERENCES stocks.Stock(StockID),
        CreatedAt DATETIME2      NOT NULL
                                 CONSTRAINT DF_StockGroup_Created
                                 DEFAULT GETDATE()
    );
    PRINT 'stocks.StockGroup created.';
END
ELSE
    PRINT 'stocks.StockGroup already exists — skipped.';
GO


-- ============================================================
-- 3. Stored procedures (drop-and-recreate for idempotency)
-- ============================================================

-- ── Group_Insert ─────────────────────────────────────────────
IF OBJECT_ID('stocks.Group_Insert', 'P') IS NOT NULL
    DROP PROCEDURE stocks.Group_Insert;
GO
CREATE PROCEDURE stocks.Group_Insert
    @GroupName NVARCHAR(200),
    @Stock1ID  INT,
    @Stock2ID  INT,
    @Stock3ID  INT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO stocks.StockGroup (GroupName, Stock1ID, Stock2ID, Stock3ID)
    VALUES (@GroupName, @Stock1ID, @Stock2ID, @Stock3ID);

    SELECT SCOPE_IDENTITY() AS GroupID;
END
GO

-- ── Group_List ───────────────────────────────────────────────
IF OBJECT_ID('stocks.Group_List', 'P') IS NOT NULL
    DROP PROCEDURE stocks.Group_List;
GO
CREATE PROCEDURE stocks.Group_List
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        g.GroupID,
        g.GroupName,

        g.Stock1ID,
        s1.Ticker     AS Stock1Ticker,
        s1.FullName   AS Stock1FullName,
        e1.Name       AS Exchange1Name,
        e1.Multiplier AS Exchange1Multiplier,
        c1.Name       AS Country1Name,

        g.Stock2ID,
        s2.Ticker     AS Stock2Ticker,
        s2.FullName   AS Stock2FullName,
        e2.Name       AS Exchange2Name,
        e2.Multiplier AS Exchange2Multiplier,
        c2.Name       AS Country2Name,

        g.Stock3ID,
        s3.Ticker     AS Stock3Ticker,
        s3.FullName   AS Stock3FullName,
        e3.Name       AS Exchange3Name,
        e3.Multiplier AS Exchange3Multiplier,
        c3.Name       AS Country3Name

    FROM       stocks.StockGroup  g
    JOIN stocks.Stock    s1 ON s1.StockID    = g.Stock1ID
    JOIN stocks.Exchange e1 ON e1.ExchangeID = s1.ExchangeID
    JOIN stocks.Country  c1 ON c1.CountryID  = e1.CountryID
    JOIN stocks.Stock    s2 ON s2.StockID    = g.Stock2ID
    JOIN stocks.Exchange e2 ON e2.ExchangeID = s2.ExchangeID
    JOIN stocks.Country  c2 ON c2.CountryID  = e2.CountryID
    JOIN stocks.Stock    s3 ON s3.StockID    = g.Stock3ID
    JOIN stocks.Exchange e3 ON e3.ExchangeID = s3.ExchangeID
    JOIN stocks.Country  c3 ON c3.CountryID  = e3.CountryID

    ORDER BY g.GroupID;
END
GO

-- ── Group_Delete ─────────────────────────────────────────────
IF OBJECT_ID('stocks.Group_Delete', 'P') IS NOT NULL
    DROP PROCEDURE stocks.Group_Delete;
GO
CREATE PROCEDURE stocks.Group_Delete
    @GroupID INT
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM stocks.StockGroup WHERE GroupID = @GroupID;
END
GO

PRINT 'Group_Insert / Group_List / Group_Delete created.';
PRINT 'Done.';
