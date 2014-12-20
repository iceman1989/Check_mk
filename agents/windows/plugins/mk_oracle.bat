@echo off

REM ; If you not run this plugin with the environment variable ORACLE_SID set,
REM ; you can uncomment (Remove the "REM " prefix) the line below to
REM ; use e.g. "localhost" as oracle sid.
REM SET ORACLE_SID=localhost

REM ; If you like to use a special auth parameter please change the line below
SET AUTH=/ as sysdba

echo ^<^<^<oracle_version^>^>^>
(echo.|set /p x=%ORACLE_SID% )
(
echo set cmdsep on
echo set cmdsep '"'; --"
echo "set pages 0"
echo "set feedback off"
echo "set head off"
echo "select banner from v$version where banner like 'Oracle%%';"
) | sqlplus -S %AUTH%

echo ^<^<^<oracle_sessions^>^>^>
(echo.|set /p x=%ORACLE_SID%)
(
echo set cmdsep on
echo set cmdsep '"'; --"
echo "set pages 0"
echo "set feedback off"
echo "set head off"
echo "select count(*) from v$session where status = 'ACTIVE';"
) | sqlplus -S %AUTH%

echo ^<^<^<oracle_logswitches^>^>^>
(echo.|set /p x=%ORACLE_SID%)
(
echo set cmdsep on
echo set cmdsep '"'; --"
echo "set pages 0"
echo "set feedback off"
echo "set head off"
echo "select count(*) from v$loghist where first_time > sysdate - 1/24;"
) | sqlplus -S %AUTH%

REM ; This is nearly the same query as in the linux agent. With the exception that the
REM ; column th.instance is fetched as first column to get the SID
echo ^<^<^<oracle_tablespaces^>^>^>
(
echo set cmdsep on
echo set cmdsep '"'; --"
echo "set pages 0"
echo "set linesize 900"
echo "set tab off"
echo "set feedback off"
echo "set head off"
echo "column instance format a10"
echo "column file_name format a100"
echo "select th.instance, f.file_name, f.tablespace_name, f.status, f.AUTOEXTENSIBLE, f.blocks, f.maxblocks, f.USER_BLOCKS, f.INCREMENT_BY, f.ONLINE_STATUS, t.BLOCK_SIZE, t.status, decode(sum(fs.blocks), NULL, 0, sum(fs.blocks)) free_blocks from v$thread th, dba_data_files f, dba_tablespaces t, dba_free_space fs where f.tablespace_name = t.tablespace_name and f.file_id = fs.file_id(+) group by th.instance, f.file_name, f.tablespace_name, f.status, f.autoextensible, f.blocks, f.maxblocks, f.user_blocks, f.increment_by, f.online_status, t.block_size, t.status UNION SELECT th.instance, f.file_name, f.tablespace_name, f.status, f.AUTOEXTENSIBLE, f.blocks, f.maxblocks, f.USER_BLOCKS, f.INCREMENT_BY, 'TEMP', t.BLOCK_SIZE, t.status, sum(sh.blocks_free) free_blocks FROM v$thread th, dba_temp_files f, dba_tablespaces t, v$temp_space_header sh WHERE f.tablespace_name = t.tablespace_name and f.file_id = sh.file_id GROUP BY th.instance, f.file_name, f.tablespace_name, f.status, f.autoextensible, f.blocks, f.maxblocks, f.user_blocks, f.increment_by, 'TEMP', t.block_size, t.status;"
) | sqlplus -S %AUTH%
