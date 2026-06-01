#!/bin/bash
# =============================================================================
# import_oracle_assurcourt.sh — Import classic Oracle DMP into schema ASSURCOURT
# =============================================================================
set -e

echo "=== [1/3] Recreating user ASSURCOURT in Oracle Database ==="
docker exec -i oracle11g sqlplus -S system/oracle <<EOF
-- Drop the existing user cascade to clean up all objects
DROP USER ASSURCOURT CASCADE;

-- Recreate user
CREATE USER ASSURCOURT IDENTIFIED BY ASSURCOURT DEFAULT TABLESPACE USERS TEMPORARY TABLESPACE TEMP;

-- Grant required roles and privileges
GRANT CONNECT, RESOURCE, DBA, DATAPUMP_EXP_FULL_DATABASE, DATAPUMP_IMP_FULL_DATABASE TO ASSURCOURT;

-- Grant unlimited quota on USERS tablespace
ALTER USER ASSURCOURT QUOTA UNLIMITED ON USERS;

EXIT;
EOF

echo "=== [2/3] Importing dump into ASSURCOURT schema ==="
# Run the classic import utility imp inside the container
docker exec -i oracle11g imp system/oracle \
  file=/u01/app/oracle/oradata/ASSKAREKAMOUN_2026_05_22.dmp \
  fromuser=ASSKAREKAMOUN \
  touser=ASSURCOURT \
  grants=y \
  rows=y \
  commit=y \
  buffer=10000000 \
  log=/u01/app/oracle/oradata/import_assurcourt.log || true

echo "=== [3/3] Import completed! Checking import log ==="
tail -n 20 /root/oracle_data/import_assurcourt.log
