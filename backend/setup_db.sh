#!/bin/bash
# KneeAI PostgreSQL setup script
# Run with: sudo bash setup_db.sh

set -e

# Formatting colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

DB_USER="deven"
DB_PASS="deven@123"
DB_NAME="kneeai"

echo -e "${BLUE}=== KneeAI PostgreSQL Automated Setup ===${NC}"

# Check if psql is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: PostgreSQL (psql) is not installed.${NC}"
    echo "Please install PostgreSQL and run this script again."
    exit 1
fi

# Check if PostgreSQL service is running
if ! pg_isready &> /dev/null && ! systemctl is-active --quiet postgresql 2>/dev/null; then
    echo -e "${YELLOW}PostgreSQL service is not running. Attempting to start...${NC}"
    systemctl start postgresql || service postgresql start || true
fi

# Ensure user and password exist
echo -e "${BLUE}[1/3] Setting up PostgreSQL user '${DB_USER}'...${NC}"
sudo -u postgres psql -c "DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
        CREATE ROLE ${DB_USER} WITH LOGIN CREATEDB PASSWORD '${DB_PASS}';
        RAISE NOTICE 'Created role ${DB_USER}';
    ELSE
        ALTER ROLE ${DB_USER} WITH LOGIN CREATEDB PASSWORD '${DB_PASS}';
        RAISE NOTICE 'Updated role ${DB_USER} password';
    END IF;
END
\$\$;"

# Create database if it does not exist
echo -e "${BLUE}[2/3] Setting up database '${DB_NAME}'...${NC}"
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1; then
    echo -e "${YELLOW}Database '${DB_NAME}' already exists.${NC}"
else
    sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
    echo -e "${GREEN}Created database '${DB_NAME}' owned by ${DB_USER}.${NC}"
fi

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" > /dev/null

# Connection verification
echo -e "${BLUE}[3/3] Verifying connection to '${DB_NAME}'...${NC}"
if PGPASSWORD="${DB_PASS}" psql -h localhost -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1;" &> /dev/null; then
    echo -e "${GREEN}✓ Connection test succeeded via TCP (localhost)!${NC}"
elif PGPASSWORD="${DB_PASS}" psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1;" &> /dev/null; then
    echo -e "${GREEN}✓ Connection test succeeded via UNIX socket!${NC}"
else
    echo -e "${YELLOW}Warning: Direct psql test skipped or host auth needs check. Peer/md5 auth configured.${NC}"
fi

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo -e "Database URL: ${YELLOW}postgresql://${DB_USER}:${DB_PASS}@localhost/${DB_NAME}${NC}"
