# db/setup.py
# Initializes system_db and all tables for SmartRetail Final Revision
# Persistent database migration script — preserves user data across app restarts.

import mysql.connector
from mysql.connector import Error

DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = "admin123"
DB_NAME = "system_db"

def initialize_database():
    """Create system_db and all required tables if they do not exist."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            autocommit=True,
        )
        cursor = conn.cursor()

        # Create database
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute(f"USE {DB_NAME};")

        # ── 1. system_config ──────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                config_id INT AUTO_INCREMENT PRIMARY KEY,
                config_key VARCHAR(100) NOT NULL UNIQUE,
                config_value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
        """)

        # ── 2. users (Manager & Cashier Accounts) ────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                user_code VARCHAR(50) NOT NULL UNIQUE,
                username VARCHAR(100) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                full_name VARCHAR(200) NOT NULL,
                role ENUM('manager','cashier') NOT NULL DEFAULT 'cashier',
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ── 3. cashier_shifts (Shift Clock-In / Clock-Out Log) ───────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cashier_shifts (
                shift_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                cashier_code VARCHAR(50) NOT NULL,
                cashier_name VARCHAR(200) NOT NULL,
                time_in DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                time_out DATETIME NULL,
                total_hours DECIMAL(8,2) DEFAULT 0.00,
                shift_date DATE NOT NULL,
                total_sales_count INT NOT NULL DEFAULT 0,
                total_sales_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
        """)

        # ── 4. categories ────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                category_id INT AUTO_INCREMENT PRIMARY KEY,
                category_name VARCHAR(100) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ── 5. products ──────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                item_id INT AUTO_INCREMENT PRIMARY KEY,
                barcode VARCHAR(100) UNIQUE,
                item_name VARCHAR(200) NOT NULL,
                category VARCHAR(100) NOT NULL DEFAULT 'General',
                cost_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                markup_percent DECIMAL(5,2) NOT NULL DEFAULT 20.00,
                unit_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                stock_qty INT NOT NULL DEFAULT 0,
                reorder_level INT NOT NULL DEFAULT 5,
                expiry_date DATE NULL,
                image_path VARCHAR(500) NULL,
                is_basic_commodity TINYINT(1) NOT NULL DEFAULT 0,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ── 6. vouchers (Manager Created Single-Use Vouchers) ─────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vouchers (
                voucher_id INT AUTO_INCREMENT PRIMARY KEY,
                voucher_code VARCHAR(50) NOT NULL UNIQUE,
                discount_type ENUM('percent','fixed') NOT NULL DEFAULT 'fixed',
                discount_value DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                target_item_id INT NULL,
                is_redeemed TINYINT(1) NOT NULL DEFAULT 0,
                redeemed_at DATETIME NULL,
                redeemed_by_sale_id INT NULL,
                expiry_date DATE NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migration check: ensure expiry_date column exists on vouchers table
        try:
            cursor.execute("ALTER TABLE vouchers ADD COLUMN expiry_date DATE NULL;")
        except Error:
            pass   # Column already exists

        # ── 7. bulk_discounts ────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bulk_discounts (
                rule_id INT AUTO_INCREMENT PRIMARY KEY,
                item_id INT NOT NULL,
                min_quantity INT NOT NULL DEFAULT 3,
                discount_percent DECIMAL(5,2) NOT NULL DEFAULT 10.00,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (item_id) REFERENCES products(item_id) ON DELETE CASCADE
            );
        """)

        # ── 7b. item_promotions ──────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_promotions (
                promo_id INT AUTO_INCREMENT PRIMARY KEY,
                item_id INT NOT NULL UNIQUE,
                promo_type ENUM('none', 'b1t1_free', 'b1g1_percent', 'bundle', 'discount') NOT NULL DEFAULT 'none',
                second_item_discount_percent DECIMAL(5,2) NOT NULL DEFAULT 100.00,
                min_qty INT NOT NULL DEFAULT 2,
                discount_percent DECIMAL(5,2) NOT NULL DEFAULT 0.00,
                discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                promo_label VARCHAR(100) NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES products(item_id) ON DELETE CASCADE
            );
        """)

        # ── 8. sales ─────────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                sale_id INT AUTO_INCREMENT PRIMARY KEY,
                si_number VARCHAR(100) NOT NULL UNIQUE,
                shift_id INT NULL,
                cashier_code VARCHAR(50) NOT NULL DEFAULT 'CSH-101',
                cashier_name VARCHAR(200) NOT NULL DEFAULT 'Cashier',
                subtotal DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                vatable_sales DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                vat_exempt_sales DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                zero_rated_sales DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                discount_type VARCHAR(50) NOT NULL DEFAULT 'none',
                discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                pwd_id_number VARCHAR(100) NULL,
                voucher_code VARCHAR(50) NULL,
                total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                payment_method ENUM('cash','gcash') NOT NULL DEFAULT 'cash',
                payment_reference VARCHAR(100) NULL,
                cash_received DECIMAL(10,2) NULL,
                change_amount DECIMAL(10,2) NULL,
                status ENUM('completed','voided') NOT NULL DEFAULT 'completed',
                voided_by_manager VARCHAR(100) NULL,
                void_reason TEXT NULL,
                notes TEXT NULL,
                sale_date DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ── 9. sale_items ────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                sale_item_id INT AUTO_INCREMENT PRIMARY KEY,
                sale_id INT NOT NULL,
                item_id INT NOT NULL,
                item_name VARCHAR(200) NOT NULL,
                barcode VARCHAR(100) NULL,
                unit_price DECIMAL(10,2) NOT NULL,
                quantity INT NOT NULL DEFAULT 1,
                line_total DECIMAL(10,2) NOT NULL,
                line_promo_discount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                promo_tag VARCHAR(100) NULL,
                is_vatable TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (sale_id) REFERENCES sales(sale_id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES products(item_id) ON DELETE CASCADE
            );
        """)

        # Migration check: ensure line_promo_discount and promo_tag columns exist on sale_items
        try:
            cursor.execute("ALTER TABLE sale_items ADD COLUMN line_promo_discount DECIMAL(10,2) NOT NULL DEFAULT 0.00;")
        except Error:
            pass
        try:
            cursor.execute("ALTER TABLE sale_items ADD COLUMN promo_tag VARCHAR(100) NULL;")
        except Error:
            pass

        # ── 10. inventory_movements ──────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_movements (
                movement_id INT AUTO_INCREMENT PRIMARY KEY,
                item_id INT NOT NULL,
                movement_type ENUM('restock','sale','adjustment','return') NOT NULL,
                quantity INT NOT NULL,
                notes TEXT NULL,
                reference_id INT NULL,
                moved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES products(item_id) ON DELETE CASCADE
            );
        """)

        # Check if initial data has been seeded
        cursor.execute("SELECT COUNT(*) FROM users;")
        user_count = cursor.fetchone()[0]

        if user_count == 0:
            # ── Seed IT Special Admin Code ───────────────────────────────────
            cursor.execute("""
                INSERT INTO system_config (config_key, config_value)
                VALUES ('it_special_code', 'IT-ADMIN-9999'),
                       ('store_name', 'ROBINSONS SUPERMARKET CORPORATION'),
                       ('tin_no', '000-405-340-010'),
                       ('store_address', 'Robinsons Town Mall Los Banos, Lopez Ave., Batong Malake, Los Banos, Laguna'),
                       ('serial_no', '4CE423DOMF'),
                       ('machine_id', '24103116151605407'),
                       ('terminal_no', '0017'),
                       ('store_no', '0202')
                ON DUPLICATE KEY UPDATE config_value=VALUES(config_value);
            """)

            # ── Seed Default Users ───────────────────────────────────────────
            cursor.execute("""
                INSERT INTO users (user_code, username, password, full_name, role)
                VALUES ('MGR-001', 'admin', 'admin123', 'System Administrator', 'manager'),
                       ('CSH-101', 'cashier', 'cashier123', 'Belda, Marinel B.', 'cashier');
            """)

            # ── Seed Default Categories ──────────────────────────────────────
            categories = [
                "Rice & Grains", "Dairy & Eggs", "Beverages",
                "Canned Goods", "Bakery & Bread", "Personal Care & Soap",
                "Snacks & Chips", "Alcohol & Beverages"
            ]
            for cat in categories:
                cursor.execute("INSERT IGNORE INTO categories (category_name) VALUES (%s);", (cat,))

            # ── Seed Initial Sample Products ─────────────────────────────────
            sample_products = [
                ("04800361402354", "Premium Dinorado Rice 5kg", "Rice & Grains", 250.00, 20.0, 300.00, 50, 10, "2027-12-31", 1),
                ("04806502572511", "Fresh Farm Large Eggs 12s", "Dairy & Eggs", 80.00, 25.0, 100.00, 40, 8, "2026-10-15", 1),
                ("04800092001122", "Nescafe Classic Coffee 100g", "Beverages", 75.00, 20.0, 90.00, 35, 10, "2027-08-30", 1),
                ("04800999000111", "Piattos Cheese Snacks 85g", "Snacks & Chips", 30.00, 20.0, 36.00, 45, 10, "2027-04-12", 0),
            ]

            for p in sample_products:
                cursor.execute("""
                    INSERT IGNORE INTO products
                    (barcode, item_name, category, cost_price, markup_percent, unit_price, stock_qty, reorder_level, expiry_date, is_basic_commodity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, p)

            # Seed sample vouchers
            cursor.execute("""
                INSERT IGNORE INTO vouchers (voucher_code, discount_type, discount_value)
                VALUES ('WELCOME50', 'fixed', 50.00),
                       ('SUPER10', 'percent', 10.00);
            """)

        cursor.close()
        conn.close()
        return True, "Database verified successfully. User data preserved."

    except Error as e:
        return False, f"Database setup error: {e}"


if __name__ == "__main__":
    ok, msg = initialize_database()
    print(msg)
