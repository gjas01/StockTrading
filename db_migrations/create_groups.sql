-- ============================================================
-- Reset stock schema data and create 3-stock group objects.
--
-- Step 1 : clears all rows from existing tables (FK-safe order)
--          and reseeds identity columns back to 1.
-- Step 2 : creates the StockGroup table (skipped if it already
--          exists from a previous run).
-- Step 3 : creates / replaces Group_Insert, Group_List and
--          Group_Delete stored procedures.
-- Step 4 : updates Stock_Delete to also block deletion when the
--          stock belongs to a group.
--
-- Run against the target SQL Server database (stocks schema).
-- ============================================================

set ansi_nulls on
set quoted_identifier on
go


-- ============================================================
-- 1. Clear existing data (FK-safe order: children before parents)
-- ============================================================

print 'Clearing existing data...';

if object_id('[stocks].[StockGroup]', 'U') is not null
begin
    delete from [stocks].[StockGroup];
    print '  stocks.StockGroup cleared';
end;

if object_id('[stocks].[Pair]', 'U') is not null
begin
    delete from [stocks].[Pair];
    print '  stocks.Pair cleared';
end;

if object_id('[stocks].[StockPrice]', 'U') is not null
begin
    delete from [stocks].[StockPrice];
    print '  stocks.StockPrice cleared';
end;

delete from [stocks].[Stock];
print '  stocks.Stock cleared';

delete from [stocks].[Exchange];
print '  stocks.Exchange cleared';

delete from [stocks].[Country];
print '  stocks.Country cleared';

-- Reseed so the first new row in each table gets ID = 1
dbcc checkident ('[stocks].[Country]',   reseed, 0) with no_infomsgs;
dbcc checkident ('[stocks].[Exchange]',  reseed, 0) with no_infomsgs;
dbcc checkident ('[stocks].[Stock]',     reseed, 0) with no_infomsgs;

if object_id('[stocks].[StockPrice]', 'U') is not null
    dbcc checkident ('[stocks].[StockPrice]', reseed, 0) with no_infomsgs;

if object_id('[stocks].[StockGroup]', 'U') is not null
    dbcc checkident ('[stocks].[StockGroup]', reseed, 0) with no_infomsgs;

print 'Data cleared and identity seeds reset.';
go


-- ============================================================
-- 2. StockGroup table
-- ============================================================

if object_id('[stocks].[StockGroup]', 'U') is null
begin
    create table [stocks].[StockGroup]
    (
        [GroupID]   bigint        identity(1,1) not null
      , [GroupName] nvarchar(200) not null
      , [Stock1ID]  bigint        not null
      , [Stock2ID]  bigint        not null
      , [Stock3ID]  bigint        not null
      , [CreatedAt] datetime2     not null constraint [DF_StockGroup_CreatedAt] default getdate()
      , constraint [PK_StockGroup]    primary key clustered ([GroupID])
      , constraint [FK_StockGroup_S1] foreign key ([Stock1ID]) references [stocks].[Stock] ([StockID])
      , constraint [FK_StockGroup_S2] foreign key ([Stock2ID]) references [stocks].[Stock] ([StockID])
      , constraint [FK_StockGroup_S3] foreign key ([Stock3ID]) references [stocks].[Stock] ([StockID])
      , constraint [CK_StockGroup_DifferentStocks] check (
            [Stock1ID] <> [Stock2ID]
        and [Stock1ID] <> [Stock3ID]
        and [Stock2ID] <> [Stock3ID]
        )
    );
    print 'stocks.StockGroup created.';
end;
else
    print 'stocks.StockGroup already exists — skipped.';
go


-- ============================================================
-- 3. Group_Insert
-- ============================================================

create or alter procedure [stocks].[Group_Insert]
    @GroupName nvarchar(200)
  , @Stock1ID  bigint
  , @Stock2ID  bigint
  , @Stock3ID  bigint
as
set nocount, xact_abort on;

if @GroupName is null or ltrim(rtrim(@GroupName)) = ''
begin
    raiserror('Group name cannot be empty.', 16, 1);
    return;
end;

if @Stock1ID = @Stock2ID or @Stock1ID = @Stock3ID or @Stock2ID = @Stock3ID
begin
    raiserror('All three stocks in a group must be different.', 16, 1);
    return;
end;

if not exists (select 1 from [stocks].[Stock] where [StockID] = @Stock1ID)
begin
    raiserror('Stock 1 does not exist.', 16, 1);
    return;
end;

if not exists (select 1 from [stocks].[Stock] where [StockID] = @Stock2ID)
begin
    raiserror('Stock 2 does not exist.', 16, 1);
    return;
end;

