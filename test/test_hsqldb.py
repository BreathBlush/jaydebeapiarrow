#-*- coding: utf-8 -*-

import jaydebeapiarrow
import os
import unittest

from decimal import Decimal
from datetime import datetime
try:
    from test._base import IntegrationTestBase, _THIS_DIR
except ImportError:
    from _base import IntegrationTestBase, _THIS_DIR


class HsqldbTest(IntegrationTestBase, unittest.TestCase):

    def connect(self):
        # http://hsqldb.org/
        # hsqldb.jar
        driver, url, driver_args = ( 'org.hsqldb.jdbcDriver',
                                     'jdbc:hsqldb:mem:.',
                                     ['SA', ''] )
        return jaydebeapiarrow, jaydebeapiarrow.connect(driver, url, driver_args)

    def setUpSql(self):
        self.sql_file(os.path.join(_THIS_DIR, 'data', 'create_hsqldb.sql'))
        self.sql_file(os.path.join(_THIS_DIR, 'data', 'insert.sql'))

    def test_varchar_non_ascii_roundtrip(self):
        """Verify that VARCHAR columns containing non-ASCII characters
        round-trip correctly through the Arrow path. Regression test for
        legacy issue baztian/jaydebeapi#176 where reading VARCHAR columns
        with umlauts caused CharConversionException."""
        test_cases = [
            "Grüße aus München",
            "café — résumé",
            "こんにちは",
            "Hello 🌍",
        ]
        stmt = ("insert into ACCOUNT (ACCOUNT_ID, ACCOUNT_NO, BALANCE, "
                "PRODUCT_NAME) values (?, ?, ?, ?)")
        with self.conn.cursor() as cursor:
            for idx, text in enumerate(test_cases):
                ts = self.dbapi.Timestamp(2024, 1, 15, 10, 0, 0, idx * 100000)
                cursor.execute(stmt, (ts, 50 + idx, Decimal('1.0'), text))
            cursor.execute(
                "select PRODUCT_NAME from ACCOUNT "
                "where ACCOUNT_NO >= 50 order by ACCOUNT_NO")
            results = cursor.fetchall()
        for idx, text in enumerate(test_cases):
            self.assertEqual(results[idx][0], text,
                             f"Failed for text: {text!r}")

    def test_long_query_string_18k_characters(self):
        """SQL queries with 18k+ characters must execute correctly.
        Regression test for baztian/jaydebeapi#91 where long queries
        caused failures in the legacy codebase."""
        long_query = ("SELECT ACCOUNT_NO FROM ACCOUNT WHERE ACCOUNT_NO IN ("
                      + ",".join(str(i) for i in range(5000)) + ")")
        self.assertGreater(len(long_query), 18000,
                           "Test query must exceed 18k characters")
        with self.conn.cursor() as cursor:
            cursor.execute(long_query)
            result = cursor.fetchall()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2,
                         "Both ACCOUNT rows (18, 19) should match the IN clause")
        returned_ids = sorted(row[0] for row in result)
        self.assertEqual(returned_ids, [18, 19])

    def test_iterator_closed_after_fetchall(self):
        """After fetchall exhausts the result set, the Arrow iterator should
        be closed and nulled out (memory leak regression, legacy #227)."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM Account")
            cursor.fetchall()
            self.assertIsNone(cursor._iter)

    def test_iterator_closed_after_fetchone_exhaustion(self):
        """After fetchone exhausts the result set, iterator should be closed."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM Account")
            cursor.fetchone()
            result = cursor.fetchone()
            self.assertIsNone(result)
            self.assertIsNone(cursor._iter)

    def test_iterator_closed_after_fetchmany_exhaustion(self):
        """After fetchmany exhausts the result set, iterator should be closed."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM Account")
            cursor.fetchmany(size=1000)
            self.assertIsNone(cursor._iter)

    def test_repeated_query_cycles_release_resources(self):
        """Repeated execute/fetchall cycles should not accumulate iterators
        or buffers (memory leak regression, legacy #227)."""
        with self.conn.cursor() as cursor:
            for _ in range(5):
                cursor.execute("SELECT * FROM Account")
                result = cursor.fetchall()
                self.assertTrue(len(result) > 0)
                self.assertIsNone(cursor._iter)
                self.assertEqual(cursor._buffer, [])

    def test_description_returns_column_alias(self):
        """cursor.description should return the AS alias, not the table column name."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT ACCOUNT_NO AS acct_num FROM ACCOUNT")
            self.assertEqual(cursor.description[0][0], "ACCT_NUM")


    def test_timestamp_utc_roundtrip_no_timezone_shift(self):
        """Verify TIMESTAMP values round-trip without timezone shifting.

        Regression test for baztian/jaydebeapi#73. Legacy jaydebeapi returned
        timestamps in the JVM's local timezone instead of UTC. This test
        inserts specific timestamp values via parameter binding and verifies
        they are returned as naive datetime objects with exact values — no
        timezone offset applied.
        """
        test_cases = [
            # (inserted_timestamp, description)
            (self.dbapi.Timestamp(2024, 1, 15, 0, 0, 0),
             "UTC midnight — legacy bug would shift to previous day in EST"),
            (self.dbapi.Timestamp(2024, 6, 15, 14, 30, 0, 123456),
             "midday with microseconds"),
            (self.dbapi.Timestamp(2024, 12, 31, 23, 59, 59, 999999),
             "end-of-day edge case — legacy bug could roll over to next day"),
        ]
        stmt = ("insert into ACCOUNT (ACCOUNT_ID, ACCOUNT_NO, BALANCE) "
                "values (?, ?, ?)")
        with self.conn.cursor() as cursor:
            for idx, (ts, _desc) in enumerate(test_cases):
                cursor.execute(stmt, (ts, 100 + idx, Decimal('1.0')))
            cursor.execute(
                "select ACCOUNT_ID from ACCOUNT "
                "where ACCOUNT_NO >= 100 order by ACCOUNT_NO")
            results = cursor.fetchall()
        for idx, (ts, desc) in enumerate(test_cases):
            with self.subTest(desc=desc):
                self.assertEqual(results[idx][0], ts)
                self.assertIsNone(results[idx][0].tzinfo,
                                  "TIMESTAMP must return naive datetime")

    def test_varchar_columns_return_data(self):
        """Verify VARCHAR columns return actual data, not empty strings.

        Regression test for legacy issue #119 where Oracle 9i VARCHAR2 columns
        returned empty strings while numeric fields worked fine. The original
        jaydebeapi used getObject() which could return driver-specific types
        (e.g., oracle.sql.CHAR) that JPype couldn't convert. jaydebeapiarrow's
        Arrow JDBC adapter uses getString() for VARCHAR columns, which always
        returns a proper java.lang.String.
        """
        with self.conn.cursor() as cursor:
            # Insert rows with VARCHAR data
            cursor.execute(
                "INSERT INTO ACCOUNT "
                "(ACCOUNT_ID, ACCOUNT_NO, BALANCE, PRODUCT_NAME) "
                "VALUES ('2010-01-01 00:00:00.000000', 100, 99.99, 'Savings Account')"
            )
            cursor.execute(
                "INSERT INTO ACCOUNT "
                "(ACCOUNT_ID, ACCOUNT_NO, BALANCE, PRODUCT_NAME) "
                "VALUES ('2010-01-02 00:00:00.000000', 101, 0.00, 'Checking Account')"
            )
            # Query with mixed VARCHAR and numeric columns
            cursor.execute(
                "SELECT ACCOUNT_NO, BALANCE, PRODUCT_NAME "
                "FROM ACCOUNT WHERE ACCOUNT_NO >= 100 ORDER BY ACCOUNT_NO"
            )
            result = cursor.fetchall()
        self.assertEqual(len(result), 2)
        # Verify numeric data is present
        self.assertEqual(result[0][0], 100)
        self.assertEqual(result[0][1], Decimal('99.99'))
        # Verify VARCHAR data is NOT empty
        self.assertIsInstance(result[0][2], str)
        self.assertEqual(result[0][2], 'Savings Account')
        self.assertNotEqual(result[0][2], '')
        self.assertEqual(result[1][2], 'Checking Account')

    def test_commit_with_autocommit_enabled(self):
        """commit() should not raise when autocommit is enabled."""
        self.conn.jconn.setAutoCommit(True)
        self.conn.commit()

    def test_commit_with_autocommit_disabled(self):
        """commit() should succeed normally when autocommit is disabled."""
        self.conn.jconn.setAutoCommit(False)
        self.conn.commit()

    def test_rollback_with_autocommit_enabled(self):
        """rollback() should not raise when autocommit is enabled."""
        self.conn.jconn.setAutoCommit(True)
        self.conn.rollback()

    def test_rollback_with_autocommit_disabled(self):
        """rollback() should succeed normally when autocommit is disabled."""
        self.conn.jconn.setAutoCommit(False)
        self.conn.rollback()
