#-*- coding: utf-8 -*-

import jaydebeapiarrow
import os
import unittest

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