if not exists (select 1 from [stocks].[Stock] where [StockID] = @Stock3ID)
begin
    raiserror('Stock 3 does not exist.', 16, 1);
    return;
end;

insert into [stocks].[StockGroup] ([GroupName], [Stock1ID], [Stock2ID], [Stock3ID])
values (@GroupName, @Stock1ID, @Stock2ID, @Stock3ID);

select scope_identity() as GroupID;
go

grant execute on [stocks].[Group_Insert] to [user_serv_role];
go


-- ============================================================
-- 4. Group_List
-- ============================================================

create or alter procedure [stocks].[Group_List]
as
set nocount, xact_abort on;

select
    g.[GroupID]
  , g.[GroupName]
  , g.[Stock1ID]
  , s1.[Ticker]     as [Stock1Ticker]
  , s1.[FullName]   as [Stock1FullName]
  , e1.[Name]       as [Exchange1Name]
  , e1.[Multiplier] as [Exchange1Multiplier]
  , c1.[Name]       as [Country1Name]
  , g.[Stock2ID]
  , s2.[Ticker]     as [Stock2Ticker]
  , s2.[FullName]   as [Stock2FullName]
  , e2.[Name]       as [Exchange2Name]
  , e2.[Multiplier] as [Exchange2Multiplier]
  , c2.[Name]       as [Country2Name]
  , g.[Stock3ID]
  , s3.[Ticker]     as [Stock3Ticker]
  , s3.[FullName]   as [Stock3FullName]
  , e3.[Name]       as [Exchange3Name]
  , e3.[Multiplier] as [Exchange3Multiplier]
  , c3.[Name]       as [Country3Name]
from [stocks].[StockGroup] g
inner join [stocks].[Stock]    s1 on s1.[StockID]    = g.[Stock1ID]
inner join [stocks].[Exchange] e1 on e1.[ExchangeID] = s1.[ExchangeID]
inner join [stocks].[Country]  c1 on c1.[CountryID]  = e1.[CountryID]
inner join [stocks].[Stock]    s2 on s2.[StockID]    = g.[Stock2ID]
inner join [stocks].[Exchange] e2 on e2.[ExchangeID] = s2.[ExchangeID]
inner join [stocks].[Country]  c2 on c2.[CountryID]  = e2.[CountryID]
inner join [stocks].[Stock]    s3 on s3.[StockID]    = g.[Stock3ID]
inner join [stocks].[Exchange] e3 on e3.[ExchangeID] = s3.[ExchangeID]
inner join [stocks].[Country]  c3 on c3.[CountryID]  = e3.[CountryID]
order by g.[GroupID];
go

grant execute on [stocks].[Group_List] to [user_serv_role];
go


-- ============================================================
-- 5. Group_Delete
-- ============================================================

create or alter procedure [stocks].[Group_Delete]
    @GroupID bigint
as
set nocount, xact_abort on;

if not exists (select 1 from [stocks].[StockGroup] where [GroupID] = @GroupID)
begin
    raiserror('Group does not exist.', 16, 1);
    return;
end;

delete from [stocks].[StockGroup]
where [GroupID] = @GroupID;
go

grant execute on [stocks].[Group_Delete] to [user_serv_role];
go


-- ============================================================
-- 6. Stock_Delete — add group membership check
-- ============================================================

create or alter procedure [stocks].[Stock_Delete]
    @StockID bigint
as
set nocount, xact_abort on;

if not exists (select 1 from [stocks].[Stock] where [StockID] = @StockID)
begin
    raiserror('Stock does not exist.', 16, 1);
    return;
end;

declare @PairIDs nvarchar(max);

select @PairIDs = string_agg(cast(p.[PairID] as nvarchar(20)), ', ')
from [stocks].[Pair] p
where p.[PrimaryStockID] = @StockID
   or p.[SecondaryStockID] = @StockID;

if @PairIDs is not null
begin
    raiserror(
        'Cannot delete stock: it is used in pair(s) %s. Delete those pairs first.',
        16, 1, @PairIDs
    );
    return;
end;

declare @GroupIDs nvarchar(max);

select @GroupIDs = string_agg(cast(g.[GroupID] as nvarchar(20)), ', ')
from [stocks].[StockGroup] g
where g.[Stock1ID] = @StockID
   or g.[Stock2ID] = @StockID
   or g.[Stock3ID] = @StockID;

if @GroupIDs is not null
begin
    raiserror(
        'Cannot delete stock: it is used in group(s) %s. Delete those groups first.',
        16, 1, @GroupIDs
    );
    return;
end;

delete from [stocks].[StockPrice]
where [StockID] = @StockID;

delete from [stocks].[Stock]
where [StockID] = @StockID;
go

grant execute on [stocks].[Stock_Delete] to [user_serv_role];
go

print 'Done.';
