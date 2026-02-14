"""
Test SQL Dependency Parser Fixes
"""

from utils.sql_dependency_parser import SQLDependencyParser

def test_values_keyword_excluded():
    """Test that VALUES keyword is not captured as a function"""
    parser = SQLDependencyParser()
    
    sql = """
    INSERT INTO sales_analytics.customer_summary
    VALUES (1, 'John', 100)
    """
    
    deps = parser.parse_dependencies(sql)
    
    print("Test 1: VALUES keyword exclusion")
    print(f"  SQL: {sql.strip()}")
    print(f"  Functions found: {deps['functions']}")
    print(f"  ✓ PASS" if 'VALUES' not in deps['functions'] and 'values' not in [f.upper() for f in deps['functions']] else "  ✗ FAIL")
    print()
    
    return 'VALUES' not in deps['functions'] and 'values' not in [f.upper() for f in deps['functions']]


def test_full_table_names():
    """Test that full table names (dataset.table) are captured"""
    parser = SQLDependencyParser()
    
    sql = """
    SELECT * FROM sales_analytics.customer_data
    JOIN sales_analytics.orders ON customer_data.id = orders.customer_id
    """
    
    deps = parser.parse_dependencies(sql)
    
    print("Test 2: Full table name capture")
    print(f"  SQL: {sql.strip()}")
    print(f"  Tables found: {deps['tables']}")
    
    # Check if full names are captured
    has_full_names = any('.' in table for table in deps['tables'])
    has_customer_data = 'sales_analytics.customer_data' in deps['tables']
    has_orders = 'sales_analytics.orders' in deps['tables']
    
    print(f"  Has full names (dataset.table): {has_full_names}")
    print(f"  Has 'sales_analytics.customer_data': {has_customer_data}")
    print(f"  Has 'sales_analytics.orders': {has_orders}")
    print(f"  ✓ PASS" if has_full_names and has_customer_data and has_orders else "  ✗ FAIL")
    print()
    
    return has_full_names and has_customer_data and has_orders


def test_stored_procedure_with_values():
    """Test stored procedure that uses VALUES"""
    parser = SQLDependencyParser()
    
    sql = """
    CREATE OR REPLACE PROCEDURE update_summary()
    BEGIN
      INSERT INTO sales_analytics.summary
      SELECT customer_id, SUM(amount)
      FROM sales_analytics.transactions
      GROUP BY customer_id;
      
      INSERT INTO sales_analytics.audit_log
      VALUES (CURRENT_TIMESTAMP(), 'summary_updated');
    END
    """
    
    deps = parser.parse_dependencies(sql)
    
    print("Test 3: Stored procedure with VALUES and multiple tables")
    print(f"  Tables found: {deps['tables']}")
    print(f"  Functions found: {deps['functions']}")
    
    has_summary = 'sales_analytics.summary' in deps['tables']
    has_transactions = 'sales_analytics.transactions' in deps['tables']
    has_audit_log = 'sales_analytics.audit_log' in deps['tables']
    no_values = 'VALUES' not in deps['functions'] and 'values' not in [f.upper() for f in deps['functions']]
    
    print(f"  Has 'sales_analytics.summary': {has_summary}")
    print(f"  Has 'sales_analytics.transactions': {has_transactions}")
    print(f"  Has 'sales_analytics.audit_log': {has_audit_log}")
    print(f"  VALUES not in functions: {no_values}")
    print(f"  ✓ PASS" if has_summary and has_transactions and has_audit_log and no_values else "  ✗ FAIL")
    print()
    
    return has_summary and has_transactions and has_audit_log and no_values


def main():
    print("=" * 60)
    print("SQL Dependency Parser - Fix Verification Tests")
    print("=" * 60)
    print()
    
    test1 = test_values_keyword_excluded()
    test2 = test_full_table_names()
    test3 = test_stored_procedure_with_values()
    
    print("=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    print(f"Test 1 (VALUES exclusion): {'✓ PASS' if test1 else '✗ FAIL'}")
    print(f"Test 2 (Full table names): {'✓ PASS' if test2 else '✗ FAIL'}")
    print(f"Test 3 (Complex procedure): {'✓ PASS' if test3 else '✗ FAIL'}")
    print()
    
    if test1 and test2 and test3:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 60)


if __name__ == "__main__":
    main()
